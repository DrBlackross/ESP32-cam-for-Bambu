import network
import camera
import socket
import time
import os
import machine
import gc
import utime
import uos

# Configuration
SSID = "YOUR_WIFI"
PASSWORD = "YOUR_WIFI_PASSWORD"
SHUTTER_PIN = 13
DEVICE_NAME = "Bambu-Camera"

# --- CAMERA QUALITY/BRIGHTNESS CONFIGURATION ---
# The named constants (UXGA, SXGA, XGA) are not supported. 
CAMERA_RESOLUTION = 10 # XGA (1024x768) is index 10
# JPEG Quality: 8 (High Quality)
JPEG_QUALITY = 8 
# ---------------------------------------------

# === SD CARD FIX: FILE SYSTEM DEFINITIONS ===
# Use /sd as the mount point, as set in previous successful boot logs.
SD_MOUNT_POINT = "/sd"
PHOTO_FOLDER_NAME = "photos"
LOG_FOLDER_NAME = "logs"

# Full Paths (Must be used for all file operations)
PHOTO_FOLDER = SD_MOUNT_POINT + "/" + PHOTO_FOLDER_NAME
LOG_FOLDER = SD_MOUNT_POINT + "/" + LOG_FOLDER_NAME
# ===============================================

# Initialize
shutter = machine.Pin(SHUTTER_PIN, machine.Pin.IN, machine.Pin.PULL_UP)
picture_count = 0
last_shutter_state = None
# Removed flash_led variable as requested

def get_formatted_time():
    """Get formatted time string for MicroPython"""
    try:
        t = utime.localtime()
        # Format: Wed Dec 3 10:30:45 2025
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        weekday = days[t[6]]
        month = months[t[1] - 1]
        day = t[2]
        hour = t[3]
        minute = t[4]
        second = t[5]
        year = t[0]
        
        return f"{weekday} {month} {day:2d} {hour:02d}:{minute:02d}:{second:02d} {year}"
    except:
        return "Time unavailable"

# === SD CARD FIX: MOUNT FUNCTION (Re-added) ===
def mount_sd_card():
    """Initializes and mounts the SD card to the defined mount point."""
    print("Attempting to mount SD Card...")
    try:
        # Use machine.SDCard() for ESP32-CAM's internal SDMMC controller pins
        sd = machine.SDCard() 
        uos.mount(sd, SD_MOUNT_POINT)
        print(f"SD Card mounted successfully at {SD_MOUNT_POINT}")
        return True
    except Exception as e:
        print(f"CRITICAL: SD Card Mount Failed: {e}")
        return False
# =====================================

def setup_filesystem():
    """Setup proper folder structure on SD card."""
    print("\n Setting up filesystem on SD Card...")
    
    try:
        # List contents of the SD card root, not the flash root (/)
        sd_root_contents = uos.listdir(SD_MOUNT_POINT)

        # Create photos folder if it doesn't exist
        if PHOTO_FOLDER_NAME not in sd_root_contents:
            uos.mkdir(PHOTO_FOLDER) # Use full path
            print(f"  Created folder: {PHOTO_FOLDER}")
        else:
            print(f"  Photos folder exists: {PHOTO_FOLDER}")
            
        # Create logs folder
        if LOG_FOLDER_NAME not in sd_root_contents:
            uos.mkdir(LOG_FOLDER) # Use full path
            print(f"  Created folder: {LOG_FOLDER}")
        else:
            print(f"  Logs folder exists: {LOG_FOLDER}")
        
        # Count existing photos
        global picture_count
        try:
            # List contents of the photo folder on the SD card
            photo_files = [f for f in uos.listdir(PHOTO_FOLDER) if f.endswith('.jpg')]
            photo_files.sort()
            
            if photo_files:
                # Find the highest number (logic updated to find the 4-digit number)
                max_num = -1
                for f in photo_files:
                    try:
                        if f.startswith('photo_') and f.endswith('.jpg'):
                            # Extract the number from 'photo_NNNN_...'
                            num_str = f[6:10]
                            num = int(num_str)
                            if num > max_num:
                                max_num = num
                    except:
                        pass
                
                picture_count = max_num + 1 if max_num >= 0 else 0
                print(f"  Found {len(photo_files)} existing photos")
                print(f"  Next photo number: {picture_count}")
            else:
                print(f"  No existing photos found")
                picture_count = 0
        except Exception as e:
            print(f"  Note: Could not list photos: {e}")
            picture_count = 0
            
        return True
        
    except Exception as e:
        print(f" Filesystem setup failed: {e}")
        return False

def connect_wifi():
    sta_if = network.WLAN(network.STA_IF)
    sta_if.active(True)
    sta_if.config(dhcp_hostname=DEVICE_NAME)
    if not sta_if.isconnected():
        print('Connecting to WiFi as', DEVICE_NAME, '...')
        sta_if.connect(SSID, PASSWORD)
        while not sta_if.isconnected():
            time.sleep(0.5)
            print('.', end='')
        print()
    print('WiFi connected!')
    print('Device Name:', DEVICE_NAME)
    print('IP Address:', sta_if.ifconfig()[0])

def init_camera():
    """
    Initializes the camera, sets resolution, quality, and attempts to set 
    gain ceiling to fix the dark image issue, avoiding unsupported functions.
    """
    try:
        # 1. Init with PSRAM for high resolution
        camera.init(0, format=camera.JPEG, fb_location=camera.PSRAM) 
        
        # 2. Set Resolution and Quality (using numeric indices)
        camera.framesize(CAMERA_RESOLUTION) 
        camera.quality(JPEG_QUALITY)
        
        # 3. CRITICAL BRIGHTNESS BOOST: Set high gain ceiling (Index 5 is 16X gain)
        # This is the single most important setting for brightness boost.
        camera.gainceiling(5) 
        
        # Removed: exposure_ctrl, whitebalance, gain_ctrl

        print(f"Camera initialized with Resolution Index {CAMERA_RESOLUTION} (1024x768) and Quality: {JPEG_QUALITY}")
        print("Attempting to set gainceiling to 16X for brighter images.")
        return True
    except Exception as e:
        print("Camera init failed:", e)
        # If this is still an AttributeError, we know gainceiling is missing too.
        return False

def take_photo():
    global picture_count
    try:
        print("\n" + "=" * 40)
        print(" Capturing photo...")
        
        buf = camera.capture()
        print(f"  Captured: {len(buf)} bytes")
        
        current_time = utime.localtime()
        date_str = "{:04d}-{:02d}-{:02d}".format(current_time[0], current_time[1], current_time[2])
        time_str = "{:02d}-{:02d}-{:02d}".format(current_time[3], current_time[4], current_time[5])
        
        filename = f"photo_{picture_count:04d}_{date_str}_{time_str}.jpg"
        # Use full path which includes the /sd mount point (CRITICAL FIX)
        full_path = PHOTO_FOLDER + "/" + filename 
        
        print(f"  Saving as: {filename}")
        print(f"  Full path: {full_path}")
        
        # Save the file
        with open(full_path, "wb") as f:
            f.write(buf)
        
        # Force file to disk - This is critical for SD card reliability
        sync_filesystem()
        
        gc.collect()
        
        try:
            # os.stat now checks the file on the mounted SD card
            file_size = os.stat(full_path)[6]
            if file_size == len(buf):
                print(f" Photo saved successfully!")
                print(f"   File: {filename}")
                print(f"   Size: {file_size} bytes")
                print(f"   Path: {full_path}")
                
                save_photo_log(filename, len(buf), picture_count)
                
                picture_count += 1
                return True
            else:
                print(f" File size mismatch: {file_size} != {len(buf)}")
                return False
                
        except Exception as e:
            print(f" Could not verify file: {e}")
            return False
            
    except Exception as e:
        print(f" Photo capture failed: {e}")
        return False
    finally:
        print("=" * 40)

def save_photo_log(filename, size, photo_num):
    """Save a log entry for the photo"""
    try:
        current_time = utime.localtime()
        timestamp = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
            current_time[0], current_time[1], current_time[2],
            current_time[3], current_time[4], current_time[5]
        )
        
        log_entry = f"{timestamp} | Photo #{photo_num:04d} | {filename} | {size} bytes\n"
        
        # LOG_FOLDER contains the /sd mount point (CRITICAL FIX)
        log_file = LOG_FOLDER + "/photos.log"
        with open(log_file, "a") as f:
            f.write(log_entry)
            
        print(f" Log entry saved")
        
    except Exception as e:
        print(f"Could not save log: {e}")

def list_photos():
    """List all photos in the photos folder"""
    try:
        # List files in the SD card photo folder (CRITICAL FIX)
        files = uos.listdir(PHOTO_FOLDER)
        photos = [f for f in files if f.endswith('.jpg')]
        photos.sort()
        return photos
    except Exception as e:
        print(f"Error listing photos: {e}")
        return []

def get_photo_count():
    """Get count of photos"""
    photos = list_photos()
    return len(photos)

def get_total_file_size():
    """Get total size of all photos"""
    total_size = 0
    photos = list_photos()
    for photo in photos:
        try:
            # Use the full path for os.stat (CRITICAL FIX)
            full_path = PHOTO_FOLDER + "/" + photo
            size = os.stat(full_path)[6]
            total_size += size
        except:
            pass
    return total_size

def format_sd_card():
    """Format SD card by deleting all files and folders on the SD card (mounted at /sd)"""
    print("\n" + "=" * 60)
    print("  FORMATTING SD CARD - ALL DATA WILL BE LOST!")
    print("  WARNING: This only deletes contents of the /sd mount point.")
    print("=" * 60)
    
    deleted_count = 0
    error_count = 0
    
    try:
        # Iterate over the contents of the SD card mount point (CRITICAL FIX)
        items = uos.listdir(SD_MOUNT_POINT)
        print(f"Found {len(items)} items on SD card to check")
        
        for item in items:
            try:
                full_path = SD_MOUNT_POINT + '/' + item
                
                is_dir = False
                try:
                    # Check if it's a directory by trying to list its contents
                    uos.listdir(full_path)
                    is_dir = True
                except OSError:
                    is_dir = False
                    
                if is_dir:
                    # Delete files inside directory first
                    sub_items = uos.listdir(full_path)
                    for sub_item in sub_items:
                        try:
                            uos.remove(full_path + '/' + sub_item)
                            deleted_count += 1
                            print(f"    Deleted file: {sub_item}")
                        except Exception as e:
                            error_count += 1
                    
                    # Now delete the directory
                    uos.rmdir(full_path)
                    deleted_count += 1
                    print(f"  Deleted directory: {item}")
                    
                else:
                    # It's a file, delete it
                    uos.remove(full_path)
                    deleted_count += 1
                    print(f"  Deleted file: {item}")
                    
            except Exception as e:
                error_count += 1
                print(f"  Error with {item}: {e}")
        
        # Now ensure our folders exist (create if they don't)
        for folder in [PHOTO_FOLDER, LOG_FOLDER]:
            try:
                uos.mkdir(folder)
                print(f"  Created folder: {folder}")
            except OSError as e:
                if "EEXIST" in str(e) or "17" in str(e):
                    print(f"  Folder already exists: {folder}")
                else:
                    raise e
        
        global picture_count
        picture_count = 0
        
        print(f"\n Format complete!")
        print(f"   Deleted: {deleted_count} items")
        print(f"   Kept: boot.py, main.py (on internal flash)")
        if error_count > 0:
            print(f"   Errors: {error_count}")
        
        return True, deleted_count, error_count
        
    except Exception as e:
        print(f" Format failed: {e}")
        return False, deleted_count, error_count

def web_page():
    photos = list_photos()
    photo_count = len(photos)
    total_size_kb = get_total_file_size() // 1024
    current_time = get_formatted_time()
    
    recent_photos = photos[-10:] if len(photos) > 10 else photos
    recent_photos.reverse()
    
    # ... (HTML content remains the same)
    html = f"""<html>
    <head><title>{DEVICE_NAME} - Photo Station</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 900px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }}
        h2 {{ color: #444; margin-top: 25px; }}
        .stats {{ 
            background: #e8f5e9; 
            padding: 15px; 
            border-radius: 5px; 
            margin: 15px 0;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 10px;
        }}
        .stat-item {{ text-align: center; }}
        .stat-value {{ font-size: 24px; font-weight: bold; color: #4CAF50; }}
        .stat-label {{ font-size: 14px; color: #666; }}
        .shutter-btn {{ 
            background: #4CAF50; 
            color: white; 
            border: none; 
            padding: 15px 30px; 
            font-size: 20px; 
            border-radius: 5px; 
            cursor: pointer;
            display: block;
            margin: 20px auto;
            width: 100%;
            max-width: 300px;
        }}
        .shutter-btn:hover {{ background: #45a049; }}
        .action-btn {{ 
            background: #2196F3; 
            color: white; 
            border: none; 
            padding: 10px 15px; 
            border-radius: 4px; 
            cursor: pointer;
            margin: 5px;
        }}
        .action-btn:hover {{ opacity: 0.8; }}
        .sync-btn {{ 
            background: #FF9800; 
            color: white; 
            border: none; 
            padding: 10px 15px; 
            border-radius: 4px; 
            cursor: pointer;
            margin: 5px;
        }}
        .photo-list {{ 
            max-height: 400px; 
            overflow-y: auto; 
            border: 1px solid #ddd; 
            padding: 15px; 
            border-radius: 5px;
            margin: 15px 0;
        }}
        .photo-item {{ 
            padding: 10px; 
            border-bottom: 1px solid #eee; 
            display: flex; 
            justify-content: space-between;
            align-items: center;
        }}
        .photo-item:last-child {{ border-bottom: none; }}
        .photo-name {{ font-family: monospace; }}
        .photo-size {{ color: #666; font-size: 14px; }}
        .warning {{ 
            background: #fff3cd; 
            border: 1px solid #ffc107;
            color: #856404;
            padding: 15px;
            border-radius: 5px;
            margin: 15px 0;
        }}
        .critical-warning {{ 
            background: #f8d7da; 
            border: 2px solid #dc3545;
            color: #721c24;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
            font-weight: bold;
        }}
        .folder-path {{ 
            background: #e3f2fd; 
            padding: 10px; 
            border-radius: 5px; 
            margin: 10px 0;
            font-family: monospace;
        }}
    </style>
    </head>
    <body>
        <div class="container">
            <h1>{DEVICE_NAME} - Photo Station</h1>
            
            <div class="critical-warning">
                CRITICAL: ALWAYS USE "SYNC FILESYSTEM" BEFORE POWERING OFF!<br>
                Then wait 10 seconds before removing power to prevent corruption.
            </div>
            
            <div class="stats">
                <div class="stat-item">
                    <div class="stat-value">{photo_count}</div>
                    <div class="stat-label">Photos Taken</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{total_size_kb} KB</div>
                    <div class="stat-label">Total Size</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{picture_count:04d}</div>
                    <div class="stat-label">Next Photo #</div>
                </div>
            </div>
            
            <div class="folder-path">
                <strong>Photos are saved to:</strong> {PHOTO_FOLDER}/
            </div>
            
            <button class="shutter-btn" onclick="location.href='/takePhoto'">
                TAKE PHOTO NOW
            </button>
            
            <div style="text-align: center; margin: 20px 0;">
                <button class="action-btn" onclick="location.href='/'">Refresh</button>
                <button class="sync-btn" onclick="if(confirm('Sync filesystem to prevent corruption before power off?')) location.href='/sync'">Sync Filesystem</button>
                <button class="action-btn" onclick="if(confirm('Format SD card? ALL files on SD will be deleted!')) location.href='/format'">Format SD</button>
                <button class="action-btn" onclick="if(confirm('Reboot camera?')) location.href='/reboot'">Reboot</button>
            </div>
            
            <h2>Recent Photos ({photo_count} total)</h2>
            <div class="photo-list">
    """
  
    if recent_photos:
        for photo in recent_photos:
            try:
                # Use the full path for stat check (CRITICAL FIX)
                full_path = PHOTO_FOLDER + "/" + photo
                size = os.stat(full_path)[6]
                size_kb = size // 1024
                html += f"""
                <div class="photo-item">
                    <div class="photo-name">{photo}</div>
                    <div class="photo-size">{size_kb} KB</div>
                </div>
                """
            except:
                html += f'<div class="photo-item">{photo}</div>'
    else:
        html += '<div style="text-align: center; color: #666; padding: 20px;">No photos yet. Take your first photo!</div>'
    
    html += f"""
            </div>
            
            <div class="warning">
                <strong>SD Card Safety:</strong>
                <ul style="margin: 10px 0; padding-left: 20px;">
                    <li>Photos are saved to <code>{PHOTO_FOLDER}/</code> folder</li>
                    <li>ALWAYS power off ESP32 before removing SD card</li>
                    <li>Wait 5 seconds after power loss</li>
                    <li>Use "Format SD" button if files don't appear on computer</li>
                </ul>
            </div>
            
            <div style="margin-top: 30px; color: #666; font-size: 12px; text-align: center;">
                {DEVICE_NAME} | {current_time} | Total photos: {photo_count}
            </div>
        </div>
    </body>
    </html>"""
    return html

def perform_system_reboot():
    """Perform a proper system reboot"""
    print("\n" + "=" * 60)
    print("Performing system reboot...")
    print("=" * 60)
    
    try:
        import gc
        gc.collect()
        print("Memory cleaned up")
    except:
        pass
    
    global s
    try:
        s.close()
        print("Socket closed")
    except:
        pass
    
    time.sleep(2)
    
    print("Rebooting now...")
    machine.reset()

def safe_shutdown():
    """Safely shutdown filesystem before power loss"""
    print("\n" + "=" * 60)
    print("Performing safe shutdown...")
    print("=" * 60)
    
    try:
        # Sync filesystem if available
        try:
            uos.sync() # CRITICAL FIX: Use uos.sync()
            print("Filesystem synced")
        except:
            pass
        
        # Force garbage collection
        import gc
        gc.collect()
        print("Memory cleaned")
        
        # Close all open files
        print("Closing open files...")
        
    except Exception as e:
        print(f"Shutdown error: {e}")
    
    print("Safe to remove power")
    print("=" * 60)

def sync_filesystem():
    """Force filesystem sync"""
    try:
        # uos.sync() forces all pending data to be written to disk (CRITICAL FIX)
        uos.sync()
        print("Filesystem synced successfully.")
        return True
    except:
        try:
            # Alternative sync method for ports without uos.sync (CRITICAL FIX)
            with open(SD_MOUNT_POINT + "/sync.tmp", "w") as f:
                f.write("sync")
            uos.remove(SD_MOUNT_POINT + "/sync.tmp")
            print("Filesystem synced via temp file.")
            return True
        except:
            print("Filesystem sync failed.")
            return False

def handle_web_requests():
    """Handle web requests"""
    global picture_count
    
    try:
        conn, addr = s.accept()
        print(f'Client connected from {addr[0]}')
        
        # Set timeout for receiving request
        conn.settimeout(5.0)
        request = conn.recv(1024)
        
        if request:
            request_str = request.decode()
            
            if 'GET / ' in request_str:
                conn.send('HTTP/1.1 200 OK\r\n')
                conn.send('Content-Type: text/html\r\n')
                conn.send('Connection: close\r\n\r\n')
                conn.sendall(web_page())
                conn.close()
                        
            elif 'GET /takePhoto' in request_str:
                # Send immediate response - don't wait for photo to complete
                conn.send('HTTP/1.1 200 OK\r\n')
                conn.send('Content-Type: text/html\r\n')
                conn.send('Connection: close\r\n\r\n')
                
                # HTML with auto-refresh and message
                html = '''
                <html>
                <head>
                    <meta http-equiv="refresh" content="3;url=/">
                    <style>
                        body { font-family: Arial; margin: 40px; text-align: center; }
                        .spinner {
                            border: 8px solid #f3f3f3;
                            border-top: 8px solid #3498db;
                            border-radius: 50%;
                            width: 60px;
                            height: 60px;
                            animation: spin 2s linear infinite;
                            margin: 20px auto;
                        }
                        @keyframes spin {
                            0% { transform: rotate(0deg); }
                            100% { transform: rotate(360deg); }
                        }
                    </style>
                </head>
                <body>
                    <h1>Taking Photo...</h1>
                    <div class="spinner"></div>
                    <p>Please wait while the photo is being taken.</p>
                    <p>You will be redirected back to the main page in a few seconds.</p>
                </body>
                </html>
                '''
                conn.sendall(html)
                conn.close()
                
                # Now take the photo in the background (non-blocking)
                print("Starting photo capture in background...")
                take_photo()
            
            elif 'GET /format' in request_str:
                success, deleted, errors = format_sd_card()
                
                if success:
                    message = f"SD Card Formatted!<br>"
                    message += f"Deleted {deleted} items"
                    if errors > 0:
                        message += f"<br>({errors} items could not be deleted)"
                    
                    html = f"""
                    <html><body style="font-family: Arial; margin: 40px; text-align: center;">
                    <h1>{message}</h1>
                    <p>Ready for new photos.</p>
                    <button onclick="location.href='/'" style="padding: 10px 20px; background: #4CAF50; color: white; border: none; border-radius: 4px; cursor: pointer;">
                        Back to Main Page
                    </button>
                    <script>setTimeout(function(){{ location.href="/"; }}, 5000);</script>
                    </body></html>
                    """
                else:
                    html = f"""
                    <html><body style="font-family: Arial; margin: 40px; text-align: center;">
                    <h1>Format Failed</h1>
                    <p>Could not format SD card.</p>
                    <p>Try physically removing and reinserting the SD card.</p>
                    <button onclick="location.href='/'" style="padding: 10px 20px; background: #2196F3; color: white; border: none; border-radius: 4px; cursor: pointer;">
                        Back
                    </button>
                    </body></html>
                    """
                
                conn.send('HTTP/1.1 200 OK\r\n')
                conn.send('Content-Type: text/html\r\n')
                conn.send('Connection: close\r\n\r\n')
                conn.sendall(html)
                conn.close()

            elif 'GET /sync' in request_str:
                # Sync filesystem before power off
                success = sync_filesystem()
                
                if success:
                    html = """
                    <html><body style="font-family: Arial; margin: 40px; text-align: center;">
                    <h1>Filesystem Synced!</h1>
                    <p>It is now safe to power off the ESP32.</p>
                    <p><strong>Wait 10 seconds</strong> after seeing this message before removing power.</p>
                    <button onclick="location.href='/'" style="padding: 10px 20px; background: #4CAF50; color: white; border: none; border-radius: 4px; cursor: pointer;">
                        Back to Main Page
                    </button>
                    <script>setTimeout(function(){ location.href="/"; }, 10000);</script>
                    </body></html>
                    """
                else:
                    html = """
                    <html><body style="font-family: Arial; margin: 40px; text-align: center;">
                    <h1>Sync Failed</h1>
                    <p>Could not sync filesystem. Wait 30 seconds before powering off.</p>
                    <button onclick="location.href='/'" style="padding: 10px 20px; background: #2196F3; color: white; border: none; border-radius: 4px; cursor: pointer;">
                        Back
                    </button>
                    </body></html>
                    """
                
                conn.send('HTTP/1.1 200 OK\r\n')
                conn.send('Content-Type: text/html\r\n')
                conn.send('Connection: close\r\n\r\n')
                conn.sendall(html)
                conn.close()
            
            elif 'GET /reboot' in request_str:
                conn.send('HTTP/1.1 200 OK\r\n')
                conn.send('Content-Type: text/html\r\n')
                conn.send('Connection: close\r\n\r\n')
                html = '''
                <html>
                <body style="font-family: Arial; margin: 40px; text-align: center;">
                <h1>Rebooting Camera...</h1>
                <p>The camera is now restarting.</p>
                <p>Please wait 10-15 seconds and refresh the page.</p>
                <p><a href="/">Click here if not redirected in 15 seconds</a></p>
                <script>
                    setTimeout(function() {
                        location.href = "/";
                    }, 15000);
                </script>
                </body>
                </html>
                '''
                conn.sendall(html)
                conn.close()
                
                time.sleep(1)
                perform_system_reboot()
        
    except OSError as e:
        if e.args[0] not in [11, 110, 115]:
            pass
        else:
            # Close connection if it's still open
            try:
                conn.close()
            except:
                pass
            
    except Exception as e:
        if "timed out" not in str(e) and "timeout" not in str(e):
            print(f"Web request error: {e}")
        # Close connection on any error
        try:
            conn.close()
        except:
            pass

def check_shutter():
    global last_shutter_state
    current_state = shutter.value()
    
    if last_shutter_state == 1 and current_state == 0:
        print("\nShutter button pressed!")
        take_photo()
        time.sleep(0.5)
    
    last_shutter_state = current_state

def main():
    """Main program function"""
    global s
    
    print("=" * 60)
    print(f"Starting {DEVICE_NAME}")
    print("=" * 60)

    connect_wifi()
    
    # Init camera after connecting wifi
    init_camera()

    # CRITICAL FIX: Attempt to mount the SD card
    if not mount_sd_card():
        print("CRITICAL: Halting due to SD card mounting failure.")
        print("Please check SD card seating and format (must be FAT32).")
        return # Stop execution if we can't save files

    # Proceed with file system setup on the mounted card
    if not setup_filesystem():
        print("Filesystem setup had issues, but continuing...")

    last_shutter_state = shutter.value()

    addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
    s = socket.socket()
    s.bind(addr)
    s.listen(5)
    s.setblocking(False)
    s.settimeout(0.1)
    print(f'Web server started on http://{network.WLAN(network.STA_IF).ifconfig()[0]}')

    print("\n" + "=" * 60)
    print("System Ready!")
    print(f"Photos will be saved to: {PHOTO_FOLDER}/")
    print("Press shutter button or use web interface")
    print("=" * 60)
    print("ALWAYS power off before removing SD card!")
    print("=" * 60)

    last_status_print = time.time()
    while True:
        check_shutter()
        try:
            handle_web_requests()
        except:
            pass
        
        if time.time() - last_status_print > 30:
            print(f"System running... Photos: {get_photo_count()}")
            last_status_print = time.time()
        
        time.sleep(0.01)

# ============ START THE PROGRAM ============
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Critical error: {e}")
        import sys
        sys.print_exception(e)
        time.sleep(5)
        machine.reset()
