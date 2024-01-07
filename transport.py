#!/usr/bin/env python3
import os
import sys
import signal

from hsl import *
from util import *

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
        size_square = (512 // 10, 512 // 10)
        self._img_double = load_and_scale_image("imgs/double-tram.png", size_double)
        self._img_left = load_and_scale_image("imgs/single-tram-left.png", size_single)
        self._img_right = load_and_scale_image("imgs/single-tram-right.png", size_single)
        self._img_warning = load_and_scale_image("imgs/warning.png", size_square)

        # Initiate queue
        self.trip_status = None
        self.alert_result = None
        # Define a flag to stop processes gracefully later
        self.stop_flag = multiprocessing.Event()
        
        # Set top and bottom bands starting coordinations
        self.top_band_x = 480
        self.top_band_y = 40
        self.bottom_band_x = -180
        self.bottom_band_y = 390

        # Set time table box surface
        self.table_x = 40
        self.table_y = 300
        self.start_cell_x = 0

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
    
    #--------------- Code for the clock starts here --------------------#
    
    def trip_table(self, data_queue, game_font, font_color, scroll_speed=0.15, clear_color=(0, 0, 0)):        
        # Usable rectangle surface is 400x260
        # Minus the middle space (maybe 20px width) -> (400-20)/2 = 190px width per column
        COL_SPACER = 20
        COL_WIDTH = 190
        COL_HEIGHT = 260
        ROW_SPACER = 70
        LEFT_COL_X = 40
        LEFT_COL_Y = 115
        RIGHT_COL_X = LEFT_COL_X + COL_SPACER + COL_WIDTH
        RIGHT_COL_Y = LEFT_COL_Y

        self.table_x -= scroll_speed

        # Update data
        check_queue_data(data_queue, self.trip_status)
        
        if self.trip_status is not None:
            # Clear screen before rendering new data
            pygame.draw.rect(self.screen, clear_color, (0, 102, 480, 287))
            status_count = len(self.trip_status)

            # Initialize row counter
            row = 1

            # Set the starting position for the first item
            x = LEFT_COL_X
            y = LEFT_COL_Y

            if status_count == 1:
                COL_WIDTH = 400

            # Only redener for 4 platforms
            if status_count <= 4:
                for location, times in self.trip_status.items():
                    text_render(self.screen, render_font(game_font, location, font_color), COL_WIDTH, self.table_x, x, y)
                    y += ROW_SPACER
                    row += 1
                    # Render setting for one platform
                    if status_count == 1:
                        for time in times:
                            text_render(self.screen, render_font(game_font, time, font_color), COL_WIDTH, self.table_x, x, y)
                            y += ROW_SPACER
                            row += 1

                            if 1 < len(times) < 3:
                                text_render(self.screen, render_font(game_font, "Next", font_color), COL_WIDTH, self.table_x, x, y)
                                y += ROW_SPACER
                                row += 1
                    # Render setting for two platforms
                    elif status_count == 2:
                        for time in times:
                            text_render(self.screen, render_font(game_font, time, font_color), COL_WIDTH, self.table_x, x, y)
                            y += ROW_SPACER
                            row += 1

                            if 1 < len(times) < 3:
                                text_render(self.screen, render_font(game_font, "Next", font_color), COL_WIDTH, self.table_x, x, y)
                                y += ROW_SPACER
                                row += 1

                        if row >= len(times):
                            row = 0
                            x = RIGHT_COL_X
                            y = RIGHT_COL_Y
                    # Render setting for 3 and 4 platforms
                    elif status_count in (3, 4):
                        text_render(self.screen, render_font(game_font, times[0], font_color), COL_WIDTH, self.table_x, x, y)
                        y += ROW_SPACER
                        row += 1
                        
                        if row > status_count:
                            row = 0
                            x = RIGHT_COL_X
                            y = RIGHT_COL_Y

    def scrolling_bands(self, data_queue, game_font, font_color, scroll_speed=3, clear_color=(0, 0, 0)):
        # Band surface size
        BAND_WIDTH = 480
        BAND_HEIGHT = 101
        PADDING = 10

        # Update alert
        check_queue_data(data_queue, self.alert_result)

        # Clear top and bottom screens
        for y_pos in (0, 390):
            pygame.draw.rect(self.screen, clear_color, (0, y_pos, BAND_WIDTH, BAND_HEIGHT))

        # Calculate the center of the top band rectangle
        top_band_center_x = (BAND_WIDTH - self._img_warning.get_width()) // 2
        top_band_center_y = (BAND_HEIGHT - self._img_warning.get_height()) // 2

        # Set up scroll speeds
        self.top_band_x += scroll_speed
        self.bottom_band_x -= scroll_speed

        if isinstance(self.alert_result, str) and self.alert_result is not None and self.alert_result.strip() != "":
            # Render top band with center aligned img
            self.screen.blit(self._img_warning, (top_band_center_x, top_band_center_y))
            self.screen.blit(self._img_left, (top_band_center_x - self._img_left.get_width() - PADDING, top_band_center_y))
            self.screen.blit(self._img_right, (top_band_center_x + self._img_warning.get_width() + PADDING, top_band_center_y))

            # Render bottom band with alert message
            text_surface = render_font(game_font, self.alert_result, font_color)
            text_width = text_surface.get_width()

            text_x = self.bottom_band_x + self._img_left.get_width() + PADDING
            text_y = self.bottom_band_y + PADDING

            text_rect = pygame.Rect(text_x, text_y, text_width, text_surface.get_height())

            if self.bottom_band_x < -(150 + text_width):
                self.bottom_band_x = BAND_WIDTH

            self.screen.blit(self._img_left, (self.bottom_band_x, self.bottom_band_y))
            self.screen.blit(text_surface, text_rect)
            self.screen.blit(self._img_right, (text_x + text_width + PADDING, self.bottom_band_y))
        else:
            # Reset the img scroll when they meet the border
            # Render top band
            if self.top_band_x > BAND_WIDTH:
                self.top_band_x = -180
            self.screen.blit(self._img_double, (self.top_band_x, self.top_band_y))

            # Render bottom band
            if self.bottom_band_x < -150:
                self.bottom_band_x = BAND_WIDTH
            self.screen.blit(self._img_double, (self.bottom_band_x, self.bottom_band_y))

    def run(self):
        config = Transit_Config.get_config()
        trip_status = HSL_Trip_Update(config)
        service_message = HSL_Service_Alert(config)

        game_font, font_color = setup_fonts()

        # Tested with single queue but not worth it
        trip_queue = multiprocessing.Queue()
        alert_queue = multiprocessing.Queue()
        stop_flag = self.stop_flag # Stop process flag

        trip_update_process = multiprocessing.Process(target=update_process, args=("Transport status update", stop_flag, fetch_data, (trip_status, 'transport_status'), 15, trip_queue))
        alert_update_process = multiprocessing.Process(target=update_process, args=("Service alert update", stop_flag, fetch_data, (service_message, 'service_alert'), 300, alert_queue))

        trip_update_process.start()
        alert_update_process.start()

        signal.signal(signal.SIGINT, self._exit)

        while self._running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._running = False

            self.trip_table(trip_queue, game_font, font_color)
            self.scrolling_bands(alert_queue, game_font, font_color)

            if self._rawfb:
                self._updatefb()
            else:
                pygame.display.update()
                pygame.event.pump()
                self._clock.tick(60) # 60fps

        stop_flag.set()
        trip_update_process.join()
        alert_update_process.join()
        
        pygame.quit()
        sys.exit(0)

display = Hyperpixel2r()
display.run()