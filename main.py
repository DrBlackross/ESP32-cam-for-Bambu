import network
import camera
import socket
import time
import os
import machine

# Configuration
SSID = "YOUR_SSID"
PASSWORD = "YOU_WIFI_PASSWORD"
SHUTTER_PIN = 13
DEVICE_NAME = "Bambu-Camera"

# Initialize
shutter = machine.Pin(SHUTTER_PIN, machine.Pin.IN, machine.Pin.PULL_UP)
picture_count = 0

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
    try:
        camera.init(0, format=camera.JPEG)
        print("Camera initialized")
    except Exception as e:
        print("Camera init failed:", e)

def take_photo():
    global picture_count
    try:
        buf = camera.capture()
        filename = "/image{}.jpg".format(picture_count)
        with open(filename, "wb") as f:
            f.write(buf)
        picture_count += 1
        print("Photo saved:", filename)
        return True
    except Exception as e:
        print("Photo capture failed:", e)
        return False

def list_files():
    try:
        files = os.listdir()
        jpgs = [f for f in files if f.endswith('.jpg')]
        return jpgs
    except:
        return []

def delete_all_photos():
    """Delete all JPG photos from the SD card"""
    files = list_files()
    deleted_count = 0
    for filename in files:
        try:
            os.remove(filename)
            deleted_count += 1
            print("Deleted:", filename)
        except Exception as e:
            print(f"Error deleting {filename}: {e}")
    return deleted_count

def reboot_esp32():
    """Delete all photos and reboot the ESP32"""
    print("Reboot requested - deleting all photos and restarting...")
    deleted_count = delete_all_photos()
    print(f"Deleted {deleted_count} photos before reboot")
    time.sleep(1)
    machine.reset()

def web_page():
    files = list_files()
    html = """<html>
    <head><title>ESP32-CAM</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1 { color: #333; }
        button { 
            color: white; 
            padding: 10px 15px; 
            border: none; 
            border-radius: 4px; 
            cursor: pointer; 
            margin: 5px;
            font-size: 16px;
        }
        button:hover { opacity: 0.8; }
        .refresh { background: #2196F3; }
        .delete-all { background: #f44336; }
        .reboot { background: #FF9800; }
        ul { list-style-type: none; padding: 0; }
        li { margin: 5px 0; padding: 8px; background: #f9f9f9; border-radius: 4px; }
        .file-count { color: #666; margin: 10px 0; }
        .danger-zone { 
            margin: 20px 0; 
            padding: 15px; 
            border: 2px solid #ffcccc; 
            border-radius: 5px; 
            background: #fff5f5;
        }
        .danger-zone h3 { color: #d32f2f; margin-top: 0; }
        .file-list { max-height: 300px; overflow-y: auto; border: 1px solid #ddd; padding: 10px; }
        .status { 
            background: #e8f5e8; 
            padding: 10px; 
            border-radius: 4px; 
            border: 1px solid #4CAF50;
            margin: 10px 0;
        }
    </style>
    </head>
    <body>
        <h1>ESP32-CAM Photo Station</h1>
        <div class="status">
            📸 <strong>Camera Active</strong> - Use physical shutter button on printer
        </div>
        <button class="refresh" onclick="location.href='/'">🔄 Refresh File List</button>"""
    
    if files:
        html += """<button class="delete-all" onclick="if(confirm('Delete all {} photos?')) location.href='/deleteAll'">🗑️ Delete All Photos</button>""".format(len(files))
    
    html += """
        <div class="file-count">📁 {} photos on SD card</div>
        <div class="file-list">
            <h3>Photo Files:</h3>
            <ul>""".format(len(files))
    
    for file in files:
        html += '<li>{}</li>'.format(file)
    
    html += """</ul>
        </div>
        <div class="danger-zone">
            <h3>⚠️ Danger Zone</h3>
            <button class="reboot" onclick="if(confirm('This will delete ALL photos and reboot the camera. Continue?')) location.href='/reboot'">🔄 Reboot & Clear All</button>
            <p><small>Deletes all photos and restarts the camera system</small></p>
        </div>
        <div style="margin-top: 20px; color: #666; font-size: 14px;">
            <strong>Usage:</strong><br>
            • Physical shutter button takes photos<br>
            • Remove SD card to transfer files<br>
            • Refresh to update file list<br>
            • Reboot to clear everything and restart
        </div>
    </body>
    </html>"""
    return html

def handle_web_requests():
    """Handle web requests without blocking the main loop"""
    try:
        conn, addr = s.accept()
        print('Client connected from', addr)
        request = conn.recv(1024)
        request_str = str(request)
        
        if 'GET / ' in request_str:
            conn.send('HTTP/1.1 200 OK\n')
            conn.send('Content-Type: text/html\n')
            conn.send('Connection: close\n\n')
            conn.sendall(web_page())
                    
        elif 'GET /deleteAll' in request_str:
            deleted_count = delete_all_photos()
            conn.send('HTTP/1.1 200 OK\n')
            conn.send('Content-Type: text/html\n')
            conn.send('Connection: close\n\n')
            conn.sendall('<html><body><h1>Deleted {} photos!</h1><a href="/">Back</a></body></html>'.format(deleted_count))
        
        elif 'GET /reboot' in request_str:
            conn.send('HTTP/1.1 200 OK\n')
            conn.send('Content-Type: text/html\n')
            conn.send('Connection: close\n\n')
            conn.sendall('<html><body><h1>Rebooting...</h1><p>Deleting all photos and restarting camera system.</p><p>Page will refresh in 10 seconds.</p><script>setTimeout(function(){ location.href="/"; }, 10000);</script></body></html>')
            conn.close()
            time.sleep(1)
            reboot_esp32()
                
        conn.close()
    except:
        pass  # No client connected, just continue we dont care

def check_shutter():
    global last_shutter_state
    current_state = shutter.value()
    
    if last_shutter_state == 1 and current_state == 0:
        print("Shutter button pressed!")
        take_photo()
        time.sleep(0.5)
    last_shutter_state = current_state

# Main setup
print("Initializing ESP32-CAM...")
connect_wifi()
init_camera()

last_shutter_state = shutter.value()

print("System ready!")
print("Press shutter button or visit http://{} to manage photos".format(network.WLAN(network.STA_IF).ifconfig()[0]))

# Setup web server socket
addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
s = socket.socket()
s.bind(addr)
s.listen(5)
s.setblocking(False)
print('Web server started on', addr)

# Main loop
while True:
    check_shutter()
    handle_web_requests()
    time.sleep(0.01)
# this should work lol
