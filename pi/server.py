#!/usr/bin/python

import SimpleHTTPServer
import SocketServer
import json
import bme280

''' Uses https://bitbucket.org/MattHawkinsUK/rpispy-misc/raw/master/python/bme280.py '''

PORT = 8090

def readValueFromBme280():
    temperature,pressure,humidity = bme280.readBME280All()
    return json.dumps({'temperature': temperature, 'pressure': pressure, 'humidity': humidity})

class RequestHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/value":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(readValueFromBme280())
        else:
            self.send_response(400, 'Bad Request: record does not exist')

httpd = SocketServer.TCPServer(("", PORT), RequestHandler)

print "Serving at port", PORT
httpd.serve_forever()