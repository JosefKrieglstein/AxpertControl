#! /usr/bin/python

# Axpert Inverter control script

# Read values from inverter, sends values to emonCMS,
# read electric low or high tarif from emonCMS and setting charger and mode to hold batteries fully charged
# controls grid charging current to meet circuit braker maximum alloweble grid current(power)
# calculation of CRC is done by XMODEM mode, but in firmware is wierd mistake in POP02 command, so exception of calculation is done in serial_command(command) function
# real PL2303 = big trouble in my setup, cheap chinese converter some times disconnecting, workaround is at the end of serial_command(command) function
# differenc between SBU(POP02) and Solar First (POP01): in state POP01 inverter works only if PV_voltage <> 0 !!! SBU mode works during night

# Josef Krieglstein 20170215 last update

import urllib2
import serial, time, sys, string
import sqlite3
import json
import urllib
import httplib
import datetime
import calendar
import os
import re
import crcmod
from binascii import unhexlify

# Domain you want to post to: localhost would be an emoncms installation on your own laptop
# this could be changed to emoncms.org to post to emoncms.org or your own server
server = "emoncms.trenet.org"

# Location of emoncms in your server, the standard setup is to place it in a folder called emoncms
# To post to emoncms.org change this to blank: ""
emoncmspath = ""

# Write apikey of emoncms account
apikey = "53863683c9745504ab727de6f736c94b"

# Node id youd like the emontx to appear as
nodeid = 13

#Axpert Commands and examples
#QPI            # Device protocol ID inquiry
#QID            # The device serial number inquiry
#QVFW           # Main CPU Firmware version inquiry
#QVFW2          # Another CPU Firmware version inquiry
#QFLAG          # Device flag status inquiry
#QPIGS          # Device general status parameters inquiry
                # GridVoltage, GridFrequency, OutputVoltage, OutputFrequency, OutputApparentPower, OutputActivePower, OutputLoadPercent, BusVoltage, BatteryVoltage, BatteryChargingCurrent, BatteryCapacity, InverterHeatSinkTemperature, PV-InputCurrentForBattery, PV-InputVoltage, BatteryVoltageFromSCC, BatteryDischargeCurrent, DeviceStatus,
#QMOD           # Device mode inquiry P: PowerOnMode, S: StandbyMode, L: LineMode, B: BatteryMode, F: FaultMode, H: PowerSavingMode
#QPIWS          # Device warning status inquiry: Reserved, InverterFault, BusOver, BusUnder, BusSoftFail, LineFail, OPVShort, InverterVoltageTooLow, InverterVoltageTooHIGH, OverTemperature, FanLocked, BatteryVoltageHigh, BatteryLowAlarm, Reserved, ButteryUnderShutdown, Reserved, OverLoad, EEPROMFault, InverterSoftFail, SelfTestFail, OPDCVoltageOver, BatOpen, CurrentSensorFail, BatteryShort, PowerLimit, PVVoltageHigh, MPPTOverloadFault, MPPTOverloadWarning, BatteryTooLowToCharge, Reserved, Reserved
#QDI            # The default setting value information
#QMCHGCR        # Enquiry selectable value about max charging current
#QMUCHGCR       # Enquiry selectable value about max utility charging current
#QBOOT          # Enquiry DSP has bootstrap or not
#QOPM           # Enquiry output mode
#QPIRI          # Device rating information inquiry - nefunguje
#QPGS0          # Parallel information inquiry
                # TheParallelNumber, SerialNumber, WorkMode, FaultCode, GridVoltage, GridFrequency, OutputVoltage, OutputFrequency, OutputAparentPower, OutputActivePower, LoadPercentage, BatteryVoltage, BatteryChargingCurrent, BatteryCapacity, PV-InputVoltage, TotalChargingCurrent, Total-AC-OutputApparentPower, Total-AC-OutputActivePower, Total-AC-OutputPercentage, InverterStatus, OutputMode, ChargerSourcePriority, MaxChargeCurrent, MaxChargerRange, Max-AC-ChargerCurrent, PV-InputCurrentForBattery, BatteryDischargeCurrent
#PEXXX          # Setting some status enable
#PDXXX          # Setting some status disable
#PF             # Setting control parameter to default value
#FXX            # Setting device output rating frequency
#POP02          # set to SBU
#POP01          # set to Solar First
#POP00          # Set to UTILITY
#PBCVXX_X       # Set battery re-charge voltage
#PBDVXX_X       # Set battery re-discharge voltage
#PCP00          # Setting device charger priority: Utility First
#PCP01          # Setting device charger priority: Solar First
#PCP02          # Setting device charger priority: Solar and Utility
#PGRXX          # Setting device grid working range
#PBTXX          # Setting battery type
#PSDVXX_X       # Setting battery cut-off voltage
#PCVVXX_X       # Setting battery C.V. charging voltage
#PBFTXX_X       # Setting battery float charging voltage
#PPVOCKCX       # Setting PV OK condition
#PSPBX          # Setting solar power balance
#MCHGC0XX       # Setting max charging Current          M XX
#MUCHGC002      # Setting utility max charging current  0 02
#MUCHGC010      # Setting utility max charging current  0 10
#MUCHGC020      # Setting utility max charging current  0 20
#MUCHGC030      # Setting utility max charging current  0 30
#POPMMX         # Set output mode       M 0:single, 1: parrallel, 2: PH1, 3: PH2, 4: PH3

#notworking
#PPCP000        # Setting parallel device charger priority: UtilityFirst - notworking
#PPCP001        # Setting parallel device charger priority: SolarFirst - notworking
#PPCP002        # Setting parallel device charger priority: OnlySolarCharging - notworking

ser = serial.Serial()
ser.port = "/dev/ttyUSB0"
ser.baudrate = 2400
ser.bytesize = serial.EIGHTBITS     #number of bits per bytes
ser.parity = serial.PARITY_NONE     #set parity check: no parity
ser.stopbits = serial.STOPBITS_ONE  #number of stop bits
ser.timeout = 1                     #non-block read
ser.xonxoff = False                 #disable software flow control
ser.rtscts = False                  #disable hardware (RTS/CTS) flow control
ser.dsrdtr = False                  #disable hardware (DSR/DTR) flow control
ser.writeTimeout = 2                #timeout for write

try:
    ser.open()

except Exception, e:
    print "error open serial port: " + str(e)
    exit()

def get_data():
    #collect data from axpert inverter
    mode = 0
    if ser.isOpen():
        try:
            data = "{"
            response = serial_command("QPGS0")
            if "NAKss" in response:
                time.sleep(2)
                return ""
            else:
                response.rstrip()
                nums = response.split(' ', 99)
                if nums[2] == "L":
                    data += "Gridmode:1"
                else:
                    data += "Gridmode:0"

                if nums[2] == "B":
                    data += ",Solarmode:1"
                else:
                    data += ",Solarmode:0"

            response = serial_command("QPIGS")
            if "NAKss" in response:
                time.sleep(0.5)
                data = ""
                return ""
            response.rstrip()
            nums = response.split(' ', 99)
            data += ",Grid_voltage:" + nums[0]
            data += ",Grid_frequency:" + nums[1]
            data += ",AC_output_voltage:" + nums[2]
            data += ",AC_output_frequency:" + nums[3]
            data += ",AC_output_apparent_power:" + nums[4]
            data += ",AC_output_active_power:" + nums[5]
            data += ",Output_Load_Percent:" + nums[6]
            data += ",Bus_voltage:" + nums[7]
            data += ",Battery_voltage:" + nums[8]
            data += ",Battery_charging_current:" + nums[9]
            data += ",Battery_capacity:" + nums[10]
            data += ",Inverter_heatsink_temperature:" + nums[11]
            data += ",PV_input_current_for_battery:" + nums[12]
            data += ",PV_input_voltage:" + nums[13]
            data += ",Battery_voltage_from_SCC:" + nums[14]
            data += ",Battery_discharge_current:" + nums[15]
            data += ",Device_status:" + nums[16]

        except Exception, e:
            print "error parsing inverter data...: " + str(e)
            return ""

    else:
        ser.close()
        data = ""
        print "cannot use serial port ..."
        return ""
    return data

def set_charge_current():
    # Automaticly adjust axpert inverter grid charging current

    # 2A = 100W, 10A = 500W, 20A = 1000W, 30 = 1500W
    # load >3000W -> 02A
    # load <3000W -> 10A
    # load <2000W -> 20A
    # load <1000W -> 30A

    if ser.isOpen():
        try:
            current = 0
            load_power = 0
            response = serial_command("QPGS0")
            if "NAKss" in response:
                time.sleep(0.5)
                return [0]
            response.rstrip()
            nums = response.split(' ', 99)
            current = int ( nums[24] )
            response = serial_command("QPIGS")
            if "NAKss" in response:
                time.sleep(0.5)
                return [0]
            response.rstrip()
            nums = response.split(' ', 99)
            load_power = int ( nums[5] )
            print load_power
            if load_power > 3000:
                if not current == 2:
                    current = 2
                    response = serial_command("MUCHGC002")
            elif load_power > 2000:
                if not current == 10:
                    current = 10
                    response = serial_command("MUCHGC010")
            elif load_power > 1000:
                if not current == 20:
                    current = 20
                    response = serial_command("MUCHGC020")
            else:
                if not current == 30:
                    current = 30
                    response = serial_command("MUCHGC030")
            print current
            if "NAKss" in response:
                time.sleep(0.5)
                return [0]

        except Exception, e:
            print "error parsing inverter data...: " + str(e)
            return [0]

    else:
        ser.close()
        print "cannot use serial port ..."
        return [0]
    return current

def get_output_source_priority():
    #get inverter output mode priority
    output_source_priority = "8"
    if ser.isOpen():
        try:
            response = serial_command("QPIRI")
            if "NAKss" in response:
                time.sleep(0.5)
                return ""
            response.rstrip()
            nums = response.split(' ', 99)
            output_source_priority = nums[16]

        except Exception, e:
            print "error parsing inverter data...: " + str(e)
            return ""

    else:
        ser.close()
        print "cannot use serial port ..."
        return ""
    return output_source_priority

def get_charger_source_priority():
    #get inverter charger mode priority
    charger_source_priority = "8"
    if ser.isOpen():
        try:
            response = serial_command("QPIRI")
            if "NAKss" in response:
                time.sleep(0.5)
                return ""
            response.rstrip()
            nums = response.split(' ', 99)
            charger_source_priority = nums[17]

        except Exception, e:
            print "error parsing inverter data...: " + str(e)
            return ""

    else:
        ser.close()
        print "cannot use serial port ..."
        return ""
    return charger_source_priority

def set_output_source_priority(output_source_priority):
    #set inverter output mode priority
        if not output_source_priority == "":
            if ser.isOpen():
                try:
                    if output_source_priority == 0:
                        response = serial_command("POP00")
                        print response
                    elif output_source_priority == 1:
                        response = serial_command("POP01")
                        print response
                    elif output_source_priority == 2:
                        response = serial_command("POP02")
                        print response

                except Exception, e:
                    print "error parsing inverter data...: " + str(e)
                    return [0]

        else:
            ser.close()
            print "cannot use serial port ..."
            return [0]
        return [1]

def set_charger_source_priority(charger_source_priority):
    #set inverter charge mode priority
        if not charger_source_priority == "":
            if ser.isOpen():
                try:
                    if charger_source_priority == 0:
                        response = serial_command("PCP00")
                        print response
                    elif charger_source_priority == 1:
                        response = serial_command("PCP01")
                        print response
                    elif charger_source_priority == 2:
                        response = serial_command("PCP02")
                        print response
                    elif charger_source_priority == 3:
                        response = serial_command("PCP03")
                        print response

                except Exception, e:
                    print "error parsing inverter data...: " + str(e)
                    return [0]

        else:
            ser.close()
            print "cannot use serial port ..."
            return [0]
        return [1]

def send_data(data):
    # Send data to emoncms server
    try:
        conn = httplib.HTTPConnection(server)
        conn.request("GET", "/"+emoncmspath+"/input/post.json?&node="+str(nodeid)+"&json="+data+"&apikey="+apikey)
        response = conn.getresponse()
        conn.close()

    except Exception as e:
        print "error sending to emoncms...: " + str(e)
        return [0]
    return [1]

def read_hdo(id):
    # Read high/low tarif from emoncms (the acctual tarif information can be created by cron script, or from emonTX input)
    # in Czech Republic, West Bohemia it is perriodicaly, tarif name is for example: A1B8DP5 => (8 hours of low and 16 hours of high) / each day
    try:
        conn = httplib.HTTPConnection(server)
        conn.request("GET", "/"+emoncmspath+"/feed/value.json?id="+str(id)+"&apikey="+apikey)
        response = conn.getresponse()
        response_tmp = response.read()
        conn.close()
        return response_tmp

    except Exception as e:
        print "error reading from emoncms...: " + str(e)
        return [0]
    return [1]


def serial_command(command):
    try:
        ser.flushInput()            #flush input buffer, discarding all its contents
        ser.flushOutput()           #flush output buffer, aborting current output and discard all that is in buffer
        xmodem_crc_func = crcmod.predefined.mkCrcFun('xmodem')
        if command == "POP02":          # wierd mistake in Axpert firmware - correct CRC is: 0xE2 0x0A
            command_crc = '\x50\x4f\x50\x30\x32\xe2\x0b\x0d'
        else:
            command_crc = command + unhexlify(hex(xmodem_crc_func(command)).replace('0x','',1)) + '\x0d'
        ser.write(command_crc)
        response = ser.readline()
        print command
        print response
        return response

    except Exception, e:
        print "error reading inverter...: " + str(e)
        ser.close()
        time.sleep(20)  # Problem with some USB-Serial adapters, they are some times disconnecting, 20 second helps to reconnect at same ttySxx
        data = ""
        ser.open()
        time.sleep(0.5)
        return [0]

    return [0]

def main():
    while True:
        time.sleep(0.1)
        data = get_data()
        charge_current = set_charge_current ()
        if not data == "":
            send = send_data(data)
        hdo_tmp_LT = read_hdo(68)       #Read emoncms feed id=68 = LowTarif
        hdo_tmp_HT = read_hdo(69)       #Read emoncms feed id=69 = HighTarif
        output_source_priority = get_output_source_priority()
        charger_source_priority = get_charger_source_priority()
        if not output_source_priority == "8":
            if not charger_source_priority == "8":
                if hdo_tmp_LT == "1":
                    print "LT"  # electricity is cheap, so charge batteries from grid and hold them fully charged! important for Lead Acid Batteries Only!
                    if not output_source_priority == "0":       # Utility First (0: Utility first, 1: Solar First, 2: SBU)
                        set_output_source_priority(0)
                    if not charger_source_priority == "2":      # Utility First (0: Utility first, 1: Solar First, 2: Solar+Utility, 3: Solar Only)
                        set_charger_source_priority(2)
                if hdo_tmp_HT == "1":
                    print "HT"  # electricity is expensive, so supply everything from batteries not from grid
                    if not output_source_priority == "2":       # Utility First (0: Utility first, 1: Solar First, 2: SBU)
                        set_output_source_priority(2)
                    if not charger_source_priority == "3":      # Utility First (0: Utility first, 1: Solar First, 2: Solar+Utility, 3: Solar Only)
                        set_charger_source_priority(3)

if __name__ == '__main__':
    main()
