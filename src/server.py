import os, json, tempfile, pytest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pygit2 import clone_repository, GIT_OBJ_BLOB, GIT_OBJ_TREE
from ast import parse
from github import Github
from pathlib import Path
from datetime import datetime

hostName = "localhost"
serverPort = 8080
builds_filename = "./builds.json"

class CIServer(HTTPServer):
    """
    This class is for the most part identical to the HTTPServer class.
    However, it also allows the server to be started with the run method
    whose only purpose is to be run in a thread when running unit tests.
    Additionally, it prints a message when started and stopped.
    It can be conventiently shut down using the inherited shutdown method.
    """
    def run(self):
        print("Server started.")
        try:
            self.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            print("Server stopped.")
            self.server_close()

class CIServerHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        """
        This is the main method for the CI server since GitHub delivers webhooks via POST.
        It attempts to read the received DATA as a GitHub-generated JSON from a push that
        contains a repository URL and a reference to a branch. It then tries to parse all
        Python source code in the repository and displays which files contain syntax errors.
        """
        # Read POST data
        content_length = int(self.headers.get("Content-Length"))
        raw_post_data = self.rfile.read(content_length)
        try:
            post_data = json.loads(raw_post_data.decode("utf-8"))
        except json.JSONDecodeError:
            print("Malformed JSON received!")
            self.send_response(400)
            return

        # Send response code & headers
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

        try:
            repository_url = post_data["repository"]["clone_url"]
            branch_name = "/".join(post_data["ref"].split("/")[2:])
        except KeyError:
            print("Invalid JSON received: one or more required fields are missing!")
            self.send_response(400)
            return

        # Clone repository
        with tempfile.TemporaryDirectory() as repo_path:
            repo = clone_repository(repository_url, repo_path, checkout_branch=branch_name)
            head_commit = repo.revparse_single(branch_name)
            tree = head_commit.tree
            # Check for syntax errors
            syntax_errors = CIServerHandler.try_compile_all(tree, repo_path)
            print("All source files checked:", syntax_errors, "syntax errors")
            # Check if unit tests fail
            previous_dir = os.getcwd()
            os.chdir(repo_path)
            exit_code = pytest.main()
            if exit_code == 0:
                print("All pytest tests were successful!")
            else:
                print("Some pytest error or failed test occurred.")
            os.chdir(previous_dir)

            # Set commit status
            state = ""
            description = ""
            if syntax_errors != 0:
                state = "failure" # syntax errors, couldn't build
                description = "Couldn't build due to syntax errors"
            elif exit_code == 0:
                state = "success" # no syntax errors, there were tests and they succeeded
                description = "No syntax errors, all tests succeeded"
            else:
                state = "error" # there were no tests or at least one of them failed (or some internal pytest error)
                description = "Tests failed"

            try:
                repo_name = post_data["repository"]["name"]
                owner_name = post_data["repository"]["owner"]["name"]
                commit_sha = post_data["head_commit"]["id"]
                CIServerHandler.set_commit_status(owner_name, repo_name, commit_sha, state, description)

                # Save build status to builds.json
                CIServerHandler.save_build(commit_sha, f"{state}: {description}")

            except KeyError:
                print("Missing fields in POST request!")
                self.send_response(400)
                return

            if repo is not None:
                repo.free()

        # Send response data
        self.wfile.write(bytes("CI jobs done!", "utf-8"))

    @staticmethod
    def set_commit_status(owner_name, repo_name, commit_sha, state, description="", context="continuous-integration"):
        """
        Uses the input parameters to set a commit status on the relevant commit on GitHub.
        Needs to have the CI_SERVER_AUTH_TOKEN environment variable set to a valid personal access token with
        access rights to repo:status. 
        """
        try:
            g = Github(os.environ["CI_SERVER_AUTH_TOKEN"])
            repo = g.get_user(owner_name).get_repo(repo_name)
            sha = repo.get_commit(sha=commit_sha)
            sha.create_status(
                state=state,
                context=context,
                description=description
            )
        except KeyError:
            print("Can't set commit status: CI_SERVER_AUTH_TOKEN environment variable not set.")

    @staticmethod
    def try_compile_all(tree, repo_path, relative_path=""):
        """
        This method recursively iterates through a git tree and attempts to parse every file containing Python source code,
        which it identifies using the .py file extension. It takes three arguments: a git tree, a path to the repository
        containing the tree, and the relative path to the tree within the repository. If the tree represents the entire
        repository, the relative path should be set to an empty string. Files in directories called "test" are ignored.
        """
        errors = 0
        for item in tree:
            if item.type == GIT_OBJ_BLOB and item.name.endswith(".py") and not item.name.startswith("__init__.py"):
                with open(os.path.join(repo_path, relative_path, item.name), "r") as f:
                    source = f.read()
                try:
                    parse(source)
                    print("OK:", os.path.join(relative_path, item.name))
                except SyntaxError:
                    errors += 1
                    print("ERR:", os.path.join(relative_path, item.name))
            elif item.type == GIT_OBJ_TREE and item.name != "test": # The test directory should be ignored as it may contain example files that are invalid on purpose
                errors += CIServerHandler.try_compile_all(item, repo_path, os.path.join(relative_path, item.name))
        return errors

    def do_GET(self):
        """
        Responds to a GET request by writing to the console (so you can test the server by visiting localhost)
        """
        CIServerHandler.ensure_builds_json_exists()
        if self.path == "/": # index page
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()

            builds_json = CIServerHandler.try_json_load(builds_filename)
            builds = list(builds_json.keys())
            build_page = CIServerHandler.generate_build_list(builds)
            self.wfile.write(bytes(build_page, "utf-8"))
        else: # build with a given SHA
            build = CIServerHandler.read_build(self.path[1:])
            if build is None:
                self.send_response(404)
            else:
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                build_page = CIServerHandler.generate_build_html_document(self.path[1:], build)
                self.wfile.write(bytes(build_page, "utf-8"))

        print("Connection!")

    @staticmethod
    def ensure_builds_json_exists():
        """
        Check if builds.json exists. If it does not, it creates it and initializes it with a dummy field.
        """
        file_path = Path(builds_filename)
        file_path.touch(exist_ok=True)
    
    @staticmethod
    def try_json_load(f):
        """
        Tries to load a JSON file. Unlike json.loads an empty dict is returned if the file is empty.
        """
        if os.stat(f).st_size == 0:
            return {}
        else:
            with open(f, "r") as f:
                return json.load(f)

    @staticmethod
    def generate_build_list(builds):
        """
        Generates a string representation of a simple HTML page that displays a list
        of links to all builds. The builds parameter should be a list of commit SHAs.
        """
        head = "<!DOCTYPE html><html><head><title>List of CI builds</title></head>"
        body = "<body><ul><p>List of CI builds</p>"
        for build in builds:
            link = f"<li><a href='./{build}'>{build}</a></li>"
            body += link
        body += "</ul></body></html>"
        return head+body

    @staticmethod
    def generate_build_html_document(sha, build):
        """
        Generates the HTML page for a specific build
        """
        head = f"<!DOCTYPE html><html><head><title>CI build {sha}</title></head>"
        timestamp = build["timestamp"]
        message = build["message"]
        body = f"<body><p>Build: {sha}</p><p>Time: {timestamp}</p><p>Message: {message}</p></body></html>"
        return head+body

    @staticmethod
    def read_build(sha):
        """"
        Reads the specific build information for a certain commit SHA
        """
        CIServerHandler.ensure_builds_json_exists()
        return CIServerHandler.try_json_load(builds_filename).get(sha)
    
    @staticmethod
    def save_build(sha, message):
        """
        Saves the build message for a commit with the specified SHA to a file called builds.json
        If the file does not yet exist, it is created first.
        """
        CIServerHandler.ensure_builds_json_exists()
        builds_json = CIServerHandler.try_json_load(builds_filename)
        builds_json[sha] = {
            "message": message,
            "timestamp": datetime.now().strftime("%d/%m/%y %c")
        }
        os.remove(builds_filename)
        with open(builds_filename, "w+") as f:
            json.dump(builds_json, f, indent=4)

if __name__ == "__main__":   
    # Used https://pythonbasics.org/webserver/ as a base for the server
    if os.environ.get("CI_SERVER_AUTH_TOKEN") is None:
        print("Please set the CI_SERVER_AUTH_TOKEN enviroment variable before starting the server!")
    else:
        webServer = CIServer((hostName, serverPort), CIServerHandler)
        webServer.run()
