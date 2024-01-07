#!/usr/bin/env python3
import os
import sys
import signal

from hsl import *
from util import *

# Credit to Pimoroni for the Hyperpixel2r class
class Transport:
    def __init__(self, screen, _exit, _rawfb, _updatefb):
        self.screen = screen
        self._exit = _exit
        self._rawfb = _rawfb
        self._updatefb = _updatefb
        
        # Load the image, reduce the size of the tram icon and create img object
        # Credit for the icon source: https://www.flaticon.com/free-icons/train
        self._img_double = load_and_scale_image("imgs/double-tram.png", (1050 // 6, 367 // 6))
        self._img_left = load_and_scale_image("imgs/single-tram-left.png", (512 // 6, 358 // 6))
        self._img_right = load_and_scale_image("imgs/single-tram-right.png", (512 // 6, 358 // 6))
        self._img_warning = load_and_scale_image("imgs/warning.png", (512 // 10, 512 // 10))

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
        
        self._clock = pygame.time.Clock()
        self._running = True
    
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
        if not data_queue.empty():
            updated_data = data_queue.get()
            # Only update if there is new data
            if self.trip_status != updated_data:
                self.trip_status = updated_data
        
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
        if not data_queue.empty():
            updated_data = data_queue.get()
            # Only update if there is new data
            if self.alert_result != updated_data:
                self.alert_result = updated_data

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
                self._updatefb
            else:
                pygame.display.update()
                pygame.event.pump()
                self._clock.tick(60) # 60fps

        stop_flag.set()
        trip_update_process.join()
        alert_update_process.join()
        
        pygame.quit()
        sys.exit(0)