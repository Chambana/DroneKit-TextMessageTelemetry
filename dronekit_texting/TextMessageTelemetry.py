
# TextMessageTelemetryClass.py
# Summary:  Class for handling Text Messaging and communication with the GCS software on the ground station laptop
# ChamBana03@gmail.com

import base64
import pylzma
import socket
import time
from pymavlink import mavlinkv10 as mavlink
import multiprocessing
import binascii
import gsmmodem

class fifo(object):
    def __init__(self):
        self.buf = []
    def write(self, data):
        self.buf += data
        return len(data)
    def read(self):
        return self.buf.pop(0)

class LocalGCScommunication(object):

    def __init__(self, GCSport, debug_level):
        self._PortGCS = GCSport
        self._PortMe = 14555
        self._IP = "127.0.0.1"
        self._LocalGCSConnection = None
        self._DEBUG_LEVEL = debug_level
        f=fifo()
        self._MavlinkHelperObject = mavlink.MAVLink(f)


    def Connect(self):
        ######################################################################################
        #
        #  Summary:  Takes a mavlink message and sends it via UDP as a raw buffer to the Ground
        #  Control Statin software (e.g. APM planner 2) running on the local computer.
        #
        ######################################################################################

        self._LocalGCSConnection = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._LocalGCSConnection.setblocking(0)
        self._LocalGCSConnection.bind((self._IP, self._PortMe))


    def SendMavlinkMessageToGCS(self, message):
        ######################################################################################
        #
        #  Summary:  Takes a mavlink message and sends it via UDP as a raw buffer to the Ground
        #  Control Statin software (e.g. APM planner 2) running on the local computer.
        #
        ######################################################################################

        if self._LocalGCSConnection!=None:
            self._LocalGCSConnection.sendto(message.get_msgbuf(), (self._IP, self._PortGCS))
        else:
            self.Logger("Can't Send Mavlink Data without first initializing Socket", message_importance=1)


    def ReceiveMavlinkMessageFromGCS(self):
        ######################################################################################
        #
        #  Summary:  Grabs raw telemetry data via UDP from the Ground Control Station software
        #  (e.g. APM planner 2) running on the local computer and returns it as a Mavlink message.
        #  Typically you'd want to subsequently relay this data to the vehicle after processing
        #  it using, for example, the TextMessageTelemetry class function SendTextMessageTelemetry()
        #
        ######################################################################################

        if self._LocalGCSConnection!=None:
            BufferFromGCS = self._LocalGCSConnection.recv(1024)
            MavlinkMessage = self._MavlinkHelperObject.decode(BufferFromGCS)
            return MavlinkMessage
        else:
            self.Logger("Can't Receive Mavlink Data without first initializing Socket", message_importance=1)


    def Logger(self, message, message_importance):
        ######################################################################################
        #
        #  Summary:  Debug logger that prints output if the message importance meets the
        #  threshold set during class object initialization.  For example, if DEBUG_LEVEL is set
        #  to 4, all debug output is printed.  Recommended DEBUG_LEVEL value is 2.
        #
        ######################################################################################
        if message_importance < self._DEBUG_LEVEL:
            print message



class TextMessageTelemetry(object):
    def __init__(self, SendToPhoneNumber, LocalModemPath, baud=115200, DEBUG_LEVEL=2):
        self._RemotePhoneNumber = SendToPhoneNumber
        self._DEBUG_LEVEL = DEBUG_LEVEL
        self._ModemLocation = LocalModemPath
        f=fifo()
        self._MavlinkHelperObject = mavlink.MAVLink(f)
        self._ModemLock = multiprocessing.Lock()
        self._ModemConnection = gsmmodem.GsmModem(port=LocalModemPath, baudrate=baud)
        try:
            self._PrepareModem()
        except Exception, err:
            self.Logger("Modem Init failed"+str(err), message_importance=1)
            self._ModemConnection=None

    def _PrepareModem(self):
        ######################################################################################
        #
        #  Summary:  Initializes modem.  Disables modem echoing our input and sets the modem
        #  to text mode.
        #
        ######################################################################################
        try: 
            self._ModemLock.acquire()
            self._ModemConnection.connect()
            self._ModemConnection.smsTextMode=True
            self._ModemLock.release()
        except Exception, e:
            self.Logger("Prepare Modem failed"+str(e), message_importance=1)
            self._ModemConnection=None

    def Logger(self, message, message_importance):
        ######################################################################################
        #
        #  Summary:  Debug logger that prints output if the message importance meets the
        #  threshold set during class object initialization.  For example, if DEBUG_LEVEL is set
        #  to 4, all debug output is printed.  Recommended DEBUG_LEVEL value is 2.
        #
        ######################################################################################
        if message_importance < self._DEBUG_LEVEL:
            print message

    def SendTextMessageTelemetry(self, ListOfMavlinkMessages, blocking=False):
        ######################################################################################
        #
        #  Summary:  Takes a list of mavlink messages, uses class helper functions to compress
        #  them with LZMA compression, encode them into Base64, and action the modem to transmit
        #  the telemetry via SMS.
        #  NOTE:  This function requires your compressed/encoded buffer to be <160 characters.
        #  It's trivial (and inefficient) to just check the length of your proposed text msg by
        #  checking the length returned by helper function ConvertMavlinkToTextMessage()
        #
        ######################################################################################

        if blocking==True:
            self._ModemLock.acquire(True)
        else:
            self.Logger("Non-blocking call to SendTextMessage..", message_importance=1)
            ret=self._ModemLock.acquire(False)
            if ret==False:
                self.Logger("Modem is not available...dumping outbound", message_importance=1)
                return False
            else:
                self.Logger("Modem available, sending.....", message_importance=1)

        OutgoingBuffer = self.ConvertMavlinkToTextMessage(ListOfMavlinkMessages)
        if len(OutgoingBuffer)>160:
            self.Logger("Can't send more than 160 characters per text message", message_importance=1)
            return False

        self.Logger("Sending SMS...", message_importance=1)
        try:
            result = self._ModemConnection.sendSms(self._RemotePhoneNumber, OutgoingBuffer)
            self._ModemLock.release()
            return result
        except Exception, e:
            self.Logger("Exception during sendSMS()"+str(e), message_importance=1)
            self._ModemLock.release()
            return None
	
    def GetTextMessageTelemetry(self, blocking=True):
        ######################################################################################
        #
        #  Summary:  Requests all the unread text messages from the modem, parses the modem output into
        #  a list of text buffers (each containing one text message's payload), and then uses class helper
        #  functions to (in order):
        #           1) decode each text message from Base64
        #           2) decompress each text message with LZMA compression
        #           3) dissect each text message into multiple Mavlink messages
        #  Finally, function returns a list of Mavlink messages compiled from all unread text messages
        #
        ######################################################################################

        if blocking==True:
            self._ModemLock.acquire(True)
        else:
            ret=self._ModemLock.acquire(False)
            if ret==False:
                return False
        try:
            ListOfTextMessages = self._ModemConnection.listStoredSms()
            ListOfMavlinkMessages=[]
            for TextMessage in ListOfTextMessages:
                #text message buffer contains multiple mavlink msgs wrapped in LZMA wrapped in Base64
                MavlinkMessages = self.ConvertTextMessageToMavlink(TextMessage.text)
                ListOfMavlinkMessages+=MavlinkMessages
            self._ModemLock.release()
            return ListOfMavlinkMessages
        except Exception, e:
            self.Logger("Exception during GetTextMessage: "+str(e), message_importance=1)
            self._ModemLock.release()

    def WaitForResponse(self, StringToWaitFor, timeout=10):
        ######################################################################################
        #
        #  Summary:  Helper function to parse modem responses looking for an expected response
        #  contained in the input value "StringToWaitFor".  Times out if the response isn't returned.
        #  This function is mostly used to make sure we get the expected "OK" from the modem before we
        #  we continue on to the next modem command.
        #
        ######################################################################################
        starttime = time.time()

        while (time.time() - starttime) < timeout:
            ret = self._ModemConnection.readline()
            if StringToWaitFor in ret:
                return True
            time.sleep(1)
        self.Logger("Didn't get expected response from modem", message_importance=1)


    def ConvertMavlinkToTextMessage(self, ListOfMavlinkMessages):
        ######################################################################################
        #
        #  Summary:  Take a list of mavlink messages, converts them to a single text buffer, crushes
        #  the buffer size down with LZMA compression, encodes the compressed buffer in Base64, and
        #  returns the encoded buffer.  Base64 is used to make the text buffer url/sms/email safe.
        #
        ######################################################################################

        BufferOfMavlinkMessages = ""
        for message in ListOfMavlinkMessages:
            MessageInASCII = binascii.hexlify(message.get_msgbuf())
            BufferOfMavlinkMessages+=MessageInASCII

        CompressedMavlinkBuffer = pylzma.compress(BufferOfMavlinkMessages)
        EncodedMavlinkBuffer = base64.b64encode(CompressedMavlinkBuffer)
        TestMavlinkBuffer = base64.b64encode(BufferOfMavlinkMessages)  #debug
        return EncodedMavlinkBuffer


    def ConvertTextMessageToMavlink(self, TextMessage):
        ######################################################################################
        #
        #  Summary:  Takes a text message's payload text, unBase64's it, decompresses it with LZMA,
        #  parses out the multiple Mavlink messages within the buffer, and a returns a list of
        #  decoded Mavlink messages.  Base64 is used to make the text buffer url/sms/email safe.
        #
        ######################################################################################
        try:
            DecodedMavlinkBuffer = base64.b64decode(TextMessage)
            DecompressedMavlinkBuffer = pylzma.decompress(DecodedMavlinkBuffer)
            ListOfMavlinkMessages = self._MavlinkHelperObject.parse_buffer(DecompressedMavlinkBuffer)
            return ListOfMavlinkMessages
        except Exception, e:
            self.Logger("Exception in ConvertTextMessagetoMavlink: "+str(e), message_importance=1)
            return None


    def PurgeIncomingTextMessages(self, timeout=90, blocking=True):
        ######################################################################################
        #
        #  Summary:  Wipes the modem's SMS memory until SMS's queued/bottlenecked on the network
        #  stop getting downloaded.  This function is useful for when your groundstation SMS processing
        #  fails for some reason, but your remote vehicle continues to send -- filling up your modem
        #  memory and leaving hundreds of SMS's backed up on the GSM network waiting to be downloaded.
        #
        ######################################################################################

        if blocking==True:
            self._ModemLock.acquire(True)
        else:
            ret=self._ModemLock.acquire(False)
            if ret==False:
                return False

        starttime=time.time()
        while (time.time()-starttime) < timeout:
            self._ModemConnection.write("AT+CMGL(0,4)\r\n")  #wipe modem memory
            self.WaitForResponse("OK")
            time.sleep(5)                                    #allow time for modem to receive any waiting SMS's
            self._ModemConnection.write('AT+CMGD="ALL"\r\n') #check if modem SMS memory is empty
            ret=self._ModemConnection.readline()
            if ret=="OK":                                    #it's empty, purge is complete
                self._ModemLock.release()
                return True
            else:                                            #there were SMS's bottlenecked on network, purge again
                continue

        self._ModemLock.release()
        return False





