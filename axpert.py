#! /usr/bin/python

# Axpert Inverter control script

# Read values from inverter, sends values to emonCMS,
# read electric low or high tarif from emonCMS and setting charger and mode to hold batteries fully charged
# controls grid charging current to meet circuit braker maximum alloweble grid current(power)
# calculation of CRC is done by XMODEM mode, but in firmware is wierd mistake in POP02 command, so exception of calculation is done in serial_command(command) function
# real PL2303 = big trouble in my setup, cheap chinese converter some times disconnecting, workaround is at the end of serial_command(command) function
# differenc between SBU(POP02) and Solar First (POP01): in state POP01 inverter works only if PV_voltage <> 0 !!! SBU mode works during night

# Josef Krieglstein 20190312 last update

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
import usb.core
import usb.util
import sys
import signal
from binascii import unhexlify
#import binascii

# Domain you want to post to: localhost would be an emoncms installation on your own laptop
# this could be changed to emoncms.org to post to emoncms.org or your own server
server = "emoncms.trenet.org"

#connection = "serial"
connection = "USB"

# Location of emoncms in your server, the standard setup is to place it in a folder called emoncms
# To post to emoncms.org change this to blank: ""
emoncmspath = ""

# Write apikey of emoncms account
apikey = "...."

# Node id youd like the emontx to appear as
nodeid0 = 21
#nodeid1 = 22

mode1 = 0
mode2 = 0

#Axpert Commands and examples
#Q1		# Undocumented command: LocalInverterStatus (seconds from absorb), ParaExistInfo (seconds from end of Float), SccOkFlag, AllowSccOnFlag, ChargeAverageCurrent, SCC PWM Temperature, Inverter Temperature, Battery Temperature, Transformer Temperature, GPDAT, FanLockStatus, FanPWMDuty, FanPWM, SCCChargePowerWatts, ParaWarning, SYNFreq, InverterChargeStatus
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
#QBV		# Compensated Voltage, SoC
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

def handler(signum, frame):
    print 'Signal handler called with signal', signum
    raise Exception("Handler")

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
#    usb0 = open('/dev/hidraw0', mode = 'rb+', buffering = 32)
#    usb0 = os.open('/dev/hidraw0', mode='rb+', newline=None)
    usb0 = os.open('/dev/hidraw0', os.O_RDWR | os.O_NONBLOCK)

except Exception, e:
    print "error open USB port: " + str(e)
    exit()

def get_data(command,inverter):
    #collect data from axpert inverter
    mode = -1
    load = -1
    status = -1
    parrallel_num = -1
    try:
    	data = "{"
	if ( connection == "serial" and ser.isOpen() or connection == "USB" ):
            response = serial_command(command)
	    if "NAKss" in response or response == '':
                if connection == "serial": time.sleep(0.2)
            	return '', '', '', ''
    	    else:
		response_num = re.sub ('[^0-9. ]','',response)
		if command == "QPGS0":
            	    response.rstrip()
            	    response_num.rstrip()
		    nums = response_num.split(' ', 99)
            	    nums_mode = response.split(' ', 99)
		    if nums_mode[2] == "L":
                	data += "Gridmode:1"
			data += ",Solarmode:0"
			mode = 0
            	    elif nums_mode[2] == "B":
                	data += "Gridmode:0"
                	data += ",Solarmode:1"
			mode = 1
            	    elif nums_mode[2] == "S":
                	data += "Gridmode:0"
                	data += ",Solarmode:0"
			mode = 2
            	    elif nums_mode[2] == "F":
                	data += "Gridmode:0"
                	data += ",Solarmode:0"
			mode = 3
        
		    data += ",The_parallel_num:" + nums[0]
        	    data += ",Serial_number:" + nums[1]
        	    data += ",Fault_code:" + nums[3]
        	    data += ",Load_percentage:" + nums[10]
        	    data += ",Total_charging_current:" + nums[15]
        	    data += ",Total_AC_output_active_power:" + nums[17]
        	    data += ",Total_AC_output_apparent_power:" + nums[16]
        	    data += ",Total_AC_output_percentage:" + nums[18]
        	    data += ",Inverter_Status:" + nums[19]
        	    data += ",Output_mode:" + nums[20]
        	    data += ",Charger_source_priority:" + nums[21]
        	    data += ",Max_Charger_current:" + nums[22]
        	    data += ",Max_Charger_range:" + nums[23]
        	    data += ",Max_AC_charger_current:" + nums[24]
		    parrallel_num = nums[0]
		    load = nums[17]

		elif command == "QPGS1":
            	    response.rstrip()
		    response_num.rstrip()
            	    nums = response_num.split(' ', 99)
            	    nums_mode = response.split(' ', 99)
		    if nums_mode[2] == "L":
                	data += "Gridmode1:1"
			data += ",Solarmode1:0"
			mode = 0
            	    elif nums_mode[2] == "B":
                	data += "Gridmode1:0"
                	data += ",Solarmode1:1"
			mode = 1
            	    elif nums_mode[2] == "S":
                	data += "Gridmode1:0"
                	data += ",Solarmode1:0"
			mode = 2
            	    elif nums_mode[2] == "F":
                	data += "Gridmode1:0"
                	data += ",Solarmode1:0"
			mode = 3
            
		    data += ",The_parallel_num1:" + nums[0]
        	    data += ",Serial_number1:" + nums[1]
        	    data += ",Fault_code1:" + nums[3]
        	    data += ",Load_percentage1:" + nums[10]
        	    data += ",Total_charging_current1:" + nums[15]
        	    data += ",Total_AC_output_active_power1:" + nums[17]
        	    data += ",Total_AC_output_apparent_power1:" + nums[16]
        	    data += ",Total_AC_output_percentage1:" + nums[18]
        	    data += ",Inverter_Status1:" + nums[19]
        	    data += ",Output_mode1:" + nums[20]
        	    data += ",Charger_source_priority1:" + nums[21]
        	    data += ",Max_Charger_current1:" + nums[22]
        	    data += ",Max_Charger_range1:" + nums[23]
        	    data += ",Max_AC_charger_current1:" + nums[24]
		    parrallel_num = nums[0]

		elif command == "QPIGS":
        	    response_num.rstrip()
        	    nums = response_num.split(' ', 99)
        	    data += "Grid_voltage:" + nums[0]
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
        	    data += ",PV_Input_Voltage:" + nums[13]
        	    data += ",Battery_voltage_from_SCC:" + nums[14]
        	    data += ",Battery_discharge_current:" + nums[15]
        	    data += ",Device_status:" + nums[16]

		elif command == "Q1":
        	    response_num.rstrip()
        	    nums = response_num.split(' ', 99)
        	    data += "SCCOkFlag:" + nums[2]
        	    data += ",AllowSCCOkFlag:" + nums[3]
        	    data += ",ChargeAverageCurrent:" + nums[4]
        	    data += ",SCCPWMTemperature:" + nums[5]
        	    data += ",InverterTemperature:" + nums[6]
        	    data += ",BatteryTemperature:" + nums[7]
        	    data += ",TransformerTemperature:" + nums[8]
        	    data += ",GPDAT:" + nums[9]
        	    data += ",FanLockStatus:" + nums[10]
        	    data += ",FanPWM:" + nums[12]
        	    data += ",SCCChargePower:" + nums[13]
        	    data += ",ParaWarning:" + nums[14]
		    data += ",InverterChargeStatus:" + nums[16]

		elif command == "QBV":
        	    response_num.rstrip()
        	    nums = response_num.split(' ', 99)
		    data += "Battery_voltage_compensated:" + nums[0]
		    data += ",SoC:" + nums[1]
		else: return '', '', '', ''
		data += "}"

    except Exception, e:
            print "error parsing inverter data...: " + str(e)
            return '', '', '', ''

    return data, parrallel_num, load, mode

def set_charge_current():
    # Automaticly adjust axpert inverter grid charging current

    # 2A = 100W, 10A = 500W, 20A = 1000W, 30 = 1500W
    # load >3000W -> 02A
    # load <3000W -> 10A
    # load <2000W -> 20A
    # load <1000W -> 30A

    try:
	if ( connection == "serial" and ser.isOpen() or connection == "USB" ):
            current = 0
            load_power = 0
            response = serial_command("QPGS0")
            if "NAKss" in response:
		if connection == "serial": time.sleep(0.5)
                return ''
            response.rstrip()
            nums = response.split(' ', 99)
            current = int ( nums[24] )
            response = serial_command("QPIGS")
            if "NAKss" in response:
		if connection == "serial": time.sleep(0.5)
                return ''
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
                if connection == "serial": time.sleep(0.5)
                return ''

    	elif ( connection == "serial" ):
            ser.close()
            print "cannot use serial port ..."
            return ""

    except Exception, e:
            print "error parsing inverter data...: " + str(e)
            return ''

    return current

def get_output_source_priority():
    #get inverter output mode priority
    output_source_priority = "8"
    try:
	if ( connection == "serial" and ser.isOpen() or connection == "USB" ):
            response = serial_command("QPIRI")
            if "NAKss" in response:
                if connection == "serial": time.sleep(0.5)
                return ""
            response.rstrip()
            nums = response.split(' ', 99)
            output_source_priority = nums[16]

    	elif ( connection == "serial" ):
            ser.close()
            print "cannot use serial port ..."
            return ""

    except Exception, e:
            print "error parsing inverter data...: " + str(e)
            return ""

    return output_source_priority

def get_charger_source_priority():
    #get inverter charger mode priority
    charger_source_priority = "8"
    try:
	if ( connection == "serial" and ser.isOpen() or connection == "USB" ):
            response = serial_command("QPIRI")
            if "NAKss" in response:
                if connection == "serial": time.sleep(0.5)
                return ""
            response.rstrip()
            nums = response.split(' ', 99)
            charger_source_priority = nums[17]

    	elif ( connection == "serial" ):
            ser.close()
            print "cannot use serial port ..."
            return ""

    except Exception, e:
            print "error parsing inverter data...: " + str(e)
            return ""

    return charger_source_priority

def set_output_source_priority(output_source_priority):
    #set inverter output mode priority
        if not output_source_priority == "":
    	    try:
		if ( connection == "serial" and ser.isOpen() or connection == "USB" ):
                    if output_source_priority == 0:
                        response = serial_command("POP00")
                        print response
                    elif output_source_priority == 1:
                        response = serial_command("POP01")
                        print response
                    elif output_source_priority == 2:
                        response = serial_command("POP02")
                        print response

    		elif ( connection == "serial" ):
        	    ser.close()
        	    print "cannot use serial port ..."
        	    return ""

    	    except Exception, e:
                print "error parsing inverter data...: " + str(e)
                return ''

        return 1

def set_charger_source_priority(charger_source_priority):
    #set inverter charge mode priority
        if not charger_source_priority == "":
            try:
		if ( connection == "serial" and ser.isOpen() or connection == "USB" ):

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

    		elif ( connection == "serial" ):
        	    ser.close()
        	    print "cannot use serial port ..."
        	    return ""

            except Exception, e:
                    print "error parsing inverter data...: " + str(e)
                    return ''

        return 1

def send_data(data):
    # Send data to emoncms server
    try:
        conn = httplib.HTTPConnection(server)
	conn.request("GET", "/"+emoncmspath+"/input/post.json?&node="+str(nodeid0)+"&json="+data+"&apikey="+apikey)
#	if inverter == 0: conn.request("GET", "/"+emoncmspath+"/input/post.json?&node="+str(nodeid0)+"&json="+data+"&apikey="+apikey)
#	if inverter == 1: conn.request("GET", "/"+emoncmspath+"/input/post.json?&node="+str(nodeid1)+"&json="+data+"&apikey="+apikey)
        response = conn.getresponse()
        conn.close()

    except Exception as e:
        print "error sending to emoncms...: " + str(e)
        return ''
    return 1

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
        return ''
    return 1


def serial_command(command):
    try:
	response = ""
	xmodem_crc_func = crcmod.predefined.mkCrcFun('xmodem')
	# wierd mistake in Axpert firmware - correct CRC is: 0xE2 0x0A
        if command == "POP02": command_crc = '\x50\x4f\x50\x30\x32\xe2\x0b\x0d\r'
        else: command_crc = command + unhexlify(hex(xmodem_crc_func(command)).replace('0x','',1)) + '\r'
	
	# Set the signal handler and a 5-second alarm 
	signal.signal(signal.SIGALRM, handler)
	signal.alarm(10)
	if len (command_crc) < 9:
	    time.sleep (0.35)
	    os.write(usb0, command_crc)
	else:
	    cmd1 = command_crc[:8]
	    cmd2 = command_crc[8:]
	    time.sleep (0.35)
	    os.write(usb0, cmd1)
	    time.sleep (0.35)
	    os.write(usb0, cmd2)
	    time.sleep (0.25)
	while True:
	    time.sleep (0.15)
	    r = os.read(usb0, 256)
	    response += r
	    if '\r' in r: break

    except Exception, e:
        print "error reading inverter...: " + str(e) + "Response :" + response
        data = ""
        if connection == "serial":
	    time.sleep(20)  # Problem with some USB-Serial adapters, they are some times disconnecting, 20 second helps to reconnect at same ttySxx
	    ser.open()
	    time.sleep(0.5)
            return ''

    signal.alarm(0)

    sys.stdout.write (command + " : ")
    sys.stdout.flush ()
    print response
    return response

def dynamic_control(load, mode1, mode2):
    # Automaticly adjust axpert inverter wakeup and standby mode
    #0:Line mode
    #1:Battery mode
    #2:Stand by mode
    #3:Fault mode
    #-1: Unknown mode
    # load > 1800 W -> Both inverters UP
    # load < 1800 W -> Master Running Slave in standby
    response = " no command "
    try:
	load = int(load)
	print "Load: " + str(load) + " MODE: " + str (mode1) + "|"  + str(mode2)
	if (load < 1800 and mode1 == 1 and mode2 == 1):
            print "Second inverter go to standby mode"
	    response = serial_command("MNCHGC1497")
        elif (load > 1800 and mode1 == 1 and mode2 == 2):
	    print "Second Inverter wake up"
            response = serial_command("MNCHGC1498")
        elif (load < 1800 and mode1 == 1 and mode2 == 2):
	    print "Second inverter already sleeping"
        elif (load > 1800 and mode1 == 1 and mode2 == 1):
	    print "Both inverter working"
        else:
	    print "No idea what to do"
        if "NAKss" in response:
	    print "Inverter didn't recognized command"
            return ''

    except Exception, e:
            print "error setting inverter mode...: " + str(e)
            return ''

    return 1

def main():
    while True:
# Inverter 0
        inverter = 0
	data, tmp, tmp2, tmp3 = get_data("QBV",inverter)
        if not data == "": send = send_data(data)
	data, tmp, tmp2, tmp3 = get_data("Q1",inverter)
        if not data == "": send = send_data(data)
	data, tmp, tmp2, tmp3 = get_data("QPIGS", inverter)
        if not data == "": send = send_data(data)
	data, parrallel_num, load, mode1 = get_data("QPGS0", inverter)
        if not data == "": send = send_data(data)

# Inverter 1
	if parrallel_num == "1":
	    inverter = 1
	    data, tmp, tmp2, mode2 = get_data("QPGS1", inverter)
    	    if not data == "": send = send_data(data)

# sleeping
	if (load > "0" and mode1 >= 0 and mode2 >= 0 and parrallel_num == "1"):
	    dynamic_control(load, mode1, mode2)

#        charge_current = set_charge_current ()
#        hdo_tmp_LT = read_hdo(68)       #Read emoncms feed id=68 = LowTarif
#        hdo_tmp_HT = read_hdo(69)       #Read emoncms feed id=69 = HighTarif
#        output_source_priority = get_output_source_priority()
#        charger_source_priority = get_charger_source_priority()
#        if not output_source_priority == "8":
#            if not charger_source_priority == "8":
#                if hdo_tmp_LT == "1":
#                    print "LT"  # electricity is cheap, so charge batteries from grid and hold them fully charged! important for Lead Acid Batteries Only!
#                    if not output_source_priority == "0":       # Utility First (0: Utility first, 1: Solar First, 2: SBU)
#                        set_output_source_priority(0)
#                    if not charger_source_priority == "2":      # Utility First (0: Utility first, 1: Solar First, 2: Solar+Utility, 3: Solar Only)
#                        set_charger_source_priority(2)
#                if hdo_tmp_HT == "1":
#                    print "HT"  # electricity is expensive, so supply everything from batteries not from grid
#                    if not output_source_priority == "2":       # Utility First (0: Utility first, 1: Solar First, 2: SBU)
#                        set_output_source_priority(2)
#                    if not charger_source_priority == "3":      # Utility First (0: Utility first, 1: Solar First, 2: Solar+Utility, 3: Solar Only)
#                        set_charger_source_priority(3)

if __name__ == '__main__':
    main()

