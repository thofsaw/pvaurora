#!/usr/bin/env python
# encoding: utf-8
'''
pvaurora -- Aurora power inverter uploader to pvoutput.org

pvaurora is a script for grabbing Aurora series power inverter
data, via external command, and uploading to pvoutput.org account

@author:     Yuri Valentini, Paul Phillips

@copyright:  2013 Yuri Valentini, 2021 Paul Phillips All rights reserved.

@license:    GNU GENERAL PUBLIC LICENSE v3

@contact:    yv@opycom.it, paul at hochikawa dot com
'''

import click
import requests
import datetime
import logging
import os

import urllib
import subprocess
import sys

import timezone
import sun

'''
legacy imports
'''
# import argparse
# import httplib

__all__ = []
__version__ = '0.1.1'
__date__ = '2014-03-26'
__updated__ = '2014-03-26'

DEBUG = 1


class PowerValue(object):
    """Power value for strings and grid"""

    def __init__(self, voltage, current, power):
        """Constructor

        Args:
            voltage (float): voltage in V
            current (float): current in A
            power (float): power in W
        """
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
    """Inverter measurement value"""

    def __init__(self, dt, str1_power, str2_power, grid_power, grid_freq, dc_ac_eff, inv_temp, env_temp, daily_energy):
        """Constructor

        Args:
            dt (datetime.datetime): date and time of measurement
            str1_power (PowerValue): pv string 1 power value
            str2_power (PowerValue): pv string 2 power value
            grid_power (PowerValue): grid power value
            grid_freq (float): grid frequency in Hz
            dc_ac_eff (float): DC-AC efficiency in conversion (0.0-1.0)
            inv_temp (float): inverter temperature in C
            env_temp (float): booster temperature in C
            daily_energy (float): daily energy production in Wh
        """
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


class Endpoints:
    API_BASE = "https://pvoutput.org"
    ADD_STATUS = "/service/r2/addstatus.jsp"


class PvOutputApi(object):
    """pvoutput.org API access"""

    headers = {"Content-type": "application/x-www-form-urlencoded",
               "Accept": "text/plain"}

    def __init__(self, api_key, system_id):
        """
        Constructor

        Args:
            api_key (str): API key
            system_id (int): system id
        """
        self.headers["X-Pvoutput-SystemId"] = str(system_id)
        self.headers["X-Pvoutput-Apikey"] = str(api_key)

    def _post(self, endpoint, params):
        """
        Sends a POST API call to the requested endpoint with parameters

        Args:
            endpoint (str): the API endpoint (without API URL prefix)
            params (dict): dictionary containing all the data to send

        Returns: API response dictionary
        """
        endpoint = Endpoints.API_BASE + endpoint
        response = requests.post(endpoint,
                                 headers=self.headers,
                                 params=params)
        return response

    def add_status(self, dt, daily_energy, power):
        """Add status api

        Args:
            dt (datetime): date and time
            daily_energy (float): produced energy from start of the day in Wh
            power (float): output power in W

        Returns:
            bool:
                True -- success
                False -- failure
        """
        params = {'d': dt.strftime("%Y%m%d"),
                  't': dt.strftime("%H:%M"),
                  'v1': daily_energy,
                  'v2': power
                  }

        logging.info("Sending: %s" % params)
        response = self._post(Endpoints.ADD_STATUS, params)
        logging.info(response.url)
        if response.status_code != 200:
            logging.info("POST failed: %d %s" % (response.status_code, response.reason))
            return False
        logging.info("POST ok: %d %s" % (response.status_code, response.reason))
        return True


class AuroraRunner(object):
    """Manages data from aurora command"""

    def get_status(self, cmdline):
        """
        Executes aurora command and captures output

        Args:
            cmdline (str): command line to execute (must specify -c -d0 -e)

        Returns:
            str:
                output line if success
                "" if failure
        """
        logging.info("Executing '%s'" % cmdline)
        proc = subprocess.Popen(cmdline.split(), stdout=subprocess.PIPE)
        out = proc.communicate()[0]
        logging.info("Return code = %d" % proc.returncode)
        logging.info("Output '%s'" % out)
        if proc.returncode != 0:
            return ""
        return out


    def decode_status(self, dt, line):
        """
        Decodes a status line obtained by get_status()

        Args:
            dt (datetime.datetime): date and time of acquisition
            line (str): output line obtained by get_status()

        Returns:
            InverterMeasurement:
                value if success
                None if failure
        """
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
        return InverterMeasurement(dt, str1_power, str2_power, grid_power, grid_freq, dc_ac_eff, inv_temp, env_temp,
                                   daily_energy)


class CLIError(Exception):
    """Generic exception to raise and log different fatal errors."""

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
    """Determines if time is daylight or night time
        Args:
            dt (datetime.datetime): date and time of observation
            latitude (float): latitude of observation
            longitude (float): longitude of observation
            delta (float): minutes before sunrise and after sunset to extend daylight range

        Returns:
            bool:
                True: is daylight time
                False: is night time
    """
    local_sun = sun.Sun(latitude, longitude)
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


def print_version(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return
    click.echo('%s %s (%s)' % (ctx.info_name, "v%s" % __version__, str(__updated__)))
    ctx.exit()


@click.command()
@click.option("-c", "--command", required=True, type=str, envvar='CMD',
              help="command to capture data from power inverter")
@click.option("-a", "--api-key", required=True, type=str, envvar='KEY',
              help="API key to access pvoutput.org services")
@click.option("-i", "--system-id", required=True, type=str, envvar='SID',
              help="system id on pvoutput.org where to store both strings pv data")
@click.option("-m", "--minutes_delta", envvar='NUM', default="30", type=int,
              help="executes if current time is %(metavar)s minutes before sunrise and %(metavar)s minutes after sunset [default: %(default)s]")
@click.option("--latitude", envvar="LAT", type=float,
              help="latitude for sunrise and sunset calculation")
@click.option("--longitude", envvar="LON", type=float,
              help="longitude for sunrise and sunset calculation")
@click.option("-v", "--verbose", count=True, help="set verbosity level")
@click.option('-V', '--version', is_flag=True, callback=print_version, expose_value=False, is_eager=True)
def main(command, api_key, system_id, minutes_delta, latitude, longitude, verbose):
    """Command line options."""
#     program_name = os.path.basename(sys.argv[0])
#     program_version = "v%s" % __version__
#     program_build_date = str(__updated__)
#     program_version_message = '%%(prog)s %s (%s)' % (program_version, program_build_date)
#     program_shortdesc = __import__('__main__').__doc__.split("\n")[1]
#     program_license = '''%s
#
#   Created by Yuri Valentini on %s.
#   Copyrights:
#     2014 Yuri Valentini. All rights reserved.
#     2021 Paul Phillips. All rights reserved.
#
#   Licensed under the GNU GENERAL PUBLIC LICENSE v3
#   https://www.gnu.org/copyleft/gpl.html
#
#   Distributed on an "AS IS" basis without warranties
#   or conditions of any kind, either express or implied.
#
# USAGE
# ''' % (program_shortdesc, str(__date__))

    try:
        # Setup argument parser
        # parser = argparse.ArgumentParser(description=program_license,
        #                                  formatter_class=argparse.RawDescriptionHelpFormatter)
        # parser.add_argument("-c", "--command", dest="command", metavar="CMD", required=True,
        #                     help="command to capture data from power inverter")
        # parser.add_argument("-a", "--api-key", dest="api_key", metavar="KEY", required=True,
        #                     help="API key to access pvoutput.org services")
        # parser.add_argument("-i", "--system-id", dest="system_id", metavar="SID", required=True,
        #                     help="system id on pvoutput.org where to store both strings pv data")
        # parser.add_argument("-m", "--minutes_delta", dest="delta", metavar="NUM", default="30", type=int,
        #                     help="executes if current time is %(metavar)s minutes before sunrise and %(metavar)s minutes after sunset [default: %(default)s]")
        # parser.add_argument("--latitude", dest="latitude", metavar="LAT", type=float,
        #                     help="latitude for sunrise and sunset calculation")
        # parser.add_argument("--longitude", dest="longitude", metavar="LON", type=float,
        #                     help="longitude for sunrise and sunset calculation")
        # parser.add_argument("-v", "--verbose", dest="verbose", action="count",
        #                     help="set verbosity level [default: %(default)s]")
        # parser.add_argument('-V', '--version', action='version', version=program_version_message)

        # # Process arguments
        # args = parser.parse_args()
        #
        if verbose > 0:
            logging.basicConfig(level=logging.INFO)

        if (longitude and not latitude) or (not longitude and latitude):
            raise CLIError(
                "you must specify both latitude and longitude to enable execution between sunset-sunrise or none to disable")

        now = datetime.datetime.now(tz=timezone.LocalTimezone())
        logging.info("Date   : %s" % now.date())
        logging.info("Time   : %s" % now.time())

        if latitude and longitude:
            if not is_daylight(now, float(latitude), float(longitude), int(minutes_delta)):
                logging.info("Not daylight time: exiting")
                return 0
        runner = AuroraRunner()
        line = runner.get_status(command)
        if not line:
            logging.info("Command error: exiting")
            return 1
        m = runner.decode_status(now, line)
        if not m:
            logging.info("Decode error: exiting")
            return 2
        api = PvOutputApi(api_key, int(system_id))
        if not api.add_status(now, m.daily_energy, m.str1_power.power + m.str2_power.power):
            logging.info("Send error: exiting")
            return 3
        logging.info("Completed successfully")
        return 0
    except KeyboardInterrupt:
        ### handle keyboard interrupt ###
        return 0


#    except Exception, e:
#        if DEBUG:
#            raise(e)
#        indent = len(program_name) * " "
#        sys.stderr.write(program_name + ": " + repr(e) + "\n")
#        sys.stderr.write(indent + "  for help use --help")
#        return -1

if __name__ == "__main__":
    # if DEBUG:
    #     import config
    #
    #     sys.argv.append("-v")  # verbose
    #     sys.argv.extend(
    #         ["-m", "30", "--latitude", str(config.LATITUDE), "--longitude", str(config.LONGITUDE)])  # sunrise sunset
    #     sys.argv.extend(["-c", "/root/pvaurora/aurora -a 2 -c -d0 -e -P 400 -Y 20 -W /dev/ttyUSB0"])
    #     sys.argv.extend(["-a", config.API_KEY])
    #     sys.argv.extend(["-i", str(config.SYSTEM_ID)])
    sys.exit(main())
