#!/usr/bin/env python3

"""
    Run in a loop tracking NAS state.
    requires inotify-tools.
"""


import sys
import requests
import socket
from pathlib import Path
from datetime import datetime, timezone, timedelta
import configparser
import queue
from threading import Thread


VERY_OLD = datetime.now(tz=timezone.utc) - timedelta(days=360)


LOG_DIR = "/var/log/jellyfin"
# Initially just the logfiles, could add other sources and push them here.
JELLYFIN_ACTIVITY = queue.Queue()


STATE_REQUESTS = queue.Queue()


class Jellyfin:
    def __init__(self, token):
        self.token = token
        self.host = "127.0.0.1"
        self.port = 8096

    def get_session_list(self):
        resp = requests.get(f"http://{self.host}:{self.port}/Sessions", headers={"X-Emby-Token": self.token})
        session_list = resp.json()
        return session_list

    def latest_activity(self):
        all_dates = []
        session_list = self.get_session_list()
        for session in session_list:
            iso_str = session["LastActivityDate"]
            iso_date = datetime.fromisoformat(iso_str)
            all_dates.append(iso_date)

        all_dates.sort()
        return all_dates[-1]


def log_watcher_thread():
    while True:
        try:
            # Run inotifywait with timeout
            result = subprocess.run(
                ['inotifywait', '-e', 'create', '-e', 'modify', LOG_DIR],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            if result.returncode == 0:
                JELLYFIN_ACTIVITY.put("logs")
                time.sleep(30)  # idle buffer before next check
            else:
                print(f"[ERROR] inotifywait exited with code {result.returncode}")
                break  # Exit thread on non-retryable error

        except FileNotFoundError:
            print("[ERROR] inotifywait or wakeonlan not found.")
            break


class Nas:
    def __init__(self, host, port, mac):
        self.host = host
        self.port = port
        self.mac = mac
        self.suspend_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def ping(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(2)
            s.sendto(b"ping", (self.host, self.port))
            try:
                data, _ = s.recvfrom(1024)
                self.assertEqual(data.decode(), "pong")
                return True
            except socket.timeout:
                pass
        return False

    def wake_on_lan(self):
        """Send a Wake-on-LAN (WOL) magic packet to the given MAC address."""
        mac_bytes = bytes.fromhex(self.mac.replace(":", "").replace("-", ""))
        magic_packet = b'\xff' * 6 + mac_bytes * 16
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.sendto(magic_packet, ('<broadcast>', 9))

    def wake_up(self):
        """Wake up the NAS"""
        max_attempts = 15
        while (not self.ping()) and max_attempts:
            self.wake_on_lan()
            max_attempts =- 1
        if mac_attempts == 0:
            raise ValueError("Failed to wake up NAS after multiple attempts.")

    def suspend(self):
        """Put to sleep the nas"""
        max_attempts = 15
        while (self.ping()) and max_attempts:
            self.suspend_socket.sendto(b"suspend", (self.host, self.port))
            max_attempts =- 1
        if mac_attempts == 0:
            raise ValueError("Failed to make the NAS sleep after multiple attempts.")


def main():
    parser = ArgumentParser()
    parser.add_argument('--config', type=str, default="/etc/suspend-server/config.json", help='Config file')

    args = parser.parse_args()

    if args.config:
        config = json.load(Path(args.config).open())
    else:
        config = {}

    host = config.get('nas_host', "0.0.0.0")
    port = config.get('nas_port', 6061)
    mac = config.get('nas_mac', None)

    if not token:
        sys.exit("No Jellyfin token provided in config, need one.")

    if not mac:
        sys.exit("No NAS mac address provided in config, need one.")

    nas = Nas(host, port, mac)
    
        
    watcher_thread = threading.Thread(target=log_watcher_thread, daemon=True)

    while True:
        try:
            item = JELLYFIN_ACTIVITY.get(timeout=300)
            needs_sleep = False
        except queue.Empty:
            needs_sleep = True

        if needs_sleep:
            nas.suspend()
        else:
            nas.wake_up()



if __name__ == "__main__":
    main()
