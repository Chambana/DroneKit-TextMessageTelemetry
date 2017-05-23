Text Messaging Telemetry for DroneKit
Control Rovers, Copters, or Planes via inexpensive text messaging from within DroneKit

http://diydrones.com/profiles/blogs/text-message-telemetry-with-dronekit

Dependencies:  

    -- pip install python-gsmmodem
    
    -- pip install pymavlink
    
    -- pip install pylzma
        
    -- pip install dronekit


How to launch text messaging telemetry between your APM Rover and Ground Station computer:

    --Copy project files to your vehicle's companion computer (e.g. Raspberry Pi) and your laptop.
            --pip install dronekit-textmessaging
    
    --On your ground station computer enter the following command:  
    
        LaunchTelemetry.py -ground
        
    --On the vehicle's companion computer, launch the script from DroneKit:
    
        LaunchTelemetry.py -vehicle (NOTE: make sure to have AUTOPILOT_PATH set appropriately)
        

Supported Hardware/Software Configuration:

    * Ground Station
        * Mac laptop/desktop
        * APM Planner 2 software
        * Sierra 313u (AT&T 313u) GSM modem
        * AT&T's $2/day pay-as-you-go unlimited texting plan
    
    * Vehicle
        * Raspberry Pi "companion computer" connected to autopilot via serial or USB cable
        * APM 2.6 or Pixhawk autopilot
        * Sierra 313u (AT&T 313u) GSM modem
        * AT&T's $2/day pay-as-you-go unlimited texting plan


Changelog: 

    -- 5 Sep 2015 -- Under Development

    -- 14 Nov 2015 -- Updated to DroneKit version 2

    -- 21 Nov 2015 -- Created pip package

License information:

    -- Copyright (C) 2015 Chambana

    -- License: GNU Lesser General Public License, version 3 or later; see COPYING included in this archive for details.
