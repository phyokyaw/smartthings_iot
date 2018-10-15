#!/usr/bin/python

import thread
import time
import wiringpi
import socket
import time
from threading import Thread
from threading import Condition
from enum import Enum
import logging
from logging.handlers import RotatingFileHandler

DEVICE_STATUS_GPIO = 4
OPER_STATUS_GPIO = 5
RELAY_GPIO = 6
HEAT_BUTTON = 29

HOME_ROUTER_IP = "192.168.1.1"



path = "/var/log/thermostat.log"

# add a rotating handler
handler = RotatingFileHandler(path, maxBytes=1024*500, backupCount=5)
handler.setFormatter(logging.Formatter('%(asctime)s.%(msecs)03d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s', datefmt='%d/%m/%Y %H:%M:%S'))
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(handler)

def log():
  return logger

def initGpio():
  wiringpi.wiringPiSetup()
  wiringpi.pinMode(DEVICE_STATUS_GPIO, 1)
  wiringpi.pinMode(OPER_STATUS_GPIO, 1)
  wiringpi.pinMode(RELAY_GPIO, 1)
  wiringpi.pinMode(HEAT_BUTTON, 0)
  wiringpi.pullUpDnControl(HEAT_BUTTON, 2)

def setDeviceStatusToOn(on):
  wiringpi.digitalWrite(DEVICE_STATUS_GPIO, int(on == True))

def set_oper_status_to_on(on):
  wiringpi.digitalWrite(OPER_STATUS_GPIO, int(on == True))

class UpdateNetworkStatus(Thread):
  def __init__(self):
    Thread.__init__(self)
    self.daemon = True

  def run(self):
    while True:
      try:
        socket.gethostbyaddr(HOME_ROUTER_IP)
        setDeviceStatusToOn(True)
      except socket.error:
        setDeviceStatusToOn(False)
      time.sleep(5)

class OPER_STATE(Enum):
  RUNNING = 1
  OFF = 2
  ERROR = 3

def turn_on(on):
  set_state(OPER_STATE.RUNNING if on == True else OPER_STATE.OFF)
  wiringpi.digitalWrite(RELAY_GPIO, int(on == True))

def turn_error():
  set_state(OPER_STATE.ERROR)

def is_on():
  return wiringpi.digitalRead(RELAY_GPIO)

class RunErrorStatus(Thread):
  def __init__(self):
      Thread.__init__(self)
      self.daemon = True
      self.paused = True
      self.state = Condition()

  def run(self):
    self.resume() # unpause self
    oper_state = True
    while True:
      set_oper_status_to_on(oper_state)
      oper_state = not oper_state
      time.sleep(.5)

  def resume(self):
    with self.state:
      self.paused = False
      self.state.notify()  # unblock self if waiting

  def pause(self):
    with self.state:
      self.paused = True  # make self block and wait

def set_state(oper_state):
  RunErrorStatus().pause()
  if oper_state == OPER_STATE.RUNNING:
    set_oper_status_to_on(True)
  elif oper_state == OPER_STATE.OFF:
    set_oper_status_to_on(False)
  elif oper_state == OPER_STATE.ERROR:
    RunErrorStatus().run()

def main():
  initGpio()
  UpdateNetworkStatus().start()
  HeatButton.start()
  set_state(OPER_STATE.ERROR)

if __name__ == "__main__":
   main()
