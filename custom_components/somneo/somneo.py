
import requests
import urllib3
import json
import xml.etree.ElementTree as ET
import logging
import datetime
from enum import Enum

_LOGGER = logging.getLogger('pysomneo')

WORKDAYS_BINARY_MASK = 62
WEEKEND_BINARY_MASK = 192

LIGHT_CURVES = {'sunny day': 0, 'island red': 1,
                'nordic white': 2, "carribean red": 3, "No Light": 4}
SOUND_SOURCE = {'wake-up': 'wus', 'radio': 'fmr', 'off': 'off'}
SOUND_CHANNEL = {'forest birds': '1',
                 'summer birds': '2',
                 'buddha wakeup': '3',
                 'morning alps': '4',
                 'yoga harmony': '5',
                 'nepal bowls': '6',
                 'summer lake': '7',
                 'ocean waves': '8',
                 }


class SoundDevice(str, Enum):
    WAKE_UP = "wus"
    RADIO = "fmr"
    OFF = "off"
    DUSK = "dus"

LIGHT_CURVES = {'sunny day': 0, 'island red': 1,
                'nordic white': 2, "carribean red": 3, "No Light": 4}

class LightCurves(Enum):
    SUNNY_DAY = 0
    ISLAND_RED = 1
    NORDIC_WHITE = 2
    CARRIBEAN_RED = 3
    NO_LIGHT = 4



class SoundChannel(str, Enum):
    RED = "1"
    GREEN = 2
    BLUE = 3


class SomneoRequestHelper():

    def __init__(self, host=None):
        self.host = host
        self._base_url = 'https://' + host + '/di/v1/products/1/'
        self._session = requests.Session()

    def _internal_call(self, method, url, headers, payload):
        """Call to the API."""
        args = dict()
        url = self._base_url + url

        if payload:
            args['data'] = json.dumps(payload)

        if headers:
            args['headers'] = headers

        while True:
            try:
                r = self._session.request(
                    method, url, verify=False, timeout=20, **args)
            except requests.Timeout:
                _LOGGER.error('Connection to Somneo timed out.')
                raise
            except requests.ConnectionError:
                continue
            except requests.RequestException:
                _LOGGER.error('Error connecting to Somneo.')
                raise
            else:
                if r.status_code == 422:
                    _LOGGER.error(f'Invalid Request. {r.content}')
                    raise Exception("Invalid Request.")
            break

        return r.json()

    def get(self, url, payload=None):
        """Get request."""
        return self._internal_call('GET', url, None, payload)

    def put(self, url, payload=None):
        """Put request."""
        return self._internal_call('PUT', url, {"Content-Type": "application/json"}, payload)


class SomneoAlarm(object):
    def __init__(self, host=None):
        self.request = SomneoRequestHelper(host)

        self.alarm_data = dict()
        self.snoozetime = None

    def __get_snooze_time(self):
        """Get the snooze time (minutes) of all alarms"""
        response = self.request.get('wualm')
        return response['snztm']

    def set_powerwake(self, alarm, onoff=False, hour=0, minute=0):
        """Set power wake"""
        alarm_settings = dict()
        alarm_settings['prfnr'] = self.alarm_data[alarm]['position']
        alarm_settings['pwrsz'] = 1 if onoff else 0
        alarm_settings['pszhr'] = int(hour)
        alarm_settings['pszmn'] = int(minute)

        # Send alarm settings
        self._put('wualm/prfwu', payload=alarm_settings)

    def add_alarm(self, alarm):
        """Add alarm to the list"""
        alarm_settings = dict()
        alarm_settings['prfnr'] = self.alarm_data[alarm]['position']
        alarm_settings['prfvs'] = True  # Add alarm

        # Send alarm settings
        self._put('wualm/prfwu', payload=alarm_settings)

    def remove_alarm(self, alarm):
        """Remove alarm from the list"""
        # Set default settings
        alarm_settings = dict()
        alarm_settings['prfnr'] = self.alarm_data[alarm]['position']
        alarm_settings['prfen'] = False  # Alarm  disabled
        alarm_settings['prfvs'] = False  # Remove alarm from alarm list
        alarm_settings['almhr'] = int(7)  # Alarm hour
        alarm_settings['almmn'] = int(30)  # Alarm Min
        alarm_settings['pwrsz'] = 0  # disable PowerWake
        alarm_settings['pszhr'] = 0  # set power wake (hour)
        alarm_settings['pszmn'] = 0  # set power wake (min)
        # set the default sunrise ("Sunny day" if curve > 0 or "No light" if curve == 0) (0 sunyday, 1 island red, 2 nordic white)
        alarm_settings['ctype'] = 0
        alarm_settings['curve'] = 20  # set light level (0-25)
        alarm_settings['durat'] = 30  # set sunrise duration (5-40)
        alarm_settings['daynm'] = 254  # set days to repeat the alarm
        alarm_settings['snddv'] = 'wus'  # set the wake_up sound (fmr is radio)
        # set sound channel (should be a string)
        alarm_settings['sndch'] = '1'
        alarm_settings['sndlv'] = 12   # set sound level

        # Send alarm settings
        self._put('wualm/prfwu', payload=alarm_settings)

    def toggle_alarm(self, alarm, status):
        """ Toggle the light on or off """
        self.alarm_data[alarm]['enabled'] = status
        payload = dict()
        payload['prfnr'] = self.alarm_data[alarm]['position']
        payload['prfvs'] = True
        payload['prfen'] = status
        self._put('wualm/prfwu', payload=payload)

    def get_alarm_settings(self, alarm):
        """ Get the alarm settings. """
        # Get alarm position
        alarm_pos = self.alarm_data[alarm]['position']

        # Get current alarm settings
        return self._put('wualm', payload={'prfnr': alarm_pos})

    def set_alarm(self, alarm, hour=None, minute=None, days=None):
        """ Set the time and day of an alarm. """

        # Adjust alarm settings
        alarm_settings = dict()
        # Alarm number
        alarm_settings['prfnr'] = self.alarm_data[alarm]['position']
        if hour is not None:
            alarm_settings['almhr'] = int(
                hour)                         # Alarm hour
            self.alarm_data[alarm]['time'] = datetime.time(
                int(hour), int(self.alarm_data[alarm]['time'].minute))
        if minute is not None:
            alarm_settings['almmn'] = int(minute)                # Alarm min
            self.alarm_data[alarm]['time'] = datetime.time(
                int(self.alarm_data[alarm]['time'].hour), int(minute))
        if days is not None:
            # set days to repeat the alarm
            alarm_settings['daynm'] = int(days)
            self.alarm_data[alarm]['days'] = days

        # Send alarm settings
        self._put('wualm/prfwu', payload=alarm_settings)

    def set_alarm_workdays(self, alarm):
        """ Set alarm on workday. """
        self.set_alarm(alarm, days=WORKDAYS_BINARY_MASK)

    def set_alarm_everyday(self, alarm):
        """ Set alarm on everyday. """
        self.set_alarm(alarm, days=WORKDAYS_BINARY_MASK + WEEKEND_BINARY_MASK)

    def set_alarm_weekend(self, alarm):
        """ Set alarm on weekends. """
        self.set_alarm(alarm, days=WEEKEND_BINARY_MASK)

    def set_alarm_tomorrow(self, alarm):
        """ Set alarm tomorrow. """
        self.set_alarm(alarm, days=0)

    def set_light_alarm(self, alarm, curve='sunny day', level=20, duration=30):
        """Adjust the lightcurve of the wake-up light"""
        alarm_settings = dict()
        # Alarm number
        alarm_settings['prfnr'] = self.alarm_data[alarm]['position']
        # Light curve type
        alarm_settings['ctype'] = LIGHT_CURVES[curve]
        # Light level (0 - 25, 0 is no light)
        alarm_settings['curve'] = level
        # Duration in minutes (5 - 40)
        alarm_settings['durat'] = duration

        # Send alarm settings
        self._put('wualm/prfwu', payload=alarm_settings)

    def set_sound_alarm(self, alarm, source='wake-up', channel='forest birds', level=12):
        """Adjust the alarm sound of the wake-up light"""
        alarm_settings = dict()
        # Alarm number
        alarm_settings['prfnr'] = self.alarm_data[alarm]['position']
        # Source (radio of wake-up)
        alarm_settings['snddv'] = SOUND_SOURCE[source]
        alarm_settings['sndch'] = SOUND_CHANNEL[channel] if source == 'wake-up' else (
            ' ' if source == 'off' else channel)    # Channel
        # Sound level (1 - 25)
        alarm_settings['sndlv'] = level

        # Send alarm settings
        self._put('wualm/prfwu', payload=alarm_settings)

    def set_snooze_time(self, snooze_time=9):
        """Adjust the snooze time (minutes) of all alarms"""
        self._put('wualm', payload={'snztm': snooze_time})

    def alarms(self):
        """Return the list of alarms."""
        alarms = dict()
        for alarm in list(self.alarm_data):
            alarms[alarm] = self.alarm_data[alarm]['enabled']

        return alarms

    def day_int(self, mon, tue, wed, thu, fri, sat, sun):
        return mon * 2 + tue * 4 + wed * 8 + thu * 16 + fri * 32 + sat * 64 + sun * 128

    def is_workday(self, alarm):
        days_int = self.alarm_data[alarm]['days']
        return days_int == 62

    def is_weekend(self, alarm):
        days_int = self.alarm_data[alarm]['days']
        return days_int == 192

    def is_everyday(self, alarm):
        days_int = self.alarm_data[alarm]['days']
        return days_int == 254

    def is_tomorrow(self, alarm):
        days_int = self.alarm_data[alarm]['days']
        return days_int == 0

    def alarm_settings(self, alarm):
        """Return the time and days alarm is set."""
        alarm_time = self.alarm_data[alarm]['time'].isoformat()

        alarm_days = []
        days_int = self.alarm_data[alarm]['days']
        if days_int & 2:
            alarm_days.append('mon')
        if days_int & 4:
            alarm_days.append('tue')
        if days_int & 8:
            alarm_days.append('wed')
        if days_int & 16:
            alarm_days.append('thu')
        if days_int & 32:
            alarm_days.append('fri')
        if days_int & 64:
            alarm_days.append('sat')
        if days_int & 128:
            alarm_days.append('sun')

        return alarm_time, alarm_days

    def next_alarm(self):
        """Get the next alarm that is set."""
        next_alarm = None
        for alarm in list(self.alarm_data):
            if self.alarm_data[alarm]['enabled'] == True:
                nu_tijd = datetime.datetime.now()
                nu_dag = datetime.date.today()
                alarm_time = self.alarm_data[alarm]['time']
                alarm_days_int = self.alarm_data[alarm]['days']
                alarm_days = []
                if alarm_days_int & 2:
                    alarm_days.append(1)
                if alarm_days_int & 4:
                    alarm_days.append(2)
                if alarm_days_int & 8:
                    alarm_days.append(3)
                if alarm_days_int & 16:
                    alarm_days.append(4)
                if alarm_days_int & 32:
                    alarm_days.append(5)
                if alarm_days_int & 64:
                    alarm_days.append(6)
                if alarm_days_int & 128:
                    alarm_days.append(7)

                day_today = nu_tijd.isoweekday()

                if not alarm_days:
                    alarm_time_full = datetime.datetime.combine(
                        nu_dag, alarm_time)
                    if alarm_time_full > nu_tijd:
                        new_next_alarm = alarm_time_full
                    elif alarm_time_full + datetime.timedelta(days=1) > nu_tijd:
                        new_next_alarm = alarm_time_full
                else:
                    for d in range(0, 7):
                        test_day = day_today + d
                        if test_day > 7:
                            test_day -= 7
                        if test_day in alarm_days:
                            alarm_time_full = datetime.datetime.combine(
                                nu_dag, alarm_time) + datetime.timedelta(days=d)
                            if alarm_time_full > nu_tijd:
                                new_next_alarm = alarm_time_full
                                break

                if next_alarm:
                    if new_next_alarm < next_alarm:
                        next_alarm = new_next_alarm
                else:
                    next_alarm = new_next_alarm

        if next_alarm:
            return next_alarm.isoformat()
        else:
            return None

    def update_alarm(self):
        # Get snoozetime
        self.snoozetime = self.__get_snooze_time()
        _LOGGER.error(f"snoozetime {self.snoozetime}")

        # Get alarm data
        enabled_alarms = self.request.get('wualm/aenvs')
        time_alarms = self.request.get('wualm/aalms')

        for alarm, enabled in enumerate(enabled_alarms['prfen']):
            alarm_name = 'alarm' + str(alarm)
            self.alarm_data[alarm_name] = dict()
            self.alarm_data[alarm_name]['position'] = alarm + 1
            self.alarm_data[alarm_name]['enabled'] = bool(enabled)
            self.alarm_data[alarm_name]['time'] = datetime.time(int(time_alarms['almhr'][alarm]),
                                                                int(time_alarms['almmn'][alarm]))
            self.alarm_data[alarm_name]['days'] = int(
                time_alarms['daynm'][alarm])


class Somneo(object):

    def __init__(self, host=None):
        """Initialize."""
        urllib3.disable_warnings()
        self.request = SomneoRequestHelper(host)
        self.alarm = SomneoAlarm(host)

        # {'name': 'Wake-up Light', 'allowpairing': False, 'type': 'HF367x', 'modelid': 'Healthy Sleep', 'allowuploads': True, 'serial': 'LMEB2117024804', 'swverwifi': '1.3.15-P ', 'wificountry': 'XX/17', 'ctn': 'HF3670/60', 'productid': '4222018689410I', 'pkgver': 500, 'swveruictrl': 'UT 0.7.1A', 'swverlight': 'LT 0.2.9', 'swvermp3': 'MP 0.0.1', 'swvericons': 'IC 0.0.8'}
        self.device_info = None

        # {'ltlvl': 20, 'onoff': False, 'tempy': False, 'ctype': 0, 'ngtlt': False, 'wucrv': [], 'pwmon': False, 'pwmvs': [0, 0, 0, 0, 0, 0], 'diman': 0}
        self.light_data = None

        #  {'mslux': 0.2, 'mstmp': 19.7, 'msrhu': 52.9, 'mssnd': 48, 'avlux': 0.2, 'avtmp': 19.8, 'avhum': 53.5, 'avsnd': 48, 'enscr': 0}
        self.sensor_data = None

        # {'stime': '2021-10-21T21:07:33-07:00', 'rlxmn': 0, 'rlxsc': 0, 'dskmn': 0, 'dsksc': 0}
        self.timer_runtime = None

        # {'durat': 15, 'onoff': False, 'maxpr': 7, 'progr': 4, 'rtype': 1, 'intny': 20, 'sndlv': 9, 'sndss': 0, 'rlbpm': [4, 5, 6, 7, 8, 9, 10], 'pause': [2000, 2000, 2000, 2000, 1000, 1000, 1000]}
        self.relax_status = None

        # {'fmthr': False, 'fmtwk': False, 'tmupd': 7, 'tzhrm': [-8, 0], 'dstwu': 60, 'tmsrc': 'int', 'tmsyn': '', 'tmser': '', 'locat': ''}
        self.timezone_status = None

        # {'onoff': False, 'curve': 15, 'durat': 30, 'ctype': 3, 'sndtp': 0, 'snddv': 'dus', 'sndch': '1', 'sndlv': 12, 'sndss': 0}
        self.dusk_status = None

        # {'onoff': False, 'tempy': False, 'sdvol': 12, 'sndss': 0, 'snddv': 'off', 'sndch': '1'}
        self.audio_info = None

        self.firmware_data = None

        # {'ntstr': '', 'ntend': '07:00', 'ntlen': '07:00', 'night': False, 'gdngt': False, 'gdday': False, 'tg2bd': '2021-10-18T20:48:44-07:00', 'tendb': '2021-10-18T20:48:44-07:00'}
        self.night_data = None

        # {'wusts': 768, 'rpair': False, 'prvmd': False, 'sdemo': False, 'pwrsz': False, 'nrcur': 25, 'wizrd': 99, 'brght': 3, 'dspon': True, 'wutim': 65535, 'dutim': 65535, 'canup': False, 'updtm': 900, 'updln': 60, 'sntim': 65535}
        self.settings_info = None

    def update(self):
        """Get the latest update from Somneo."""

        self.timezone_status = self.request.get("wutms")
        _LOGGER.error(f"timezone_status {self.timezone_status}")

        # Get Relax Mode Status
        self.relax_status = self.request.get("wurlx")
        _LOGGER.error(f"relax_status {self.relax_status}")

        # Get Dusk Status
        self.dusk_status = self.request.get("wudsk")
        _LOGGER.error(f"dusk_status {self.dusk_status}")

        # Get Timer Runtime
        self.timer_runtime = self.request.get("wutmr")
        _LOGGER.error(f"timer_runtime {self.timer_runtime}")

        self.settings_info = self.request.get("wusts")
        _LOGGER.error(f"settings_info {self.settings_info}")

        # Get light information
        self.light_data = self.request.get('wulgt')
        _LOGGER.error(f"light_data {self.light_data}")

        # Get firmware data
        # self.firmware_data = self.request.get('firmware')
        # _LOGGER.error(f"firmware_data {self.firmware_data}")

        # Get sensor data
        self.sensor_data = self.request.get('wusrd')
        _LOGGER.error(f"sensor_data {self.sensor_data}")

        # Get Unique Device info
        self.device_info = self.request.get('device')
        _LOGGER.error(f"device_info {self.device_info}")

        self.audio_info = self.request.get('wuply')
        _LOGGER.error(f"audio_info {self.audio_info}")

        self.night_data = self.request.get('wungt')
        _LOGGER.error(f"night_data {self.night_data}")

        self.alarm.update_alarm()

    def set_alarm(self,
                  alarm_num=0,
                  enabled=False,
                  hours=0,
                  minutes=0,
                  days=0,
                  sun_duration=0,
                  sun_intensity=0,
                  sun_theme="No Light",
                  power_wake=False,
                  sound="forest birds",
                  snooze_duration=9,
                  ):
        return self

    def set_sunset(self,
                   enable=False,
                   duration=None,  # app does 5 to 60 min
                   light_intensity=None,  # 0 to 25
                   color_type=None,  # 0 to 4
                   sound_device="dus",  # dus, fmr, off
                   sound_channel=1,  # 1 to 4 if dus; 1 to 6 if fmr; blank if off
                   volume=None,  # 1 to 25
                   ):
        self.dusk_status["onoff"] = enable
        if light_intensity:
            self.dusk_status["curve"] = light_intensity
        if duration:
            self.dusk_status["durat"] = duration
        if color_type:
            self.dusk_status["ctype"] = color_type
        if sound_device:
            self.dusk_status["snddv"] = sound_device
        if sound_channel:
            self.dusk_status["sndch"] = sound_channel
        if volume:
            self.dusk_status["sndlv"] = volume
        return self.request.put("wudsk", payload=self.dusk_status)

    def set_relax_breathe(self,
                          breating_pace=0,
                          duration=15,
                          guidance_type="sound",
                          volume=0,
                          light_intensity=0,
                          ):
        return self

    def set_audio(self,
                  enable=False,
                  sound_device="fmr",
                  sound_volume=None,
                  sound_channel=None):
        self.audio_info["onoff"] = enable
        self.audio_info["snddv"] = sound_device
        if sound_volume:
            self.audio_info["sdvol"] = sound_volume
        if sound_channel:
            self.audio_info["sndch"] = sound_channel
        return self.request.put("wuply", payload=self.audio_info)

    def set_light(self,
                  enable=False,
                  light_intensity=None,
                  color_type=None):

        self.light_data["onoff"] = enable
        if light_intensity:
            self.light_data["ltlvl"] = light_intensity
        if color_type and color_type != LightCurves.NO_LIGHT:
            self.light_data["ctype"] = color_type.value
        return self.request.put("wulgt", payload=self.light_data)