# dd2480-ci-server
## Summary
This is a small CI server for python projects. It will be triggered as a GitHub webhook on **push events** only. When a push has been delivered to the server, it will try to parse all python files to detect syntax errors. Then, it will use `pytest` to run all test files. It will then set a GitHub commit status on the relevant commit. If there are syntax errors, the status will be `failure`. If there are no tests or at least one test fails, the status will be `error`. Otherwise, if all tests succeeds, it will be `success`.

## Running the project
To run the server, make sure to install all required dependencies with `pip install -r requirements.txt`. In order for the commit statuses to be set, the machine running the server needs to have a valid GitHub Personal Access Token with access rights to `repo:status` saved in an environment variable called `CI_SERVER_AUTH_TOKEN`. Then, start the server with `python src/server.py`. 

## Browsable documentation
To create HTML documentation from the docstrings, navigate to the `docs` directory and run `make html`. The documentation can be accessed by opening the `index.html` file that is created in the `docs/build` directory.

## Implementation and testing
### P1: Compilation
**Implementation:**
Since Python doesn't require compilation, we implemented a static syntax check for all python files. This is done by cloning the repo to a temporary directory and checking out the branch that was pushed to, and then recursively iterating through the git tree to check all python files and returning the amount of syntax errors that were found. The implementation will ignore any folders named `test`. This is because the server was tested on itself and our test folder contains some files that were created with syntax errors in order to check that the syntax check works as intended. In other projects, files in test folders will probably be run in some other way (e.g. with `Pytest`) and therefore syntax errors might be detected when running them. 

**Testing:** 
One unit test will create a local repo with a subdirectory called `test` that contains files with syntax errors and assert that the method that performs the syntax check doesn't find any syntax errors. Two other unit tests will create a local repo with a commit that contains one python file that is syntactically correct and one that is incorrect, respectively, start a local webserver, send a small POST request that simulates the one you would get from GitHub, and assert that the webserver prints the expected output to stdout.

### P2: Running tests
**Implementation:**
To implement the testing feature, the server will simply move into the newly cloned repo and invoke `pytest` to run all tests. Since we tested the server on itself, we had to add a `pytest.ini` file that ignores the files we created for tests (in `test/invalid_files` and `test/valid_files`). Then we use the exit code from `pytest` to determine the outcome of the test run. 

**Testing:** 
Our tests for running tests are similar to our tests for syntax checking. We create a local repo with some tests that will succeed (which can be found in `test/valid_files`) and some that will fail (in `test/invalid_files`) and create a local webserver that we send a POST request to, same as we did with the syntax checking. Then we assert that the server prints the expected output. 

### P3: Build results
**Implementation:**
We implemented the notification of CI results as GitHub commit statuses. This was implemented by parsing the relevant fields from the POST data sent to the webhook and using it to create a status with `PyGithub`'s method, which sends a POST request to the relevant URL. In order to do this, the machine running the server needs to use an authentication token from GitHub (with the proper access rights to the repo, as mentioned above), which needs to be stored in an environment variable called `CI_SERVER_AUTH_TOKEN`. 

**Testing:** 
We implemented a unit test that will set the commit status of a specific commit in our repo (hard-coded) with a context message that says that it's a test and contains a random 32-bit number. Then, all statuses on that commit are fetched, and if there is a status with the correct state and context message, the test will pass. Othwerwise, it fails. 

## P+ implementation
We implemented build history by creating a JSON file that stores a JSON object for every build. The information stored is the commit SHA (which is the key for each build object), a timestamp, and a message describing the build (containing the commit status and its description). When visiting the address at which the server is hosted (i.e. doing a GET request to the base address), it will generate an HTML page listing all the builds in the JSON file, with clickable links that will generate a HTML page for the specific build by reading the JSON file.

## Contributions
Most tasks were done by several group members working together. Edit and Erik worked on implementing a basic server, which was roughly the equivalent of the Java code skeleton that was provided. Edit and Elias implemented the syntax checking and P+ part. The entire group worked together on implementing the testing functionality and commit status setting. 

## Essence
