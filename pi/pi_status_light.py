#!/usr/bin/python

import thread
import time
import wiringpi
import socket
import time
from threading import Thread

DEVICE_STATUS_GPIO = 4
HOME_ROUTER_IP = "192.168.1.1"

def initGpio():
  wiringpi.wiringPiSetup()
  wiringpi.pinMode(DEVICE_STATUS_GPIO, 1)

def setDeviceStatusToOn(on):
  wiringpi.digitalWrite(DEVICE_STATUS_GPIO, int(on == True))

class checkDeviceStatus(Thread):
  def run(self):
    while True:
      try:
        socket.gethostbyaddr(HOME_ROUTER_IP)
        setDeviceStatusToOn(True)
      except socket.herror:
        setDeviceStatusToOn(False)
      time.sleep(5)

def main():
  initGpio()
  checkDeviceStatus().start()

if __name__ == "__main__":
   main()
