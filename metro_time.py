#!/usr/bin/env python3
import logging
import os
import sys
import signal
import pygame
import time
import threading
import configparser

from hsl import HSL_Trip_Update
from hsl import HSL_Service_Alert

COMING = "Coming"
NEXT = "Next"
DESTINATION = "Destination"
MESSAGE = "Message"


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
        # self._clock = pygame.time.Clock()
        self._colour = (255, 0, 255)

        # Load the image and create img object
        def load_and_scale_image(path, size):
            img = pygame.image.load(path)
            img = pygame.transform.scale(img, size)
            return img.convert_alpha()

        size_single = (512 // 6, 358 // 6)
        size_double = (1050 // 6, 367 // 6)

        self._img_double = load_and_scale_image("imgs/double-tram.png", size_double)
        self._img_left = load_and_scale_image("imgs/single-tram-left.png", size_single)
        self._img_right = load_and_scale_image("imgs/single-tram-right.png", size_single)


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


    # This code defines a function called blit_screen that takes in a list of dictionaries called items as its argument. 
    # The function sets up several variables at the beginning:
        # spacer is set to 70 and determines the size of the space between items.
        # top_row is set to 120 and determines the position of the first item on the screen.
        # l and r are set to 50 and 120, respectively, and determine the starting position for the first item.
        # row is set to 0 and is used to keep track of the current row number.
    # The function then enters a loop that iterates over each dictionary in items. 
    # For each dictionary, the function checks if the dictionary has a key called "item" and a non-empty value. 
    # If this is the case, the function calls the blit method on self.screen with the value of the "item" key and a tuple of coordinates as arguments. 
    # The blit method is used to draw an image onto the screen object at the specified coordinates.

    # After the blit call, the value of r is increased by spacer, and the value of row is incremented by 1. 
    # If row is equal to 4, the values of row and l are reset to 0 and 270, respectively, and r is set to top_row again.
    #  This process continues until all dictionaries in items have been processed. The blit_screen function does not return any value.
    def blit_screen(self, items):
        # Set the size of the space between items and the position of the first item
        spacer = 70
        top_row = 120

        # Set the starting position for the first item
        l = 50
        r = top_row

        # Initialize the row counter
        row = 0

        # Iterate over the items in the list
        for item in items:
            # Check if the item exists
            if item["item"]:
                # Blit the item onto the screen at the specified position
                self.screen.blit(item["item"], (l, r))

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

        # The number here will change the font size
        game_font = pygame.font.Font("font/train-font.ttf", 50)
        font_colour = (250, 250, 0)

        return game_font, font_colour

    def scrolling_object_loop(self, scroll_speed=3, clear_color=(0, 0, 0)):
        
        # Image surface size
        BAND_WIDTH = 480
        BAND_HEIGHT = 101

        # image_positions = [(self.top_x, self.top_y), (self.bottom_x, self.bottom_y)]

        # Clear the top and bottom parts of the screen
        pygame.draw.rect(self.screen, clear_color, (0, 0, BAND_WIDTH, BAND_HEIGHT)) # top screen
        pygame.draw.rect(self.screen, clear_color, (0, 390, BAND_WIDTH, BAND_HEIGHT)) # bottom screen

        # Update the position of the image
        self.top_x -= scroll_speed
        self.bottom_x += scroll_speed

        # If the image has moved off the screen, reset its position
        if self.top_x < -150:
            self.top_x = 480
        if self.bottom_x > 480:
            self.bottom_x = -180

        # Draw the scrolling image on the top and bottom of the screen
        self.screen.blit(self._img_double, (self.top_x, self.top_y))
        self.screen.blit(self._img_double, (self.bottom_x, self.bottom_y))

    def display_update_thread(self, metro, game_font, font_colour, start_time):
        while self._running:
            elapsed_time = time.perf_counter() - start_time
            if elapsed_time > 30:
                start_time = time.perf_counter()
                display_times(metro, game_font, font_colour)


    def run(self):
        # Read the config file to get your API token and metro line
        config = get_config()
        metro = HSL_Trip_Update(config['stop_id_with_names'], config['route_id_metro'], config['trip_update_url'])
        service_message = HSL_Service_Alert (config['service_alerts_url'])

        # Configure the font and colour
        game_font, font_colour = self.setup_fonts()

        # Set the starting position for the text
        self.top_x = 480 # start off the screen to the right
        self.top_y = 40

        self.bottom_x = -180
        self.bottom_y = 390

        self._running = True
        signal.signal(signal.SIGINT, self._exit)

        start_time = time.perf_counter()
        
        # Create the Clock object
        clock = pygame.time.Clock()

        display_update_thread = threading.Thread(target=self.display_update_thread, args=(metro, game_font, font_colour, start_time))
        display_update_thread.start()
        
        while self._running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._running = False
                    break
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self._running = False
                        break

            self.scrolling_object_loop()

            if self._rawfb:
                self._updatefb()
            else:
                pygame.display.update()
                # Limit the loop to the specified frame rate
                clock.tick(60)
                pygame.event.pump()

        display_update_thread.join()
        pygame.quit()
        sys.exit(0)

def display_times(metro, game_font, font_colour):

    statuses = metro.metro_status()

    if not statuses:
        return False

    results = {
        'first_metro_incoming': check_for_value(statuses[0], COMING),
        'second_metro_incoming': check_for_value(statuses[1], COMING),
        'first_metro_next': check_for_value(statuses[0], NEXT),
        'second_metro_next': check_for_value(statuses[1], NEXT),
        'first_metro_dest': check_for_value(statuses[0], DESTINATION),
        'second_metro_dest': check_for_value(statuses[1], DESTINATION)
    }

    truncate = 6
    dests = ["{}..".format(result[:truncate]) if len(result) > truncate else result
            for result in [results['first_metro_dest'], results['second_metro_dest']]]
    first_metro_dest, second_metro_dest = [f"{dest}  " for dest in dests]

    first_metro_incoming = f"{results['first_metro_incoming']} {min_or_mins(results['first_metro_incoming'])}"
    second_metro_incoming = f"{results['second_metro_incoming']} {min_or_mins(results['second_metro_incoming'])}"
    first_metro_text = "Next"
    second_metro_text = "Next"
    first_metro_next = f"{results['first_metro_next']} {min_or_mins(results['first_metro_next'])}"
    second_metro_next = f"{results['second_metro_next']} {min_or_mins(results['second_metro_next'])}"

    first_metro_dest = render_font(game_font, first_metro_dest, font_colour)
    second_metro_dest = render_font(game_font, second_metro_dest, font_colour)
    first_metro_incoming = render_font(game_font, first_metro_incoming, font_colour)
    second_metro_incoming = render_font(game_font, second_metro_incoming, font_colour)
    first_metro_text = render_font(game_font, first_metro_text, font_colour)
    second_metro_text = render_font(game_font, second_metro_text, font_colour)
    first_metro_next = render_font(game_font, first_metro_next, font_colour)
    second_metro_next = render_font(game_font, second_metro_next, font_colour)
        
    # Clear screen before rendering new data
    pygame.draw.rect(display.screen, (0, 0, 0), (0, 102, 480, 287))

    display.blit_screen(
        [
            {"item": first_metro_dest, "type": "text"},
            # {"item": first_metro_header, "type": "text"},
            {"item": first_metro_incoming, "type": "text"},
            {"item": first_metro_text, "type": "text"},
            {"item": first_metro_next, "type": "text"},
            # {"item": first_metro_image, "type": "image"},

            {"item": second_metro_dest, "type": "text"},
            # {"item": second_metro_header, "type": "text"},
            {"item": second_metro_incoming, "type": "text"},
            {"item": second_metro_text, "type": "text"},
            {"item": second_metro_next, "type": "text"},
            # {"item": second_metro_image, "type": "image"},
        ]
    )

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


def render_font(font, text, font_colour, bold=False):
    return font.render(text, bold, font_colour)


def get_config():
    config = configparser.ConfigParser()
    config.read("config.ini")
    if "HSL-CONFIG" not in config:
        logging.info("No config file found, or badly formatted.")
        return {}
    config_options = ["trip_update_url", "service_alerts_url", "stop_id_with_names", "route_id_metro"]
    configured_values = {}
    for option in config_options:
        configured_value = config['HSL-CONFIG'][f'{option}']
        if not configured_value:
            logging.error(f"Missing {option} from config file, but it is required.")
            sys.exit()
        else:
            configured_values[option] = configured_value.strip()

    return configured_values

display = Hyperpixel2r()
display.run()
