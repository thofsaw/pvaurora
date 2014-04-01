#!/usr/bin/env python
# encoding: utf-8
'''
pvaurora -- Aurora power inverter uploader to pvoutput.org

pvaurora is a script for grabbing Aurora series power inverter
data, via external command, and uploading to pvoutput.org account

@author:     Yuri Valentini

@copyright:  2013 Yuri Valentini. All rights reserved.

@license:    GNU GENERAL PUBLIC LICENSE v3

@contact:    yv@opycom.it
'''

import argparse
import datetime
import logging
import os
import httplib
import urllib
import subprocess
import sys

import config
import timezone
import sun

__all__ = []
__version__ = '0.1.0'
__date__ = '2014-03-26'
__updated__ = '2014-03-26'

DEBUG = 1

class PowerValue(object):
    '''Power value for strings and grid'''
    def __init__(self, voltage, current, power):
        '''Constructor
        
        Args:
            voltage (float): voltage in V
            current (float): current in A
            power (float): power in W
        '''
        self._voltage = voltage
        self._current = current
        self._power = power

    @property
    def voltage(self):
        return self._voltage
    @property
    def current(self):
        return self._current
    @property
    def power(self):
        return self._power

    def __str__(self):
        return "%.1fV %.1fA %.1fW" % (self._voltage, self._current, self._power)

class InverterMeasurement(object):
    '''Inverter measurement value'''
    def __init__(self, dt, str1_power, str2_power, grid_power, grid_freq, dc_ac_eff, inv_temp, env_temp, daily_energy):
        '''Constructor
        
        Args:
            dt (datetime.datetime): date and time of measurement
            str1_power (PowerValue): pv string 1 power value
            str2_power (PowerValue): pv string 2 power value
            grid_power (PowerValue): grid power value
            grid_freq (float): grid frequency in Hz
            dc_ac_eff (float): DC-AC efficiency in conversion (0.0-1.0)
            inv_temp (float): inverter temperature in C
            env_temp (float): booster temperature in C
            daily_energy (float): dayily energy production in Wh
        '''
        self._dt = dt
        self._str1_power = str1_power
        self._str2_power = str2_power
        self._grid_power = grid_power
        self._grid_freq = grid_freq
        self._dc_ac_eff = dc_ac_eff
        self._inv_temp = inv_temp
        self._env_temp = env_temp
        self._daily_energy = daily_energy
    
    @property
    def dt(self):
        return self._dt
    @property
    def str1_power(self):
        return self._str1_power
    @property
    def str2_power(self):
        return self._str2_power
    @property
    def grid_power(self):
        return self._grid_power
    @property
    def grid_freq(self):
        return self._grid_freq
    @property
    def dc_ac_eff(self):
        return self._dc_ac_eff
    @property
    def inv_temp(self):
        return self._inv_temp
    @property
    def env_temp(self):
        return self._env_temp
    @property
    def daily_energy(self):
        return self._daily_energy

    def __str__(self):
        return "%s S1(%s) S2(%s) G(%s %.1fHz) eff=%.1f%% inv=%.1f°C env=%.1f°C daily=%.0fWh" % (
            self._dt, self._str1_power, self._str2_power, self._grid_power, self._grid_freq,
            self._dc_ac_eff * 100.0, self._inv_temp, self._env_temp, self._daily_energy)

class PvOutputApi(object):
    '''pvoutput.org API access'''
    def __init__(self, api_key, system_id):
        '''Constructor
        
        Args:
            api_key (str): API key
            system_id (int): system id
        '''
        self._api_key = api_key
        self._system_id = system_id
    
    def add_status(self, dt, daily_energy, power, temperature, voltage):
        '''Add status api
        
        Args:
            dt (datetime): date and time
            daily_energy (float): produced energy from start of the day in Wh
            power (float): output power in W
            temperature (float): inverter temperature in C
            voltage (float): output voltage in V
            
        Returns:
            bool:
                True -- success
                False -- failure
        '''
        host = "pvoutput.org"
        service = "/service/r2/addstatus.jsp"
        data = { 'd' : dt.strftime("%Y%m%d"),
            't' : dt.strftime("%H:%M"),
            'v1' : daily_energy,
            'v2' : power,
            'v5' : temperature,
            'v6' : voltage }
        params = urllib.urlencode(data)
        headers = { "Content-type" : "application/x-www-form-urlencoded",
               "Accept" : "text/plain",
               "X-Pvoutput-SystemId" : self._system_id,
               "X-Pvoutput-Apikey" : self._api_key }
        logging.info("Connecting to %s" % host)
        conn = httplib.HTTPConnection(host)
        logging.info("sending: %s" % params)
        conn.request("POST", service, params, headers)
        response = conn.getresponse()
        if response.status != 200:
            logging.info("POST failed: %d %s" % (response.status, response.reason))
            return False
        logging.info("POST ok: %d %s" % (response.status, response.reason))
        return True


class AuroraRunner(object):
    '''Manages data from aurora command'''
    def get_status(self, cmdline):
        '''Executes aurora command and captures output
        
        Args:
            cmdline (str): command line to execute (must specify -c -d0 -e)

        Returns:
            str:
                output line if success
                "" if failure
        '''
        proc = subprocess.Popen(cmdline, stdout=subprocess.PIPE)
        out = proc.communicate()[0]
        if proc.returncode != 0:
            return ""
        return out
    
    def decode_status(self, dt, line):
        '''Decodes a status line obtained by get_status()
        
        Args:
            dt (datetime.datetime): date and time of acquisition 
            line (str): output line obtained by get_status()
            
        Returns:
            InverterMeasurement:
                value if success
                None if failure
        '''
        elems = line.split()
        if len(elems) != 21:
            return None
        if elems[-1] != "OK":
            return None
        values = [float(i) for i in elems[:-1]]
        str1_power = PowerValue(values[0], values[1], values[2])
        str2_power = PowerValue(values[3], values[4], values[5])
        grid_power = PowerValue(values[6], values[7], values[8])
        grid_freq = values[9]
        dc_ac_eff = values[10] / 100.0
        inv_temp = values[11]
        env_temp = values[12]
        daily_energy = values[13] * 1000.0
        return InverterMeasurement(dt, str1_power, str2_power, grid_power, grid_freq, dc_ac_eff, inv_temp, env_temp, daily_energy)


class CLIError(Exception):
    '''Generic exception to raise and log different fatal errors.'''
    def __init__(self, msg):
        super(CLIError).__init__(type(self))
        self.msg = "E: %s" % msg
    def __str__(self):
        return self.msg
    def __unicode__(self):
        return self.msg

def replace_tz_datetime(dt, t):
    return dt.replace(hour=t.hour, minute=t.minute, second=t.second, microsecond=t.microsecond)
    
def is_daylight(dt, latitude, longitude, delta):
    '''Determines if time is daylight or night time
        Args:
            dt (datetime.datetime): date and time of observation 
            latitude (float): latitude of observation
            longitude (float): longitude of observation
            delta (datetime.timedelta): time before sunrise and after sunset to extend daylight range
            
        Returns:
            bool:
                True: is daylight time
                False: is night time
    '''
    local_sun = sun.sun(latitude, longitude)
    sunrise = local_sun.sunrise(dt)
    sunset = local_sun.sunset(dt)
    delta = datetime.timedelta(minutes=delta)
    logging.info("Sunrise: %s" % sunrise)
    logging.info("Sunset : %s" % sunset)
    logging.info("Delta  : %s" % delta)
    sunrise_dt = replace_tz_datetime(dt, sunrise)
    sunset_dt = replace_tz_datetime(dt, sunset)
    daylight = sunrise_dt <= dt <= sunset_dt
    if daylight:
        logging.info("Daylight time")
    else:
        logging.info("Night time")
    return daylight 
    
def main():
    '''Command line options.'''
    program_name = os.path.basename(sys.argv[0])
    program_version = "v%s" % __version__
    program_build_date = str(__updated__)
    program_version_message = '%%(prog)s %s (%s)' % (program_version, program_build_date)
    program_shortdesc = __import__('__main__').__doc__.split("\n")[1]
    program_license = '''%s

  Created by Yuri Valentini on %s.
  Copyright 2014 Yuri Valentini. All rights reserved.

  Licensed under the GNU GENERAL PUBLIC LICENSE v3
  https://www.gnu.org/copyleft/gpl.html

  Distributed on an "AS IS" basis without warranties
  or conditions of any kind, either express or implied.

USAGE
''' % (program_shortdesc, str(__date__))

    try:
        # Setup argument parser
        parser = argparse.ArgumentParser(description=program_license, formatter_class=argparse.RawDescriptionHelpFormatter)
        parser.add_argument("-c", "--command", dest="command", metavar="CMD", required=True,
                            help="command to capture data from power inverter")
        parser.add_argument("-a", "--api-key", dest="api_key", metavar="KEY", required=True,
                            help="API key to access pvoutput.org services")
        parser.add_argument("-i1", "--system-id-primary", dest="system_id1", metavar="SID", required=True,
                            help="primary system id on pvoutput.org where to store first pv string data")
        parser.add_argument("-i2", "--system-id-secondary", dest="system_id2", metavar="SID",
                            help="secondary system id on pvoutput.org where to store second pv string data")
        parser.add_argument("-m", "--minutes_delta", dest="delta", metavar="NUM", default="3600", type=int,
                            help="executes if current time is %(metavar)s minutes before sunrise and %(metavar)s minutes after sunset [default: %(default)s]")
        parser.add_argument("--latitude", dest="latitude", metavar="LAT", type=float,
                            help="latitude for sunrise and sunset calculation")
        parser.add_argument("--longitude", dest="longitude", metavar="LON", type=float,
                            help="longitude for sunrise and sunset calculation")
        parser.add_argument("-v", "--verbose", dest="verbose", action="count", help="set verbosity level [default: %(default)s]")
        parser.add_argument('-V', '--version', action='version', version=program_version_message)
        
        # Process arguments
        args = parser.parse_args()

        if args.verbose > 0:
            logging.basicConfig(level=logging.INFO)

        if (args.longitude and not args.latitude) or (not args.longitude and args.latitude): 
            raise CLIError("you must specify both latitude and longitude to enable execution between sunset-sunrise or none to disable")
        
        now = datetime.datetime.now(tz=timezone.LocalTimezone())
        logging.info("Date   : %s" % now.date())
        logging.info("Time   : %s" % now.time())
            
        if args.latitude and args.longitude:
            if not is_daylight(now, float(args.latitude), float(args.longitude), int(args.delta)):
                logging.info("Not daylight time: exiting")
                return 0
                 
        #api = PvOutputApi(args.api_key, int(args.system_id1))
        #api.add_status(now, 12000.0, 1800.0, 30.0, 200.0, True)
        return 0
    except KeyboardInterrupt:
        ### handle keyboard interrupt ###
        return 0
#     except Exception, e:
#         if DEBUG:
#             raise(e)
#         indent = len(program_name) * " "
#         sys.stderr.write(program_name + ": " + repr(e) + "\n")
#         sys.stderr.write(indent + "  for help use --help")
#         return 2

if __name__ == "__main__":
    if DEBUG:
        #m = aurora.decode_status(datetime.datetime.now(tz=timezone.LocalTimezone()), line)
        sys.argv.append("-v") # verbose
        sys.argv.extend(["-m", "60", "--latitude", str(config.LATITUDE), "--longitude", str(config.LOGITUDE)]) # sunrise sunset
        sys.argv.extend(["-c", "/aurora -a 2 -c -d0 -e -P 400 -Y 20 -W /dev/ttyUSB0"])
        sys.argv.extend(["-a", config.API_KEY])
        sys.argv.extend(["-i1", str(config.SYSTEM_ID1)])
        sys.argv.extend(["-i2", str(config.SYSTEM_ID2)])
    sys.exit(main())