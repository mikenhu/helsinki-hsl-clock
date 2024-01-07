#!/usr/bin/env python3
import os
import sys
import pygame

class Hyperpixel2r:
    screen = None
    def __init__(self):
        self._init_display()

        self.screen.fill((0, 0, 0))
        if self._rawfb:
            self._updatefb()
        else:
            pygame.display.update()

        # For some reason the canvas needs a 7px vertical offset
        # circular screens are weird...
        self.center = (240, 247)
        self._radius = 240

        # Distance of hour marks from center
        self._marks = 220

        self._origin = pygame.math.Vector2(*self.center)
        self._colour = (255, 0, 255)

    def _exit(self, sig, frame):
        self._running = False
        print("\nExiting!...\n")

    def _init_display(self):
        self._rawfb = False
        # Based on "Python GUI in Linux frame buffer"
        # http://www.karoltomala.com/blog/?p=679
        DISPLAY = os.getenv("DISPLAY")
        if DISPLAY:
            print("Display: {0}".format(DISPLAY))

        if os.getenv('SDL_VIDEODRIVER'):
            print("Using driver specified by SDL_VIDEODRIVER: {}".format(os.getenv('SDL_VIDEODRIVER')))
            pygame.display.init()
            size = (pygame.display.Info().current_w, pygame.display.Info().current_h)
            if size == (480, 480): # Fix for 480x480 mode offset
                size = (640, 480)
            self.screen = pygame.display.set_mode(size, pygame.FULLSCREEN | pygame.DOUBLEBUF | pygame.NOFRAME | pygame.HWSURFACE)
            return

        else:
            # Iterate through drivers and attempt to init/set_mode
            for driver in ['rpi', 'kmsdrm', 'fbcon', 'directfb', 'svgalib']:
                os.putenv('SDL_VIDEODRIVER', driver)
                try:
                    pygame.display.init()
                    size = (pygame.display.Info().current_w, pygame.display.Info().current_h)
                    if size == (480, 480):  # Fix for 480x480 mode offset
                        size = (640, 480)
                    self.screen = pygame.display.set_mode(size, pygame.FULLSCREEN | pygame.DOUBLEBUF | pygame.NOFRAME | pygame.HWSURFACE)
                    print("Using driver: {0}, Framebuffer size: {1:d} x {2:d}".format(driver, *size))
                    return
                except pygame.error as e:
                    print('Driver "{0}" failed: {1}'.format(driver, e))
                    continue
                break

        print("All SDL drivers failed, falling back to raw framebuffer access.")
        self._rawfb = True
        os.putenv('SDL_VIDEODRIVER', 'dummy')
        pygame.display.init()  # Need to init for .convert() to work
        self.screen = pygame.Surface((480, 480))

    def __del__(self):
        "Destructor to make sure pygame shuts down, etc."

    def _updatefb(self):
        fbdev = os.getenv('SDL_FBDEV', '/dev/fb0')
        with open(fbdev, 'wb') as fb:
            fb.write(self.screen.convert(16, 0).get_buffer())
