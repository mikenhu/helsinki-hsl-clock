#!/usr/bin/env python3
import os
import sys
import signal
import pygame
import time
import threading
import queue

from hsl import *

# Credit to Pimoroni for the Hyperpixel2r class
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
        # self._marks = 220

        self._running = False
        self._origin = pygame.math.Vector2(*self.center)
        self._clock = pygame.time.Clock()
        self._colour = (255, 0, 255)

        # Load the image, reduce the size of the tram icon and create img object
        # Credit for the icon source: https://www.flaticon.com/free-icons/train
        size_single = (512 // 6, 358 // 6)
        size_double = (1050 // 6, 367 // 6)
        self._img_double = load_and_scale_image("imgs/double-tram.png", size_double)
        self._img_left = load_and_scale_image("imgs/single-tram-left.png", size_single)
        self._img_right = load_and_scale_image("imgs/single-tram-right.png", size_single)

        # Initiate alert message
        self.alert_result = None
        # Define a flag to stop threads gracefully later
        self.stop_flag = threading.Event()
        
        # Set top and bottom bands starting coordinations
        self.top_x = 480
        self.top_y = 40
        self.bottom_x = -180
        self.bottom_y = 390

        self._running = True

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

        if os.getenv("SDL_VIDEODRIVER"):
            print(
                "Using driver specified by SDL_VIDEODRIVER: {}".format(
                    os.getenv("SDL_VIDEODRIVER")
                )
            )
            pygame.display.init()
            size = (pygame.display.Info().current_w, pygame.display.Info().current_h)
            if size == (480, 480):  # Fix for 480x480 mode offset
                size = (640, 480)
            self.screen = pygame.display.set_mode(
                size,
                pygame.FULLSCREEN
                | pygame.DOUBLEBUF
                | pygame.NOFRAME
                | pygame.HWSURFACE,
            )
            return

        else:
            # Iterate through drivers and attempt to init/set_mode
            for driver in ["rpi", "kmsdrm", "fbcon", "directfb", "svgalib"]:
                os.putenv("SDL_VIDEODRIVER", driver)
                try:
                    pygame.display.init()
                    size = (
                        pygame.display.Info().current_w,
                        pygame.display.Info().current_h,
                    )
                    if size == (480, 480):  # Fix for 480x480 mode offset
                        size = (640, 480)
                    self.screen = pygame.display.set_mode(
                        size,
                        pygame.FULLSCREEN
                        | pygame.DOUBLEBUF
                        | pygame.NOFRAME
                        | pygame.HWSURFACE,
                    )
                    print(
                        "Using driver: {0}, Framebuffer size: {1:d} x {2:d}".format(
                            driver, *size
                        )
                    )
                    return
                except pygame.error as e:
                    print('Driver "{0}" failed: {1}'.format(driver, e))
                    continue
                break

        print("All SDL drivers failed, falling back to raw framebuffer access.")
        self._rawfb = True
        os.putenv("SDL_VIDEODRIVER", "dummy")
        pygame.display.init()  # Need to init for .convert() to work
        self.screen = pygame.Surface((480, 480))

    def __del__(self):
        "Destructor to make sure pygame shuts down, etc."

    def _updatefb(self):
        fbdev = os.getenv("SDL_FBDEV", "/dev/fb0")
        with open(fbdev, "wb") as fb:
            fb.write(self.screen.convert(16, 0).get_buffer())

    # This code defines a function called blit_screen that takes in an array as its argument. 
    # The function sets up several variables at the beginning:
        # spacer is set to 70 and determines the size of the space between array items.
        # top_row is set to 120 and determines the position of the first item on the screen.
        # l and r are set to 50 and 120, respectively, and determine the starting position for the first item.
        # row is set to 0 and is used to keep track of the current row number.
    # The blit method is used to draw an image onto the screen object at the specified coordinates.
    # After the blit call, the value of r is increased by spacer, and the value of row is incremented by 1. 
    # If row is equal to 4, the values of row and l are reset to 0 and 270, respectively, and r is set to top_row again.
    # This process continues until all array items have been processed. The blit_screen function does not return any value.
    def blit_screen(self, items):
        # Set the size of the space between items and the position of the first item
        spacer = 70
        top_row = 120

        # Set the starting position for the first item
        l = 50
        r = top_row

        # Initialize the row counter
        row = 0

        # Iterate over the items in the array
        for index, item in enumerate(items):
            # Blit the item onto the screen at the specified position
            self.screen.blit(items[index], (l, r))

            # Increment the row position and row counter
            r += spacer
            row += 1

            # If we have reached the fourth row, reset the position and row counter
            if row == 4:
                row = 0
                l = 270
                r = top_row
    
    def setup_fonts(self):
        pygame.font.init()
        # Credit for this font: https://github.com/chrisys/train-departure-display/tree/main/src/fonts

        # The number here will change the font size and color
        game_font = pygame.font.Font("font/train-font.ttf", 50)
        font_color = (250, 250, 0)

        return game_font, font_color

    def scrolling_objects_loop(self, alert_queue, game_font, font_color, scroll_speed=3, clear_color=(0, 0, 0)):
        # Band surface size
        BAND_WIDTH = 480
        BAND_HEIGHT = 101
        obj_padding = 10

        # Update alert if new data in the queue
        if not alert_queue.empty():
            new_alert_data = alert_queue.get()
            if self.alert_result != new_alert_data:
                self.alert_result = new_alert_data

        pygame.draw.rect(self.screen, clear_color, (0, 0, BAND_WIDTH, BAND_HEIGHT)) # Clear top screen
        pygame.draw.rect(self.screen, clear_color, (0, 390, BAND_WIDTH, BAND_HEIGHT)) # Clear bottom screen

        self.top_x += scroll_speed
        self.bottom_x -= scroll_speed

        if self.top_x > BAND_WIDTH:
            self.top_x = -180

        self.screen.blit(self._img_double, (self.top_x, self.top_y))

        if isinstance(self.alert_result, str) and self.alert_result is not None and self.alert_result.strip() != "":
            text_surface = render_font(game_font, self.alert_result, font_color)
            text_width = text_surface.get_width()

            text_x = self.bottom_x + self._img_left.get_width() + obj_padding
            text_y = self.bottom_y + obj_padding

            text_rect = pygame.Rect(text_x, text_y, text_width, text_surface.get_height())

            if self.bottom_x < -(150 + text_width):
                self.bottom_x = BAND_WIDTH

            self.screen.blit(self._img_left, (self.bottom_x, self.bottom_y))
            self.screen.blit(text_surface, text_rect)
            self.screen.blit(self._img_right, (text_x + text_width + obj_padding, self.bottom_y))
        else:
            if self.bottom_x < -150:
                self.bottom_x = BAND_WIDTH
            self.screen.blit(self._img_double, (self.bottom_x, self.bottom_y))

    def update_thread(self, thread_desc, stop_flag, updater_func, updater_args, interval, queue=None):
        while self._running:
            if stop_flag.is_set():
                break  # Exit the loop if stop_flag is set
            if queue is None:
                updater_func(*updater_args)
            else:
                result = updater_func(*updater_args)
                queue.put(result)
            # Synchronize sleep with stop_flag.wait() for a specific interval
            stop_flag.wait(interval)
        print(f"{thread_desc} thread stopped.")

    def run(self):
        config = Transit_Config.get_config()
        trip_status = HSL_Trip_Update(config)
        service_message = HSL_Service_Alert(config)

        game_font, font_color = self.setup_fonts()

        alert_queue = queue.Queue() # Initialize the alert queue
        stop_flag = self.stop_flag # Stop thread flag

        trip_update_thread = threading.Thread(target=self.update_thread, args=("Metro status", stop_flag, display_times, (trip_status, game_font, font_color), 15))
        alert_update_thread = threading.Thread(target=self.update_thread, args=("Service alert", stop_flag, display_alert, (service_message,), 300, alert_queue))

        trip_update_thread.start()
        alert_update_thread.start()

        signal.signal(signal.SIGINT, self._exit)

        while self._running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._running = False

            self.scrolling_objects_loop(alert_queue, game_font, font_color)

            if self._rawfb:
                self._updatefb()
            else:
                pygame.display.update()
                pygame.event.pump()
                self._clock.tick(60) # 60fps

        stop_flag.set()
        trip_update_thread.join(timeout=10)
        alert_update_thread.join(timeout=10)
        pygame.quit()
        sys.exit(0)

def display_times(trip_status, game_font, font_color):

    statuses = trip_status.metro_status()

    if not statuses:
        return False

    results = {
        'first_metro_incoming': check_for_value(statuses[0], "Incoming"),
        'second_metro_incoming': check_for_value(statuses[1], "Incoming"),
        'first_metro_next': check_for_value(statuses[0], "Next"),
        'second_metro_next': check_for_value(statuses[1], "Next"),
        'first_metro_dest': check_for_value(statuses[0], "Destination"),
        'second_metro_dest': check_for_value(statuses[1], "Destination")
    }

    truncate = 6
    dests = ["{}..".format(result[:truncate]) if len(result) > truncate else result
            for result in [results['first_metro_dest'], results['second_metro_dest']]]
    first_metro_dest, second_metro_dest = [f"{dest}" for dest in dests]

    first_metro_incoming = f"{results['first_metro_incoming']} {min_or_mins(results['first_metro_incoming'])}"
    second_metro_incoming = f"{results['second_metro_incoming']} {min_or_mins(results['second_metro_incoming'])}"
    first_metro_text = "Next"
    second_metro_text = "Next"
    first_metro_next = f"{results['first_metro_next']} {min_or_mins(results['first_metro_next'])}"
    second_metro_next = f"{results['second_metro_next']} {min_or_mins(results['second_metro_next'])}"

    first_metro_dest = render_font(game_font, first_metro_dest, font_color)
    second_metro_dest = render_font(game_font, second_metro_dest, font_color)
    first_metro_incoming = render_font(game_font, first_metro_incoming, font_color)
    second_metro_incoming = render_font(game_font, second_metro_incoming, font_color)
    first_metro_text = render_font(game_font, first_metro_text, font_color)
    second_metro_text = render_font(game_font, second_metro_text, font_color)
    first_metro_next = render_font(game_font, first_metro_next, font_color)
    second_metro_next = render_font(game_font, second_metro_next, font_color)
        
    # Clear screen before rendering new data
    pygame.draw.rect(display.screen, (0, 0, 0), (0, 102, 480, 287))

    display.blit_screen(
        [
            first_metro_dest,
            first_metro_incoming,
            first_metro_text,
            first_metro_next,
            second_metro_dest,
            second_metro_incoming,
            second_metro_text,
            second_metro_next,
        ]
    )

def display_alert(string):

    message = string.service_alert()

    if not message:
        return ""

    return message

# Fix minutes display
def min_or_mins(wait_time):
    if wait_time is not None:
        wait_time = str(wait_time)
        if wait_time in ['0', '1']:
            return " min"
        else:
            return " mins"
    else:
        return " "

def check_for_value(obj, key):
    return obj[key] if key in obj else "?"

def render_font(font, text, font_color, bold=False):
    return font.render(text, bold, font_color)

def load_and_scale_image(path, size):
    img = pygame.image.load(path)
    img = pygame.transform.scale(img, size)
    return img.convert_alpha()

display = Hyperpixel2r()
display.run()