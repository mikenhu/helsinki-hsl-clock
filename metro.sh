#!/bin/sh
cd /home/pi/hsl-metro-clock
sudo SDL_FBDEV=/dev/fb0 python3 metro_time.py &
