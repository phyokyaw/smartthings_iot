#!/usr/bin/python

import SimpleHTTPServer
import SocketServer
import json
import schedule_provider
import pi_status_light
import logging

PORT = 8090
LOW_RANGE = 30
UP_RANGE = 100

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)
logger.addHandler(pi_status_light.handler)

class RequestHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        if self.path == "/value":
            state = schedule_provider.load_state()
            logger.debug("Received value request responding with: " + state)
            self.wfile.write(data = state)
        else:
            self.send_response(400, 'Bad Request: invalid path')
    def do_PUT(self):
        if self.path == "/schedule":
            length = int(self.headers['Content-Length'])
            content = self.rfile.read(length)
            if (isValid(content)):
                schedule_provider.write_schedule(content)
                self.send_response(204)
                self.end_headers()
            else:
                self.send_response(400, 'Bad Request: invalid value')
        elif self.path == "/mode":
            length = int(self.headers['Content-Length'])
            content = self.rfile.read(length)
            if (isValid(content)):
                schedule_provider.write_mode(content)
                self.send_response(204)
                self.end_headers()
            else:
                self.send_response(400, 'Bad Request: invalid value')
        else:
            self.send_response(400, 'Bad Request: invalid path')

def isValid(s):
    return True

httpd = SocketServer.TCPServer(("", PORT), RequestHandler)

pi_status_light.initGpio()
pi_status_light.UpdateNetworkStatus().start()
schedule_provider.HeatButton().start()
schedule_provider.Control().start()

logger.debug("Starting server")
httpd.serve_forever()
