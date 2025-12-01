## ESP32-cam-for-Bambu
Here is a script and instructions for using a ESP32Cam for snapping a series of shots when the arm sweeps to one end of the rail to compile later into a GIF, MP4, etc to post or share, BUT, only in linux :(

##### The case I will be using for my Bambu A1's Esp32-cam is
 https://makerworld.com/en/models/1220385-esp32-cam-case-kit-snap-fit-ball-joint?from=search#profileId-1497664

With just a simple microswitch (snagged from my defunct ender3) that is attached just above the swiper section of the X axis. There is a simple webserver in the script to "delete all" images, and a "delete all and reboot" with a directory listing on the page for when a print is done. Just pop out the Sdcard and pull off the images onto your desktop, etc. and edit, replace the sdcard back in the esp32cam and power cycle. I DID try to have it zip up and package all the images or allow the images in the directory be clicked on or downloaded and viewed, but that would eat up to many cycles and lag the monitoring of switch on GPIO13. 

The ESP32 was NOT having it (not with micropython).

So I followed this diagram for wiring minus the resistor

<img width="768" height="432" alt="image" src="https://github.com/user-attachments/assets/fb8bc05d-63a8-4428-aad2-013277347762" />

Where I simply took a microswitch that was wired in a N.O. setup as a limit switch for an axis (x,y,x) from my old printer and placed 1 wire to GND and the other wire to GPIO13 from the switch. Dronebotworkshop.com has a really good write up already on how to use the esp32-cam with a shutter button [here](https://dronebotworkshop.com/esp32-cam-microsd/).

I wrote this in MicroPython and tried to keep it simple, since python (albeit 'micro') is a heavy workload already for a esp32 MCU.

#### Step 1: Install Python and create virtual environment

##### Update system
    sudo apt update
    sudo apt install python3 python3-pip python3-venv

##### Create project directory
    mkdir ~/esp32-cam-project
    cd ~/esp32-cam-project

##### Create virtual environment
    python3 -m venv esp32cam-env

##### Activate virtual environment
    source esp32cam-env/bin/activate

#### Step 2: Install required tools
##### Install ampy and esptool
    pip install adafruit-ampy esptool.py pyserial

#### Step 3: Connect ESP32-CAM to FTDI

FTDI to ESP32-CAM wiring:

        FTDI TX  → ESP32 RX  (GPIO 3)
        FTDI RX  → ESP32 TX  (GPIO 1) 
        FTDI GND → ESP32 GND
        FTDI 5V  → NOT CONNECTED (use external 5V power)

Additional connections for programming:
        GPIO 0  → GND (during programming only!)
        External 5V → ESP32 5V pin

#### Step 4: Download MicroPython firmware

##### Download ESP32-CAM compatible MicroPython
##### I used the one with out bluetooth from this github repo or compile you own (not helping you there, compiling that was a pain without any success (for some reason))
    wget https://github.com/lemariva/micropython-camera-driver/blob/master/firmware/micropython_v1.21.0_camera_no_ble.bin

#### Step 5: Flash MicroPython firmware

##### Put ESP32 in programming mode:
##### 1. Connect GPIO 0 to GND
##### 2. Press RESET button
##### 3. Run erase command:

    esptool.py --chip esp32 --port /dev/ttyUSB0 erase_flash

##### Flash MicroPython (replace with actual filename):
    esptool.py --chip esp32 --port /dev/ttyUSB0 --baud 460800 write_flash -z 0x1000 micropython_v1.21.0_camera_no_ble.bin

#### After flashing:
##### 1. Disconnect GPIO 0 from GND
##### 2. Connect GPIO 0 to 3.3V (or leave floating, works best, just incase you have to do it over again lol)
##### 3. Press RESET button

#### Step 6: Test MicroPython
##### Open serial monitor to verify
    screen /dev/ttyUSB0 115200

##### Press RESET button
###### You should see:
    MicroPython v1.xx.x on ESP32 module
    Type "help()" for more information.
    >>>

This part is optional, but should work
##### Test camera (in REPL):
    import camera
    camera.init(0)
    buf = camera.capture()
    print("Camera works!", len(buf))

##### Exit screen: Ctrl+A then Ctrl+\

#### Step 7: Upload your main.py (fun part)

##### Edit your main.py file, downloaded from here
    nano main.py
  
Replace you SSID and WIFI_PASSWORD

    SSID = "YOUR_SSID"
    PASSWORD = "YOU_WIFI_PASSWORD"
  
Also you can change the name of the camera to something else instead of Bambu-Camera, so you can see it on your wifi

    DEVICE_NAME = "Bambu-Camera"

##### Upload using ampy (works best for me)
    ampy --port /dev/ttyUSB0 put main.py

##### Verify upload
    ampy --port /dev/ttyUSB0 ls

##### Should see this output...

        $ ampy --port /dev/ttyUSB0 ls
        /boot.py
        /main.py

#### Step 8: Test the system

  Power cycle ESP32-CAM (disconnect/reconnect 5V)
  Monitor boot with serial monitor:

*NOTE: This part I was using two terminals and when I would unplug the FTDI it would free up the ttyUSB0 so I could watch the startup process when I power cycled the ESP32cam. In terminal 1 I would use ampy to flash the micropython firmware, and also push the main.py over.. and (after unplugging the FTDI) in terminal 2 I would use screen as a serial monitor. Sooo... my process was complicated, see below.

1. terminal 1 flash mircopython.bin to the esp32cam, when there was no errors cut off the 5v power to the esp32 and power it back on. Then flash main.py with ampy to side load the main.py onto the esp32cam module, unplug FDTI from the usb port and uplug 5v power from the cam.

2. switch to terminal 2, plug in the FDTI to the usb port, then plug the 5v back in to the camera module and run...

    screen /dev/ttyUSB0 115200

  watch the boot up of the esp32cam module for WIFI, button presses, errors, etc..

3. repeat if needed

4. no errors, then access web interface at the IP shown in serial monitor

(I seriouly never had any 'fun' with a esp32-cam (Ai-Thinker, etc) for me and linux it always felt like a chore LOL)

Troubleshooting
If /dev/ttyUSB0 permission denied:

    sudo usermod -a -G dialout $USER

 Log out and log back in, or restart

 Or temporary fix:

    sudo chmod 666 /dev/ttyUSB0

If port not found:

 Check available ports

    ls /dev/ttyUSB*

 Check if device detected
 
    dmesg | grep tty

If upload fails:

    Make sure GPIO 0 is NOT connected to GND during upload

    Ensure stable 5V power supply

    Try different USB cable/port

Quick Reference Commands

### Always work within virtual environment (saves you from a headache of messing up your entire system)
    source esp32cam-env/bin/activate

### Common commands:
    esptool.py --port /dev/ttyUSB0 erase_flash                    # Erase
    esptool.py --port /dev/ttyUSB0 write_flash 0x1000 firmware.bin # Flash
    ampy --port /dev/ttyUSB0 put main.py                         # Upload code
    ampy --port /dev/ttyUSB0 ls                                  # List files
    screen /dev/ttyUSB0 115200                                   # Serial monitor

Your complete workflow:

    python3 -m venv esp32cam-env
    source esp32cam-env/bin/activate
    pip install adafruit-ampy esptool.py

Activate your programming session:
    
    source esp32cam-env/bin/activate

### Connect ESP32-CAM with GPIO 0 to GND
    esptool.py --port /dev/ttyUSB0 erase_flash
    esptool.py --port /dev/ttyUSB0 write_flash 0x1000 firmware.bin

### Disconnect GPIO 0 from GND

    ampy --port /dev/ttyUSB0 put main.py

This gives you a clean, reproducible setup for programming your ESP32-CAM! CAKE! (no)
After this........ you can then assemble your printed ["Esp32-camera case"](https://makerworld.com/en/models/1220385-esp32-cam-case-kit-snap-fit-ball-joint?from=search#profileId-1497664), power it up and mount your microswitch above the swiper with paper clips, painters tape, gum.... i don't know mounting is your call with the switch, enjoy. lol

I did use this ["poop catcher"](https://makerworld.com/en/models/451897-compact-poop-bucket-s-a1-a1-mini#profileId-416433) and added a rectangle cube on the top (just extended the surface area). 

![20251130_175958](https://github.com/user-attachments/assets/cbf6aab0-b14f-4a50-9c5f-b24a1c4c0ae1)

![20251130_175949](https://github.com/user-attachments/assets/287b0cff-47d6-48c2-a1bb-57b9a96bb250)


###### It should work as soon as i finish printing the extentions for the camera mount.

BUT, mount the switch on the modified poop catcher, screw in first front screw and the second one, but tighten the first down to hold the switch on the catcher. clip the catcher onto the printhead and home your axis... then after homing move the printhead all the way "-X" as far as it can go, then slide the switch gently to the right till it clicks, and lock it in place with that second screw as a set screw.

There is only 1 hole in the catcher to hold the switch in place.

