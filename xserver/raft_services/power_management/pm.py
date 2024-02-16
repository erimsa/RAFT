# Copyright (C) 2023 Advanced Micro Devices, Inc.  All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause

__author__ = "Salih Erim"
__copyright__ = "Copyright 2023, Advanced Micro Devices, Inc."

import os
import platform
import sys
import json
import subprocess


RAFT_DIR = '/usr/share/raft/'

sys.path.append(RAFT_DIR + 'xserver/utils')
#sys.path.append(os.environ['RAFT_DIR'] + 'xserver/utils')
import logging
from pmic import PMIC
from pmic import Rails
from pmic import Domain
from pmic import DeviceType
from sysmon import Sysmon_Device_Type
from sysmon import Sysmon
from utils import get_python_log_levels

        
class PM(object):
    _instance = None
    device_id = 0
    logger = None
    domains = []
    rails = []
    pmic = None
    board_name = ""
    sysmons = []

    def __init__(self, json_data, board_name, rail_prefix, eeprom):
        self.logger = self.GetLogger()
        self.boardeeprom = eeprom
        self.board_name = board_name
        power_domains_data = json_data[board_name]['POWER DOMAIN']
        temperature_data = json_data[board_name]['Temperature']
        rails_data = json_data[board_name][rail_prefix]
        for k, v in power_domains_data.items():
            temp_d = Domain(**v)
            for railname in temp_d.railnames:
                for k, v in rails_data.items():
                    if k == railname:
                        temp_r = Rails(**v)
                        temp_r._device_type = DeviceType.INA226 # fix this !!!
                        self.rails.append(temp_r)
                        temp_d.rails.append(temp_r)
            self.domains.append(temp_d)

        sensorStr = temperature_data['Sensor']
        if "i2c" in sensorStr:
            tokens = sensorStr.split("-")
            address = tokens[3]
            device = "/dev/i2c-" + tokens[2]
            temp_s = None
            try:
                temp_s = Sysmon(address, device, Sysmon_Device_Type.iic)
            except Exception as e:
                print(e)
                
            if temp_s is not None:
                self.sysmons.append(temp_s)


        self.pmic = PMIC(self.domains)
        if self.pmic is None:
            self.logger.error(f"PM: InitBoardInfo failed. ret = {ret}")
        self.logger.info("Inside PM Constructor")

    @staticmethod
    def GetLogger():
        """
        Static method to get the logger for the class.
        Default loglevel is set inside this class

        :return: logger

        """
        log_level = logging.INFO
        logging.basicConfig(format="%(levelname)s:%(message)s")
        logger = logging.getLogger(__name__)
        try:
            handler_set_check = getattr(logger, 'handler_set')
        except AttributeError:
            handler_set_check = False
        if not handler_set_check:
            logger.setLevel(log_level)
            logger.handler_set = True
            logger.disabled = False
        return logger

    # Log level
    def GetPythonLogLevels(self):
        """
        Return the logging levels supported by logging library in python

        :param : None
        :return: Dictionary showing the log levels supported by logging library
        """
        return get_python_log_levels()

    def SetServerLogLevel(self, PythonLogLevel):
        """
        Set the python log level to the given level

        :param : Log level to set
        :return: None
        """
        self.logger.debug(f"PythonLogLevel = {PythonLogLevel}")
        LogLevelsDict = get_python_log_levels()
        if PythonLogLevel == LogLevelsDict["DEBUG"]:
            self.logger.setLevel(logging.DEBUG)
        elif PythonLogLevel == LogLevelsDict["INFO"]:
            self.logger.setLevel(logging.INFO)
        elif PythonLogLevel == LogLevelsDict["WARNING"]:
            self.logger.setLevel(logging.WARNING)
        elif PythonLogLevel == LogLevelsDict["ERROR"]:
            self.logger.setLevel(logging.ERROR)
        else:
            self.logger.setLevel(logging.CRITICAL)
        return

    def GetBoardInfo(self):
        """
        Gets Board's Info

        :param : None 
        :return: Board Info in json formatted
        """
        return self.pmic.BoardInfo(self.boardeeprom)
    
    def GetPSTemperature(self):
        ps_temp = {}
        ret, val = subprocess.getstatusoutput('cat /sys/bus/iio/devices/iio\:device0/in_temp20_input')
        if ret == 0:
            ps_temp['PS_TEMP'] = float(int(val)/1000)
        return ps_temp
    
    def GetPowerDomains(self):
        """
        Gets list of Power Domains.

        :param : None
        :return: Domains in json formatted
        """
        powerdomains = {}
        powerdomains['POWER DOMAINS'] = []
        for d in self.domains:
            for k, v in d.__dict__.items():
                if k in ['name'] and v:
                    temp = {k: v}
                    powerdomains['POWER DOMAINS'].append(temp)
        return powerdomains

    def GetRailsOfDomain(self, domainname):
        """
        Gets list of Rails given domain name.

        :param domainname: string of a "domainname" 
        :return: Rails in json formatted
        """
        rails = {}
        rails[domainname] = []
        for d in self.domains:
            if d.name == domainname:
               for r in d.rails:
                for k, v in r.__dict__.items():
                    if k in ['name'] and v:
                        temp = {k: v}
                        rails[domainname].append(temp)
        return rails
    
    def GetRailDetails(self, railname):
        """
        Gets list of the rail's details given rail name.

        :param railname: string of a "railname" 
        :return: Details of the Rail in json formatted
        """
        details = {}
        for d in self.domains:
            for r in d.rails:
                if railname == r.name:
                    details[r.name] = {}
                    for k, v in r.__dict__.items():
                        if k not in ['name', 'sensor', '_sensor', '_device_type'] and v:
                                details[r.name][k] = v
        return details
    
    @staticmethod
    def GetRailValues(domain, rail):
        val = None
        for rail in domain.rails:
            val = self.GetValueOfRail(rail)

    
    def GetSensorValue(self, sensor, railname):
        value = {}
        v, i, p = self.pmic.GetSensorValues(sensor)
        value[railname] = {}
        value[railname]['Voltage'] = round(v, 4)
        value[railname]['Current'] = round(i, 4)
        value[railname]['Power'] = round(p, 4)
        return value

    def GetPowerValue(self, sensor, railname):
        value = {}
        v, i, p = self.pmic.GetSensorValues(sensor)
        value[railname] = {}
        value[railname]['Power'] = round(p, 4)
        return value

    def GetValueOfRail(self, railname):
        """
        Gets list of the rail's sensor values given rail name.

        :param railname: string of a "railname" 
        :return: Sensor values of the Rail in json formatted
        """
        data = None
        sensor = None
        for domain in self.domains:
            for rail in domain.rails:
                if rail.name == railname:
                    sensor = self.pmic.GetSensor(domain.name, rail.name)
        if sensor is not None: 
            data = self.GetSensorValue(sensor, railname)
        return data

    def GetValueOfDomain(self, domainname):
        """
        Gets the domain's all rail sensor values given domain name.

        :param : string of a "domainname" 
        :return: The domain's all rails sensor values of the Rail in json formatted
        """
        total_power = 0.0
        data = {}
        sensor = None
        data[domainname] = {}
        data[domainname]['Rails'] = []
        for domain in self.domains:
            if domain.name == domainname:
                for rail in domain.rails:
                    sensor = self.pmic.GetSensor(domain.name, rail.name)
                    if sensor is not None:
                        temp_v = self.GetSensorValue(sensor,rail.name)
                        data[domainname]['Rails'].append(temp_v)
                        total_power += temp_v[rail.name]['Power']
        data[domainname]['Total Power'] = round(total_power, 4)
        return data

    def GetPowerValueOfDomain(self, domainname):
        """
        Gets the domain's power value given domain name.

        :param : string of a "domainname" 
        :return: The domain's power value in json formatted
        """
        total_power = 0.0
        domain_power = 0.0
        data = {}
        data[domainname] = {}
        sensor = None
        for domain in self.domains:
            if domain.name == domainname:
                domain_power = 0.0
                for rail in domain.rails:
                    sensor = self.pmic.GetSensor(domain.name, rail.name)
                    if sensor is not None:
                        temp_p = self.GetPowerValue(sensor,rail.name)
                        domain_power += temp_p[rail.name]['Power']
                data[domainname]['Power'] = round(domain_power, 4)
        return data

    def GetPowersAll(self):
        """
        Gets the boards's all domain's and total power values

        :param : None 
        :return: The boards's all domain's and total power values
        """
        data = {}
        data[self.board_name] = {}
        data[self.board_name]['Power Domains'] = []
        total_power = 0.0
        for domain in self.domains:
            temp_p = self.GetPowerValueOfDomain(domain.name)
            total_power += temp_p[domain.name]['Power']
            data[self.board_name]['Power Domains'].append(temp_p)
        data[self.board_name]['Total Power'] = round(total_power, 4)
        return data

    def GetValuesAll(self):
        """
        Gets the boards's all domain's rails sensor values

        :param : None 
        :return: The board's all rails sensor values of the Rail in json formatted
        """
        data = {}
        data[self.board_name] = []
        for domain in self.domains:
            data[self.board_name].append(self.GetValueOfDomain(domain.name))
        return data
    

    def GetSysmonTemperatures(self):
        data = {}
        for s in self.sysmons:
            data[self.board_name] = {}
            _min, _max, _min_min, _max_max = s.ReadSysmonTemperatures()
            data[self.board_name]['MIN'] = _min
            data[self.board_name]['MAX'] = _max
            data[self.board_name]['MIN_MIN'] = _min_min
            data[self.board_name]['MAX_MAX'] = _max_max
            #data[self.board_name].append(temp_s)
        return data
        
    def __del__(self):
        self.logger.info("Inside PM Destructor")
