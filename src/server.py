from http.server import BaseHTTPRequestHandler, HTTPServer

hostName = "localhost"
serverPort = 8080

class CIServer(BaseHTTPRequestHandler):
    def do_POST(self):
        """
        This is the main method for the CI server since GitHub delivers webhooks via POST. 
        """
        # Send response code & headers
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

        # Do CI stuff here
        # Clone repo, do syntax check etc.

        # Send response data
        self.wfile.write(bytes("CI jobs done!", "utf-8"))

    def do_GET(self):
        """
        Responds to a GET request by writing to the console (so you can test the server by visiting localhost)
        """
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

        print("Connection!")

if __name__ == "__main__":   
    # Used https://pythonbasics.org/webserver/ as a base for the server     
    webServer = HTTPServer((hostName, serverPort), CIServer)
    print("Server started.")

    try:
        webServer.serve_forever()
    except KeyboardInterrupt:
        pass

    webServer.server_close()
    print("Server stopped.")