Intro
=====

Wake your PC nas on Jellyfin activity

Installation
============

On the NAS PC:
Follow the instructions to install:
https://github.com/bifferos/suspend-server

On the Jellyfin PC:
Ensure you have the python pyinotify module.  It comes
with Linux Mint because it's used by Cinnamon.  There
are two commonly used inotify packages for python make sure
you get the right one:

$ sudo apt install python3-pyinotify

Put the right stuff in config.json, ensure port
matches what you're using on the NAS (suspend-server)

$ vim config.json

Check the log path is right for Jellyfin, usually 
/var/log/jellyfin
Set idle time and poll interval to something low for testing,
then I suggest you raise it to 300 and 30 for production.  
This gives suspend after 5 minutes of idle, and checks every
30 seconds.
Make sure it works as you intended by running first outside
systemd:

$ make run

This will allow you to see the text output telling you what
it's doing without journalctl commands.

Finally install the systemd service on Jellyfin to start
the service and have it run at boot:

$ make install

