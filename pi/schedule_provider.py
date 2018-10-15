#!/usr/bin/python

import json
from collections import namedtuple
from datetime import datetime
from datetime import timedelta
import bme280
import pi_status_light
from threading import Thread
import time
import os
import requests
import wiringpi
from requests.exceptions import ConnectionError
from requests.exceptions import Timeout
import logging
import feedparser
import requests
from io import BytesIO
import re

''' Uses https://bitbucket.org/MattHawkinsUK/rpispy-misc/raw/master/python/bme280.py '''

home_dir = '/home/pi'
file_path = os.path.join(home_dir, '.schedule.json')
smarthings_config_path = os.path.join(home_dir, '.smartthings.json')
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(pi_status_light.handler)
weather_area_code_didcot = '2651269'
weather_area_code_didcot_url = 'https://weather-broker-cdn.api.bbci.co.uk/en/forecast/rss/3day/' + weather_area_code_didcot

def load_config():
  with open(smarthings_config_path, 'r') as myfile:
    return json.loads(myfile.read().translate(None, ' \n\t\r'))

def load_data():
  with open(file_path, 'r') as myfile:
    return json.loads(myfile.read().translate(None, ' \n\t\r'))

def write_json_data(data):
  with open(file_path, 'w') as myfile:
    # print data
    myfile.write(json.dumps(data, sort_keys=True, indent=2, separators=(',', ': ')))

def write_mode(mode):
  data = load_data()
  y = json.loads(mode)
  data['state']['thermostatMode'] = y['thermostatMode']
  data['state']['setDate'] = datetime.now().strftime('%b-%d-%Y_%H:%M')
  data['state']['heatingSetpoint'] = y['heatingSetpoint']
  logger.debug("Received mode update " + data['state']['thermostatMode'])
  logger.debug("Received heatingSetpoint update " + str(data['state']['heatingSetpoint']))
  write_json_data(data)


def write_schedule(schedule):
  data = load_data()
  schedule_data = json.loads(schedule)
  data['daysOfWeek'] = schedule_data['daysOfWeek']
  data['minimun_temp'] = schedule_data['minimun_temp']
  data['offset_temp'] = schedule_data['offset_temp']
  data['temp_on_offset'] = schedule_data['temp_on_offset']
  logger.debug("Received schedule and minimun_temp update")
  write_json_data(data)

def load_state():
  data = load_data()
  # Parse JSON into an object with attributes corresponding to dict keys.
  # x = json.loads(data, object_hook=lambda d: namedtuple('X', d.keys())(*d.values()))
  thermostatOperatingState = 'heating' if pi_status_light.is_on() == 1 else 'idle'
  temperature,pressure,humidity = getDataValue(data['offset_temp'])
  return json.dumps(
      {
          'temperature': temperature, 
          'pressure': pressure, 
          'humidity': humidity, 
          'thermostatOperatingState': thermostatOperatingState,
          'thermostatMode': data['state']['thermostatMode'],
          'setDate': data['state']['setDate'],
          'heatingSetpoint': data['state']['heatingSetpoint'],
          'weather': 
          {
            'today': data['weather']['today'],
            'tomorrow': data['weather']['tomorrow'],
            'day2': data['weather']['day2']
          }
      })

def update_mode(now, currentTemp, currentWeatherData, data):
  report_required = False
  s_temp = get_temp(now, data)
  if data['state']['thermostatMode'] == 'turning_heat':
    data['state']['thermostatMode'] = 'heat'
    report_required = True
  elif  data['state']['thermostatMode'] == 'turning_auto':
    data['state']['thermostatMode'] = 'auto'
    report_required = True
  elif  data['state']['thermostatMode'] == 'turning_off':
    data['state']['thermostatMode'] = 'off'
    report_required = True
  if data['state']['thermostatMode'] == 'heat' and data['state']['heatingSetpoint'] < currentTemp - data['temp_on_offset']:
    data['state']['thermostatMode'] = 'auto'
    data['state']['setDate'] = now.strftime('%b-%d-%Y_%H:%M')
    data['state']['heatingSetpoint'] = currentTemp if currentTemp > s_temp else s_temp
    logger.debug("Switching back to auto from heat "+ str(data['state']['heatingSetpoint']))
    report_required = True
  elif data['state']['thermostatMode'] == 'auto' and pi_status_light.is_on() == 1 and data['state']['heatingSetpoint'] != s_temp:
    data['state']['heatingSetpoint'] = s_temp
    logger.debug("Updating auto temperature: " + str(data['state']['heatingSetpoint']))
    report_required = True
  if abs(data['recorded_temp'] - currentTemp) > 0.3:
    data['recorded_temp'] = currentTemp
    logger.debug("Update temperature to " + str(currentTemp))
    report_required = True
  if currentWeatherData is not None:
    data['weather']['today'] = currentWeatherData[0]
    data['weather']['tomorrow'] = currentWeatherData[1]
    data['weather']['day2'] = currentWeatherData[2]
    report_required = True
  if (report_required):
      logger.debug("Update mode to " + str(data['state']['thermostatMode']))
      logger.debug("Update heatingSetpoint to " + str(data['state']['heatingSetpoint']))
      write_json_data(data)
  return report_required

def get_temp(now, data):
  now_time = now.time()
  for time in data['daysOfWeek'][0 if datetime.today().weekday() < 5 else 1]['hour']:
      start = datetime.strptime(time['s'], '%H:%M').time()
      end = datetime.strptime(time['e'], '%H:%M').time()
      if in_between(now_time, start, end):
        return time['t']
  return data['minimun_temp']

def should_be_on(now, currentTemp, data):
  # Parse JSON into an object with attributes corresponding to dict keys.
  # x = json.loads(data, object_hook=lambda d: namedtuple('X', d.keys())(*d.values()))

  if data['state']['thermostatMode'] == 'heat':
    # check heat on
    return True

  if data['state']['thermostatMode'] == 'off':
    return False

  if data['state']['thermostatMode'] == 'auto':
    if pi_status_light.is_on():
      currentTemp = currentTemp - data['temp_on_offset']
    return True if get_temp(now, data) > currentTemp else False

  # Lower than min temp set
  return data['minimun_temp'] > currentTemp

def report_update():
  logger.debug("Pushing changes to smartthings")
  try:
    config = load_config()
    response = requests.put("https://%s%s" % (config['host'], config['endpoint_url']),
      data=load_state(),
      headers=
        {'content-type':'application/json', 
        'Authorization':"Bearer %s" % config['access_token']},
      timeout=1.0)
    logger.debug("Got status " + str(response.status_code))
  except ConnectionError as e:    # This is the correct syntax
    logger.error("Connection error")
  except Timeout as e:    # This is the correct syntax
    logger.error("Connection timeout")

def in_between(now, start, end):
  if start <= end:
    return start <= now < end
  else: # over midnight e.g., 23:30-04:15
    return start <= now or now < end

class Control(Thread):
  def __init__(self):
    Thread.__init__(self)
    self.daemon = True

  def run(self):
    lastWeatherDownload = None
    weatherData = None
    while True:
      try:
        report_required = False
        logger.debug("reading schedule data from file")
        data = load_data()
        logger.debug("reading temp values from device")
        temperature,pressure,humidity = getDataValue(data['offset_temp'])
        now = datetime.now()
        if lastWeatherDownload is None:
          weatherData = get_weather()
          lastWeatherDownload = now
        else:
          if now > lastWeatherDownload + timedelta(minutes=1):
            lastWeatherDownload = now
            weatherData = get_weather()
          else:
            weatherData = None
        logger.debug("update mode and write data")
        report_required = update_mode(now, temperature, weatherData, data)
        if should_be_on(now, temperature, data):
          if pi_status_light.is_on() != 1:
            logger.debug("trying to turn on")
            pi_status_light.turn_on(True)
            report_required = True
        else:
          if pi_status_light.is_on() == 1:
            logger.debug("trying to turn off")
            pi_status_light.turn_on(False)
            report_required = True
        if report_required:
          logger.debug("reporting back to smartthings")
          report_update()
      except Exception as e:
        logger.error(e)
        pi_status_light.turn_error()

      time.sleep(5)

class HeatButton(Thread):
  def __init__(self):
    Thread.__init__(self)
    self.daemon = True

  def run(self):
    while True:
      if (wiringpi.digitalRead(pi_status_light.HEAT_BUTTON) == 1):
        time.sleep(3)
        if pi_status_light.is_on() != 1:
          data = load_data()
          data['state']['thermostatMode'] = 'turning_heat'
          data['state']['setDate'] = datetime.now().strftime('%b-%d-%Y_%H:%M')
          data['state']['heatingSetpoint'] = 21.0
          write_json_data(data)
          report_update()
      else:
        time.sleep(0.2)

def getDataValue(offset):
  temperature,pressure,humidity = bme280.readBME280All()
  temperature = temperature + offset
  return temperature,pressure,humidity

def parse_weather(data):
  temp = {}
  match = re.compile(":(.*?),").search(data)
  if match:
    temp['summary'] = match.group(1)
  match = re.compile("Minimum Temperature:\s*(-?\d+)").search(data)
  if match:
    temp['min'] = match.group(1)
  match = re.compile("Maximum Temperature:\s*(-?\d+)").search(data)
  if match:
    temp['max'] = match.group(1)
  return temp

def get_weather():
  try:
    resp = requests.get(weather_area_code_didcot_url, timeout=20.0)
    # Put it to memory stream object universal feedparser
    content = BytesIO(resp.content)
    # Parse content
    weather_data = feedparser.parse(content)
    logger.debug("Got weather data")
    today = parse_weather(weather_data['entries'][0]['title'])
    tomorrow = parse_weather(weather_data['entries'][1]['title'])
    twoday = parse_weather(weather_data['entries'][2]['title'])
    return today, tomorrow, twoday
  except Exception as e:
    logger.error("Error getting weather update: " + e.message)
    return None

def main():
  pi_status_light.initGpio()
  try:
    t = Control()
    t.start()
    while t.isAlive(): 
      t.join(1)  # not sure if there is an appreciable cost to this.
  except (KeyboardInterrupt, SystemExit):
    logger.error('Received keyboard interrupt, quitting threads')

if __name__=="__main__":
  main()