import os, shutil, tempfile, pygit2, src.server
from threading import Thread
from requests import post
from time import sleep

def create_repo_with_files_and_commit(repo_path, files_added):
    """
    Initializes a git repo in repo_path and copies a file with path file_added
    to the newly initialized repo, creates a commit, then returns the repo.
    """
    # Add test file
    for file in files_added:
        shutil.copy(file, repo_path)

    # Create repo
    repo = pygit2.init_repository(repo_path, initial_head="main", bare=False)

    # Stage
    index = repo.index
    index.add_all()
    index.write()

    # Prepare to commit
    ref = "HEAD"
    author = pygit2.Signature("Pytest", "pytest@example.com")
    committer = pygit2.Signature("Pytest", "pytest@example.com")
    message = "Pytest commit message"
    tree = index.write_tree()
    parents = []

    # Commit
    repo.create_commit(ref, author, committer, message, tree, parents)
    return repo

def test_compile_valid_file(capsys):
    """
    Tests that the server correctly clones a remote repository, runs syntax checking
    and detects no errors for a project consisting of a single valid Python file.
    """
    web_server = src.server.CIServer((src.server.hostName, src.server.serverPort), src.server.CIServerHandler)
    thread = Thread(target = web_server.run, args = ()) # Thread writes to stdout
    thread.start()

    # Create repo and commit
    with tempfile.TemporaryDirectory() as local_repo_path:
        _ = create_repo_with_files_and_commit(local_repo_path, [os.path.join(".", "src", "test", "valid_files", "hello_world.py")])
        post_data = {
            "repository": {
                "clone_url": local_repo_path
            },
            "ref": "refs/heads/main"
        }
        r = post("http://localhost:"+str(src.server.serverPort), json=post_data)

    web_server.shutdown()

    out, _ = capsys.readouterr()
    assert "OK: hello_world.py\nAll source files checked: 0 syntax errors\n" in out

def test_compile_invalid_file(capsys):
    """
    Tests that the server correctly clones a remote repository, runs syntax checking
    and detects an error for a project consisting of a single invalid Python file.
    """
    web_server = src.server.CIServer((src.server.hostName, src.server.serverPort), src.server.CIServerHandler)
    thread = Thread(target = web_server.run, args = ()) # Thread writes to stdout
    thread.start()

    # Create repo and commit
    with tempfile.TemporaryDirectory() as local_repo_path:
        _ = create_repo_with_files_and_commit(local_repo_path, [os.path.join(".", "src", "test", "invalid_files", "hello_world_invalid.py")])
        post_data = {
            "repository": {
                "clone_url": local_repo_path
            },
            "ref": "refs/heads/main"
        }
        r = post("http://localhost:"+str(src.server.serverPort), json=post_data)

    web_server.shutdown()

    out, _ = capsys.readouterr()
    assert "ERR: hello_world_invalid.py\nAll source files checked: 1 syntax errors\n" in out

def test_run_pytest_passing_tests(capsys):
    """
    Tests that the server correctly clones a remote repository, runs syntax checking and runs Pytest.
    As the repository contains a single valid file and test, and they are correctly implemented,
    all tests should pass and no syntax errors should be detected.
    """
    web_server = src.server.CIServer((src.server.hostName, src.server.serverPort), src.server.CIServerHandler)
    thread = Thread(target = web_server.run, args = ()) # Thread writes to stdout
    thread.start()

    # Create repo and commit
    with tempfile.TemporaryDirectory() as local_repo_path:
        _ = create_repo_with_files_and_commit(local_repo_path, [os.path.join(".", "src", "test", "valid_files", "add.py"), os.path.join(".", "src", "test", "valid_files", "test_add.py")])
        post_data = {
            "repository": {
                "clone_url": local_repo_path
            },
            "ref": "refs/heads/main"
        }
        r = post("http://localhost:"+str(src.server.serverPort), json=post_data)

    web_server.shutdown()

    out, _ = capsys.readouterr()
    assert "OK: add.py\nOK: test_add.py\nAll source files checked: 0 syntax errors\n" in out
    assert "All pytest tests were successful!" in out

def test_run_pytest_failing_tests(capsys):
    """
    Tests that the server correctly clones a remote repository, runs syntax checking and runs Pytest.
    As the repository contains a single valid file and test, and add is incorrectly implemented,
    the test should fail. No syntax errors should be detected.
    """
    web_server = src.server.CIServer((src.server.hostName, src.server.serverPort), src.server.CIServerHandler)
    thread = Thread(target = web_server.run, args = ()) # Thread writes to stdout
    thread.start()

    # Create repo and commit
    with tempfile.TemporaryDirectory() as local_repo_path:
        _ = create_repo_with_files_and_commit(local_repo_path, [os.path.join(".", "src", "test", "invalid_files", "invalid_add.py"), os.path.join(".", "src", "test", "invalid_files", "test_invalid_add.py")])
        post_data = {
            "repository": {
                "clone_url": local_repo_path
            },
            "ref": "refs/heads/main"
        }
        r = post("http://localhost:"+str(src.server.serverPort), json=post_data)

    web_server.shutdown()

    out, _ = capsys.readouterr()
    assert "OK: invalid_add.py\nOK: test_invalid_add.py\nAll source files checked: 0 syntax errors\n" in out
    assert "Some pytest error or failed test occurred." in out
