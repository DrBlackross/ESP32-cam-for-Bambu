# boot.py - Run on boot to start main application 
# this helps with the reboot command on the webpage, just serial in and control+C to break the loop till you >>> 
# then you can ampy --port /dev/ttyUSB0 put main.py (if you change settings), if not the boot.py will keep reloading
# just mash the crap out of CTRL+C a bunch LOL

import time
import machine
import sys

print("=" * 50)
print("ESP32-CAM Booting...")
print("=" * 50)

# Give system time to initialize
time.sleep(2)

print("Starting main application...")

# Attempt to import and run main.py
try:
    # This line loads your main application code from internal flash
    import main 
    
    # Check if main has a main() function and run it
    if hasattr(main, 'main'):
        main.main()
    else:
        print("Error: main.py doesn't have a main() function.")
        
except Exception as e:
    # This catches errors during the import or during main.main() execution
    print(f"\nCRITICAL BOOT ERROR: {e}")
    import sys
    sys.print_exception(e)

print("=" * 50)
print("If you see this, the application exited.")
print("Will soft reboot in 10 seconds to retry...")
print("=" * 50)

time.sleep(10)
machine.reset()
