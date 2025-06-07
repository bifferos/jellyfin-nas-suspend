Intro
=====

Wake your PC nas on Jellyfin activity

Installation
============

Install on the nas:
https://github.com/bifferos/suspend-server

On the Jellyfin host:
Ensure you have inotify-tools

$ sudo apt install inotify-tools

Put the right stuff in config.json, ensure it
matches what you're using on the NAS (suspend-server)

Install the systemd service on Jellyfin.
Check the log path is right (assumes /var/log/jellyfin)

$ make install

