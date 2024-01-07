#!/bin/sh
# Fix issue Hyperpixel display does not initiate after a restart resulting a blank output.
/usr/bin/hyperpixel2r-init &
cd /home/pi/hsl-metro-clock
sudo SDL_FBDEV=/dev/fb0 python3 metro.py &
