#!/usr/bin/env python

# LaunchTelemetry.py
# Summary:  Launches Text Message Telemetry from within DroneKit
# Chambana03@gmail.com

import sys, os
sys.path.append(os.getcwd())
import time
from dronekit_texting.TextMessageTelemetry import LocalGCScommunication, TextMessageTelemetry
import multiprocessing
from dronekit import connect
import threading



######################################################################################
#
#  CONFIGURATION
#
######################################################################################

#MANDATORY CONFIGURATION
AM_I_GROUNDSTATION_OR_VEHICLE = "VEHICLE"

#GROUND CONFIGURATION
GROUNDSTATION_PHONE_NUMBER = "7031234567"
GROUNDSTATION_MODEM_PATH = '/dev/tty.sierra03'
GCS_PORT = 14550
GROUNDSTATION_MODEM_BAUD = 115200

#VEHICLE CONFIGURATION
VEHICLE_PHONE_NUMBER = "7031234567"
AUTOPILOT_PATH = '/dev/ttyACM0'
VEHICLE_MODEM_PATH = '/dev/tty.netgear03'
SECONDS_BETWEEN_MAILBOX_CHECKS = 5  #how often does the vehicle grab the modem to check for new commands
VEHICLE_MODEM_BAUD = 115200

#GLOBALS
MessageQueue = []
MessageQueueLock = threading.Lock()




######################################################################################
#
#  Summary:  Run this on your ground station laptop
#
######################################################################################
def RunAsGroundStation():

    def GCSListener():
        while 1:
            GCScommand=LocalGCSconnection.ReceiveMavlinkMessageFromGCS()
            if GCScommand.get_type()=="HEARTBEAT":
                #filter ground-to-vehicle heartbeats to limit SMS's
                continue
            else:
                list=[]
                list.append(GCScommand)
                TextMessagingConnection.SendTextMessageTelemetry(list, blocking=True)  #prioritize outgoing commands by blocking

    def HeartbeatRepeater():
        if LastIncomingHeartbeat!=None:
            LocalGCSconnection.SendMavlinkMessageToGCS(LastIncomingHeartbeat)
            time.sleep(0.5)  #the GCS wants to be fed a vehicle heartbeat something like every second or it complains

    try:
        print "Verifying initialization values..."
        print "  -GROUNDSTATION PHONE NUMBER =",GROUNDSTATION_PHONE_NUMBER
        print "  -VEHICLE PHONE NUMBER =",VEHICLE_PHONE_NUMBER
        print "  -GROUNDSTATION MODEM PATH =", GROUNDSTATION_MODEM_PATH
        print "  -GROUNDSTATION MODEM BAUD =", GROUNDSTATION_MODEM_BAUD
        print "  -GCS SOFTWARE (E.G. MISSION PLANNER) LISTENING ON PORT", GCS_PORT
        sys.stdout.write("Are these values correct? (y/n) ")
        response = raw_input().lower()
        if response == 'n':
            print "Please input the correct values in LaunchTelemetry.py"
            return
        elif response == 'y':
            print "launching telemetry..."
        else:
            print "invalid keystroke"
            return

        LastIncomingHeartbeat = None  #Cached copy of last received heartbeat from vehicle
        LocalGCSconnection = LocalGCScommunication(GCSport=GCS_PORT, debug_level=4)
        TextMessagingConnection = TextMessageTelemetry(VEHICLE_PHONE_NUMBER, GROUNDSTATION_MODEM_PATH, VEHICLE_MODEM_BAUD, DEBUG_LEVEL=4)
        TextMessagingConnection.PurgeIncomingTextMessages()

        LocalGCSconnection.Connect()

        GCSListenerProcess = multiprocessing.Process(target=GCSListener)
        GCSListenerProcess.start()
        HeartbeatFakerProcess = multiprocessing.Process(target=HeartbeatRepeater)
        HeartbeatFakerProcess.start()
    except Exception, error:
        print "Exception during Groundstation comms initialization: ", str(error)
        quit()

    print "Launching Telemetry Loop"
    while 1:
        try:
            ListOfIncomingMavlinkMessages = TextMessagingConnection.GetTextMessageTelemetry(blocking=False)
            for message in ListOfIncomingMavlinkMessages:
                LocalGCSconnection.SendMavlinkMessageToGCS(message)
                if message.get_type()=="HEARTBEAT":
                    LastIncomingHeartbeat = message
            time.sleep(0.5)  #sleep to avoid hammering the GSM network
        except Exception, error:
            print "Exception Receiving Telemetry: ", str(error)
            #pass



######################################################################################
#
#  Summary:  Run this on the vehicle
#
######################################################################################
def RunAsVehicle():

    def GroundListener():
        LastMailboxCheck = time.time()
        while 1:
            if (time.time() - LastMailboxCheck) > SECONDS_BETWEEN_MAILBOX_CHECKS:
                CommandMessageFromGround = TextMessagingConnection.GetTextMessageTelemetry()
                if CommandMessageFromGround!=None:
                    AutopilotConnection.write(CommandMessageFromGround.get_msgbuf())
                LastMailboxCheck=time.time()


    def AutopilotIncomingMessageHandler(MavlinkMessage):
        try:
            global MessageQueue
            global MessageQueueLock
            if MavlinkMessage==None:
                return
            if MavlinkMessage.get_type()=="BAD_DATA":
                return
            print "Received:", MavlinkMessage.get_type(), "| Current MessageQueue length:", len(MessageQueue)

            if "ACK" in MavlinkMessage.get_type():
                #critical message, block until added to outgoing queue
                print "Critical outgoing message, blocking.."
                MessageQueueLock.acquire(True)
            elif MessageQueueLock.acquire(False)==False:
                print "MessageQueue was LOCKED, returning.."
                return #another callback is processing a msg from autopilot.  Drop this message
            else:
                print "MessageQueue was UNLOCKED. processing msg.."

            MessageQueue.append(MavlinkMessage)
            #print "MessageQueue len AFTER:", len(MessageQueue)
            if len(TextMessagingConnection.ConvertMavlinkToTextMessage(MessageQueue))>160:
                print "MessageQueue Over 160, sending!"
                MessageQueue.pop()
                #TODO:  This should probably be a thread
                block=False
                for msg in MessageQueue:
                    #check for critical msgs
                    if "ACK" in msg.get_type():
                        block=True
                        break
                TextMessagingConnection.SendTextMessageTelemetry(ListOfMavlinkMessages=MessageQueue,blocking=block)
                MessageQueue=[]
                MessageQueue.append(MavlinkMessage)
            MessageQueueLock.release()
        except Exception, e:
            print "Exception in Pixhawk callback", str(e)
            if MessageQueueLock.locked():
                MessageQueueLock.release()


    try:
        print "Verifying initialization values..."
        print "  -GROUNDSTATION PHONE NUMBER =",GROUNDSTATION_PHONE_NUMBER
        print "  -VEHICLE PHONE NUMBER =",VEHICLE_PHONE_NUMBER
        print "  -VEHICLE MODEM PATH =", VEHICLE_MODEM_PATH
        print "  -VEHICLE MODEM BAUD =", VEHICLE_MODEM_BAUD
        print "  -AUTOPILOT_PATH =", AUTOPILOT_PATH
        print "  -SECONDS BETWEEN MAILBOX CHECKS =", SECONDS_BETWEEN_MAILBOX_CHECKS

        sys.stdout.write("Are these values correct? (y/n) ")
        response = raw_input().lower()
        if response == 'n':
            print "Please input the correct values in LaunchTelemetry.py"
            return
        elif response == 'y':
            print "launching telemetry..."
        else:
            print "invalid keystroke"
            return


        #Start DroneKit ver.2
        vehicle = connect(AUTOPILOT_PATH, wait_ready=True)

        print "DroneKit init:  ", vehicle

        TextMessagingConnection = TextMessageTelemetry(GROUNDSTATION_PHONE_NUMBER, VEHICLE_MODEM_PATH, GROUNDSTATION_MODEM_BAUD, DEBUG_LEVEL=4)
        TextMessagingConnection.PurgeIncomingTextMessages()
        print "Text Messaging init: ", TextMessagingConnection

        time.sleep(3)
        vehicle.set_mavlink_callback(AutopilotIncomingMessageHandler)
        
        GroundCommandListenerProcess = multiprocessing.Process(target=GroundListener)
        GroundCommandListenerProcess.start()


    except Exception, error:
        print "Exception during Vehicle comms initialization: ", str(error)
        quit()

    while 1:
        #TODO:  INSERT YOUR DRONEKIT CODE HERE (OR DON'T TO JUST USE TEXT MESSAGING TELEMETRY)
        pass



#Process Command Line arguments
if len(sys.argv) > 1:   #if we got a command line argument (setting the mode to be vehicle or groundstation)
    if sys.argv[1]=="-vehicle":
        AM_I_GROUNDSTATION_OR_VEHICLE = "VEHICLE"
    if sys.argv[1]=="-ground":
        AM_I_GROUNDSTATION_OR_VEHICLE = "GROUNDSTATION"
else:
    AM_I_GROUNDSTATION_OR_VEHICLE = "VEHICLE"  #default to vehicle with no cmd line argument


if AM_I_GROUNDSTATION_OR_VEHICLE == "GROUNDSTATION":
    print "\n\nLaunching Ground Station Comms..."
    RunAsGroundStation()

if AM_I_GROUNDSTATION_OR_VEHICLE == "VEHICLE":
    print "\n\nLaunching Vehicle Comms..."
    RunAsVehicle()













