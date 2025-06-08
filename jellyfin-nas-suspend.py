#!/usr/bin/env python3

"""
    Run on a Jellyfin to suspend/wake your NAS

    requires python3-pyinotify.
"""


import sys
import pyinotify
import requests
import socket
import json
import time
from argparse import ArgumentParser
from pathlib import Path
from datetime import datetime
import queue
import threading
import subprocess


JELLYFIN_ACTIVITY = queue.Queue()


# Not used, may add session monitoring later.
class Jellyfin:
    def __init__(self, token):
        self.token = token
        self.host = "127.0.0.1"
        self.port = 8096

    def get_session_list(self):
        try:
            resp = requests.get(f"http://{self.host}:{self.port}/Sessions", headers={"X-Emby-Token": self.token}, timeout=5)
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError):
            print("API call failed, Jellyfin offline or token invalid?")
            return None

    def latest_activity(self):
        all_dates = []
        session_list = self.get_session_list()
        if session_list is None:
            return None
        for session in session_list:
            iso_str = session["LastActivityDate"]
            iso_date = datetime.fromisoformat(iso_str)
            all_dates.append(iso_date)

        all_dates.sort()
        if len(all_dates) == 0:
            return None
        return all_dates[-1]
        
        
def session_watcher_thread(token, poll_interval):
    """Session watcher is not as responsive as log watcher, so this is more for keeping the NAS on
        rather than waking it up, still handy to have a fallback in case logs go quiet"""
    JELLYFIN_ACTIVITY.put("session watcher startup")
    date_now = datetime.now(tz=timezone.utc)
    very_old = date_now - timedelta(days=360)
    latest_session = very_old
    jellyfin_api = Jellyfin(token)
    while True:
        latest_activity = jellyfin_api.latest_activity()
        if latest_activity is None:
            continue
        if latest_activity > latest_session:
            latest_session = latest_activity
            JELLYFIN_ACTIVITY.put("sessions")


class JellyfinEventHandler(pyinotify.ProcessEvent):
    def __init__(self, queue, poll_interval):
        self.queue = queue
        self.poll_interval = poll_interval

    def process_IN_CREATE(self, event):
        self._handle_event()

    def process_IN_MODIFY(self, event):
        self._handle_event()

    def _handle_event(self):
        print("Encountered Jellyfin activity")
        self.queue.put("logs")
        time.sleep(self.poll_interval)  # idle buffer before next check


def log_watcher_thread(log_dir, poll_interval):
    JELLYFIN_ACTIVITY.put("log watcher startup")

    wm = pyinotify.WatchManager()
    mask = pyinotify.IN_CREATE | pyinotify.IN_MODIFY

    handler = JellyfinEventHandler(JELLYFIN_ACTIVITY, poll_interval)
    notifier = pyinotify.Notifier(wm, handler)

    try:
        wm.add_watch(log_dir, mask, rec=False)
        notifier.loop()
    except KeyboardInterrupt:
        print("[INFO] Log watcher interrupted")
    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        notifier.stop()


def get_local_ip_for_target(target_ip):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # doesn't actually send data, just triggers routing logic
            s.connect((target_ip, 9))  # any port will do
            local_ip = s.getsockname()[0]
            return local_ip
    except Exception as e:
        print(f"Error: {e}")
        return None


class Nas:
    def __init__(self, host, port, mac):
        self.host = host
        self.port = port
        self.mac = mac
        self.local_ip = get_local_ip_for_target(self.host)
        self.suspend_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def ping(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(2)
            s.sendto(b"ping", (self.host, self.port))
            try:
                data, _ = s.recvfrom(1024)
                return True
            except socket.timeout:
                pass
        return False

    def wake_on_lan(self):
        """Send a Wake-on-LAN (WOL) magic packet to the given MAC address."""
        print(f"Sending WOL to {self.mac}")
        mac_bytes = bytes.fromhex(self.mac.replace(":", "").replace("-", ""))
        magic_packet = b'\xff' * 6 + mac_bytes * 16
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.bind((self.local_ip, 0))
            s.sendto(magic_packet, ('<broadcast>', 9))

    def wake_up(self):
        """Wake up the NAS"""
        print("NAS wake_up()")
        max_attempts = 15
        while (not self.ping()) and max_attempts:
            self.wake_on_lan()
            # Wake-up can take a while
            time.sleep(1)
            max_attempts =- 1
        if max_attempts == 0:
            raise ValueError("Failed to wake up NAS after multiple attempts.")
        print("Successfully woken")

    def suspend(self):
        """Put to sleep the nas"""
        print("NAS suspend()")
        max_attempts = 15
        while (self.ping()) and max_attempts:
            print("Sending suspend packet")
            self.suspend_socket.sendto(b"suspend", (self.host, self.port))
            max_attempts =- 1
        if max_attempts == 0:
            raise ValueError("Failed to make the NAS sleep after multiple attempts.")
        print("Successfully suspended, no longer responding to network requests")


def main():
    parser = ArgumentParser()
    parser.add_argument('--config', type=str, default="/etc/suspend-server/config.json", help='Config file')

    args = parser.parse_args()

    if args.config:
        config = json.load(Path(args.config).open())
    else:
        config = {}

    logs = config.get('jellyfin_log_dir', "/var/log/jellyfin")
    token = config.get('jellyfin_token', None)
    host = config.get('remote_nas_host', "0.0.0.0")
    port = config.get('remote_nas_port', 6061)
    mac = config.get('remote_nas_mac', None)
    idle_time = config.get('idle_time', 300)
    poll_interval = config.get('poll_interval', 30)

    print("Using configuration:")
    print(f"  jellyfin_log_dir: {logs}")
    print(f"  jellyfin_token: {token}")
    print(f"  remote_nas_host: {host}")
    print(f"  remote_nas_port: {port}")
    print(f"  remote_nas_mac: {mac}")
    print(f"  idle_time: {idle_time}")
    print(f"  poll_interval: {poll_interval}")

    if not mac:
        sys.exit("No NAS mac address provided in config, need one to wake something.")

    nas = Nas(host, port, mac)

    # We're always going to watch at least the log
    log_watcher = threading.Thread(target=log_watcher_thread, args=(logs,poll_interval), daemon=True)
    log_watcher.start()
    
    if token is not None:
        session_watcher = threading.Thread(target=session_watcher_thread, args=(token,poll_interval), daemon=True)
        session_watcher.start()
        

    while True:
        try:
            JELLYFIN_ACTIVITY.get(timeout=idle_time)
            print("Returned from activity poll, doesn't need sleep")
            needs_sleep = False
        except queue.Empty:
            print("Returned from activity poll, no activity, needs sleep")
            needs_sleep = True

        if needs_sleep:
            nas.suspend()
        else:
            nas.wake_up()


if __name__ == "__main__":
    main()
