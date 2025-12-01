import network
import camera
import socket
import time
import os
import machine
import ubinascii

# ============ CONFIGURATION ============
SSID = "YOUR_SSID"
PASSWORD = "YOUR_SSID_PASSWORD"
SHUTTER_PIN = 13
DEVICE_NAME = "Bambu-Camera"
WEB_PORT = 80
USE_AUTH = False
WEB_PASSWORD = "admin123"
# =======================================

# Global variables
shutter = machine.Pin(SHUTTER_PIN, machine.Pin.IN, machine.Pin.PULL_UP)
picture_count = 0
last_shutter_state = None
wlan = None
server_socket = None

def connect_wifi():
    """Connect to WiFi network"""
    global wlan
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.config(dhcp_hostname=DEVICE_NAME)
    
    if not wlan.isconnected():
        print("Connecting to WiFi...")
        wlan.connect(SSID, PASSWORD)
        
        timeout = 30
        start = time.time()
        while not wlan.isconnected():
            if time.time() - start > timeout:
                print("WiFi timeout!")
                return False
            time.sleep(0.5)
            print('.', end='')
    
    print("\nWiFi Connected!")
    print("Device:", DEVICE_NAME)
    print("IP:", wlan.ifconfig()[0])
    return True

def init_camera():
    """Initialize ESP32-CAM"""
    try:
        camera.init(0, format=camera.JPEG)
        print("Camera initialized")
        return True
    except Exception as e:
        print("Camera error:", e)
        return False

def take_photo():
    """Capture and save photo"""
    global picture_count
    try:
        buf = camera.capture()
        filename = "/image{}.jpg".format(picture_count)
        with open(filename, "wb") as f:
            f.write(buf)
        picture_count += 1
        print("Photo saved:", filename)
        return filename
    except Exception as e:
        print("Photo failed:", e)
        return None

def list_files(ext=".jpg"):
    """List files on SD card"""
    try:
        files = os.listdir()
        if ext:
            filtered = [f for f in files if f.endswith(ext)]
        else:
            filtered = files
        return sorted(filtered)
    except:
        return []

def delete_all_photos():
    """Delete all photos and reset counter"""
    files = list_files(".jpg")
    deleted = 0
    for f in files:
        try:
            os.remove(f)
            deleted += 1
        except:
            pass
    
    global picture_count
    picture_count = 0
    
    return deleted

def format_sd_card():
    """Delete ALL files from SD card"""
    try:
        files = os.listdir()
        deleted = 0
        for f in files:
            try:
                os.remove(f)
                deleted += 1
            except:
                pass
        global picture_count
        picture_count = 0
        return deleted
    except:
        return 0

def check_auth(request):
    """Check Basic Authentication"""
    if not USE_AUTH:
        return True
    
    if "Authorization: Basic " in request:
        auth = request.split("Authorization: Basic ")[1].split("\r\n")[0]
        try:
            decoded = ubinascii.a2b_base64(auth).decode()
            return decoded.endswith(":" + WEB_PASSWORD)
        except:
            pass
    return False

def send_unauthorized(conn):
    """Send 401 Unauthorized response"""
    response = """HTTP/1.1 401 Unauthorized\r
WWW-Authenticate: Basic realm="ESP32-CAM Access"\r
Content-Type: text/html\r
\r
<html>
<head><title>Authentication Required</title></head>
<body>
<h1>Authentication Required</h1>
<p>Please enter password to access ESP32-CAM</p>
</body>
</html>"""
    conn.send(response)
    conn.close()

def get_file_size_kb(filename):
    """Get file size in KB"""
    try:
        size = os.stat(filename)[6]
        return size // 1024
    except:
        return 0

def create_webpage():
    """Generate HTML control panel"""
    files = list_files(".jpg")
    all_files = list_files("")
    
    total_size = 0
    for f in all_files:
        total_size += get_file_size_kb(f)
    
    html = """HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\n\r\n
<!DOCTYPE html>
<html>
<head>
    <title>""" + DEVICE_NAME + """ Control Panel</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { background: white; padding: 25px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }
        .status-box { background: #e8f4f8; padding: 15px; border-radius: 8px; margin: 15px 0; border-left: 5px solid #3498db; }
        .action-buttons { margin: 20px 0; }
        .btn { 
            display: inline-block; padding: 12px 25px; margin: 8px 5px; 
            color: white; text-decoration: none; border-radius: 6px; 
            border: none; font-size: 16px; font-weight: bold; cursor: pointer;
            transition: all 0.3s;
        }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 4px 8px rgba(0,0,0,0.2); }
        .btn-refresh { background: #3498db; }
        .btn-delete { background: #e74c3c; }
        .btn-format { background: #9b59b6; }
        .btn-reboot { background: #e67e22; }
        .btn-shutter { background: #2ecc71; font-size: 18px; padding: 15px 30px; }
        .file-list { 
            background: #f8f9fa; border: 2px solid #dee2e6; border-radius: 8px; 
            padding: 20px; margin: 20px 0; max-height: 400px; overflow-y: auto;
        }
        .file-item { 
            padding: 10px; margin: 5px 0; background: white; 
            border-radius: 5px; border-left: 4px solid #2ecc71;
        }
        .danger-zone { 
            background: #ffeaa7; border: 3px solid #fdcb6e; border-radius: 10px; 
            padding: 20px; margin: 25px 0;
        }
        .info-text { color: #7f8c8d; font-size: 14px; margin-top: 5px; }
        @media (max-width: 600px) { .btn { display: block; width: 100%; margin: 10px 0; } }
    </style>
    <script>
        function takePhoto() {
            fetch('/capture').then(function() { location.reload(); });
        }
        function deletePhotos() {
            if(confirm('Delete all """ + str(len(files)) + """ photos?')) {
                fetch('/delete').then(function() { location.reload(); });
            }
        }
        function formatSD() {
            if(confirm('DELETE ALL """ + str(len(all_files)) + """ FILES?\\nThis cannot be undone!')) {
                fetch('/format').then(function() { location.reload(); });
            }
        }
        function rebootDevice() {
            if(confirm('Reboot ESP32?')) {
                fetch('/reboot');
            }
        }
        function updateTime() {
            var elem = document.getElementById('uptime');
            if (elem) elem.innerText = Math.floor(performance.now() / 1000) + 's';
        }
        setInterval(updateTime, 1000);
    </script>
</head>
<body>
    <div class="container">
        <h1>""" + DEVICE_NAME + """ Control Panel</h1>
        
        <div class="status-box">
            <strong>Status:</strong><br>
            IP: """ + wlan.ifconfig()[0] + """<br>
            Files: """ + str(len(all_files)) + """ total (""" + str(len(files)) + """ photos)<br>
            Storage: """ + ("{:.1f}".format(total_size) if total_size > 0 else "0") + """ KB used<br>
            Next photo: image""" + str(picture_count) + """.jpg<br>
            Uptime: <span id="uptime">0s</span>
        </div>
        
        <div class="action-buttons">
            <button class="btn btn-refresh" onclick="location.reload()">Refresh</button>
            <button class="btn btn-shutter" onclick="takePhoto()">Take Photo</button>
            <button class="btn btn-delete" onclick="deletePhotos()">Delete Photos</button>
            <button class="btn btn-format" onclick="formatSD()">Format SD</button>
            <button class="btn btn-reboot" onclick="rebootDevice()">Reboot</button>
        </div>
        
        <div class="file-list">
            <h3>Photo Files (""" + str(len(files)) + """):</h3>"""
    
    if files:
        for f in files:
            size_kb = get_file_size_kb(f)
            html += '<div class="file-item">' + f + ' <small>(' + str(size_kb) + ' KB)</small></div>'
    else:
        html += '<p style="color: #95a5a6;">No photos found</p>'
    
    html += """
        </div>
        
        <div class="danger-zone">
            <h3 style="color: #d35400;">DANGER ZONE</h3>
            <p class="info-text">These actions are irreversible:</p>
            <button class="btn btn-format" onclick="formatSD()" style="background: #c0392b;">
                FORMAT SD CARD (ALL FILES)
            </button>
            <button class="btn btn-reboot" onclick="rebootDevice()" style="background: #d35400;">
                REBOOT & CLEAR
            </button>
        </div>
        
        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee;">
            <p class="info-text">
                <strong>Instructions:</strong><br>
                1. Physical shutter button on GPIO """ + str(SHUTTER_PIN) + """<br>
                2. Photos auto-save to SD card as imageX.jpg<br>
                3. Format SD card to delete everything<br>
                4. Remove SD card to transfer files to computer<br>
                5. Connection: HTTP on port """ + str(WEB_PORT) + """
            </p>
        </div>
    </div>
</body>
</html>"""
    
    return html

def handle_request(conn, request):
    """Handle HTTP requests"""
    global server_socket  
    
    if USE_AUTH and not check_auth(request):
        send_unauthorized(conn)
        return
    
    if "GET / " in request or "GET /index" in request:
        conn.send(create_webpage())
    
    elif "GET /capture" in request:
        filename = take_photo()
        if filename:
            response = """HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n
            <h1>Photo Taken!</h1>
            <p>Saved as: """ + filename + """</p>
            <p><a href="/">Back</a></p>
            <script>setTimeout(function() { location.href='/'; }, 2000);</script>"""
        else:
            response = """HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n
            <h1>Photo Failed</h1>
            <p><a href="/">Back</a></p>"""
        conn.send(response)
    
    elif "GET /delete" in request:
        deleted = delete_all_photos()
        response = """HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n
        <h1>""" + str(deleted) + """ Photos Deleted</h1>
        <p><a href="/">Back</a></p>
        <script>setTimeout(function() { location.href='/'; }, 2000);</script>"""
        conn.send(response)
    
    elif "GET /format" in request:
        deleted = format_sd_card()
        response = """HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n
        <h1>SD Card Formatted</h1>
        <p>""" + str(deleted) + """ files deleted</p>
        <p><a href="/">Back</a></p>
        <script>setTimeout(function() { location.href='/'; }, 2000);</script>"""
        conn.send(response)
    
    elif "GET /reboot" in request:
        response = """HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n
        <h1>Restarting Services...</h1>
        <p>Web server restarting, page will reload in 5 seconds</p>
        <script>setTimeout(function() { location.href='/'; }, 5000);</script>"""
        conn.send(response)
        conn.close()
        
        # Close and restart socket
        if server_socket:
            server_socket.close()
        
        # Reinitialize
        time.sleep(2)
        start_server()
        print("Web server restarted")
        return 
    
    else:
        # 404 Not Found
        response = """HTTP/1.1 404 Not Found\r\nContent-Type: text/html\r\n\r\n
        <h1>404 - Page Not Found</h1>
        <p><a href="/">Go to Home</a></p>"""
        conn.send(response)
    
    conn.close()

def check_shutter():
    """Monitor shutter button"""
    global last_shutter_state
    current = shutter.value()
    
    if last_shutter_state is not None and last_shutter_state == 1 and current == 0:
        print("Shutter button pressed!")
        take_photo()
        time.sleep(0.3)
    
    last_shutter_state = current

def start_server():
    """Start HTTP server"""
    global server_socket
    
    addr = ('0.0.0.0', WEB_PORT)
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(addr)
    server_socket.listen(5)
    server_socket.settimeout(0.5)
    
    print("HTTP server started on port", WEB_PORT)
    print("Open: http://" + wlan.ifconfig()[0] + ":" + str(WEB_PORT))
    if USE_AUTH:
        print("Password protected")

def main():
    """Main program"""
    print("=" * 50)
    print("Starting", DEVICE_NAME)
    print("=" * 50)
    
    if not connect_wifi():
        print("Failed to connect. Rebooting in 10s...")
        time.sleep(10)
        machine.reset()
    
    init_camera()
    
    global last_shutter_state
    last_shutter_state = shutter.value()
    
    start_server()
    
    print("=" * 50)
    print("System Ready!")
    print("Press shutter button to take photos")
    print("Visit web interface to manage files")
    print("=" * 50)
    
    request_count = 0
    
    while True:
        try:
            conn, addr = server_socket.accept()
            request_count += 1
            print("Request #" + str(request_count) + " from", addr[0])
            
            request = conn.recv(1024).decode()
            if request:
                handle_request(conn, request)
        
        except OSError as e:
            if e.args[0] not in [116, 110, 11, 113]:
                print("Socket error:", e)
        
        check_shutter()
        time.sleep(0.01)

# Create boot.py to ensure main.py runs on startup
def create_boot_py():
    """Create boot.py if it doesn't exist"""
    try:
        # Check if boot.py exists
        os.stat("boot.py")
        print("boot.py already exists")
    except:
        # Create boot.py
        boot_content = """# boot.py - Run on boot to start main.py
import machine
import time
import os

print("Booting ESP32-CAM...")
time.sleep(1)

# Run main.py if it exists
try:
    import main
    print("main.py imported successfully")
except Exception as e:
    print("Error importing main.py:", e)
    # Try to run it directly
    try:
        exec(open('main.py').read())
    except Exception as e2:
        print("Failed to run main.py:", e2)
"""
        with open("boot.py", "w") as f:
            f.write(boot_content)
        print("Created boot.py")

# Check/create boot.py on first run
create_boot_py()

# Run main program
try:
    main()
except KeyboardInterrupt:
    print("\nStopping...")
except Exception as e:
    print("Critical error:", e)
    time.sleep(5)
    machine.reset()
