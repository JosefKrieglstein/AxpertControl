#! /usr/bin/python

import serial, time, sys, string
import os
import re
import crcmod
from binascii import unhexlify

#Commands with CRC cheats
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

#nefunkcni
#QPIRI          # Device rating information inquiry - nefunguje
#PPCP000        # Setting parallel device charger priority: UtilityFirst - nefunguje
#PPCP001        # Setting parallel device charger priority: SolarFirst - nefunguje
#PPCP002        # Setting parallel device charger priority: OnlySolarCharging - nefunguje

ser = serial.Serial()
ser.port = "/dev/ttyUSB0"
ser.baudrate = 2400
ser.bytesize = serial.EIGHTBITS     #number of bits per bytes
ser.parity = serial.PARITY_NONE     #set parity check: no parity
ser.stopbits = serial.STOPBITS_ONE  #number of stop bits
#ser.timeout = none                 #block read
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

try:
    ser.flushInput()            #flush input buffer, discarding all its contents
    ser.flushOutput()           #flush output buffer, aborting current output and discard all that is in buffer
    command = "POP0088"
    print command
    xmodem_crc_func = crcmod.predefined.mkCrcFun('xmodem')
    print hex(xmodem_crc_func(command))
    print hex(xmodem_crc_func(command)).replace("0x","",1)
    command_crc = command + unhexlify(hex(xmodem_crc_func(command)).replace('0x','',1)) + '\x0d'
    print command_crc

#    command_crc = '\x50\x4f\x50\x30\x32\xe2\x0b\x0d'
    ser.write(command_crc)
    response = ser.readline()
    print response
    response_hex = ':'.join(hex(ord(x))[2:] for x in response)
    print response_hex
    ser.close()

except Exception, e:
    print "error reading inverter...: " + str(e)
    exit()
