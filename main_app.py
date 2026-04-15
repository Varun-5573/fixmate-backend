import threading
import time
import webbrowser
import logging
import sys
import os
import urllib.request

# ── Silence Flask logs ─────────────────────────────────────────
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# ── Fix path when running as PyInstaller EXE ──────────────────
if getattr(sys, 'frozen', False):
    os.chdir(os.path.dirname(sys.executable))

URL = "http://127.0.0.1:5000/admin"

def run_server():
    try:
        from server import socketio, app
        socketio.run(
            app,
            host="127.0.0.1",
            port=5000,
            debug=False,
            use_reloader=False,
            allow_unsafe_werkzeug=True
        )
    except Exception as e:
        print(f"Server error: {e}")

def wait_and_open():
    """Wait for Flask to be ready, then open browser"""
    print("Waiting for FixMate server to start...")
    for _ in range(40):
        try:
            urllib.request.urlopen(URL, timeout=1)
            print("Server ready! Opening Admin Panel...")
            # Open in Chrome app mode (looks like a standalone app)
            opened = False
            for browser_path in [
                "C:/Program Files/Google/Chrome/Application/chrome.exe",
                "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
                "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
                "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
            ]:
                if os.path.exists(browser_path):
                    import subprocess
                    subprocess.Popen([
                        browser_path,
                        f"--app={URL}",
                        "--window-size=1400,860",
                        "--disable-extensions",
                    ])
                    opened = True
                    break
            if not opened:
                webbrowser.open(URL)
            return
        except:
            time.sleep(0.5)
    print("ERROR: Server failed to start. Please check server.py")

if __name__ == "__main__":
    print("Starting FixMate Admin Pro...")

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    browser_thread = threading.Thread(target=wait_and_open, daemon=True)
    browser_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("FixMate Admin closed.")
        sys.exit(0)
