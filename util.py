import pygame
import os
import logging
from logging.handlers import TimedRotatingFileHandler

logger = None  # Initialize logger

def setup_logger():
    try:
        # Get the directory path of the script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        logs_folder = os.path.join(script_dir, 'logs')  # Path to the 'logs' folder
        error_log_file = os.path.join(logs_folder, 'error_logs.txt')

        # Create 'logs' folder if it doesn't exist
        os.makedirs(logs_folder, exist_ok=True)

        # Grant write permissions to the 'logs' folder and log file
        os.chmod(logs_folder, 0o777)  # Set write permissions for the 'logs' folder
        with open(error_log_file, 'a'):  # Create/append to log file to ensure it exists
            os.chmod(error_log_file, 0o666)  # Set write permissions for the log file

        # Create a logger
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG)  # Set the logging level

        # Create a TimedRotatingFileHandler for log rotation
        handler = TimedRotatingFileHandler(
            error_log_file, when='W0', interval=1, backupCount=4
        )
        handler.setLevel(logging.WARNING)  # Set the handler's logging level

        # Define a log formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)  # Apply the formatter to the handler

        # Add the handler to the logger
        logger.addHandler(handler)

        # Log an initial message to confirm successful logger setup
        logger.info("Error log file created and logger configured successfully.")
        
        return logger # Return the configured logger

    except FileNotFoundError as fnf_error:
        print(f"File not found error: {fnf_error}")
    except PermissionError as perm_error:
        print(f"Permission error: {perm_error}")
    except Exception as e:
        print(f"Error: {e}")

def setup_fonts():
    pygame.font.init()
    # Credit for this font: https://github.com/chrisys/train-departure-display/tree/main/src/fonts
    # The number here will change the font size and color
    game_font = pygame.font.Font("font/train-font.ttf", 50)
    font_color = (250, 250, 0)
    return game_font, font_color

def render_font(font, text, font_color, bold=False):
    return font.render(text, bold, font_color)

def load_and_scale_image(path, size):
    img = pygame.image.load(path)
    img = pygame.transform.scale(img, size)
    return img.convert_alpha()

# Passing the instance of the classes along with the method name as a string
def fetch_data(instance, method_name):
    # Retrieve the method based on the provided method_name from the instance
    method = getattr(instance, method_name, None)
    if method:
        # If methos exists, call the method and store its result in the result variable
        result = method()
        if not result:
            # If the result is empty, return False if it's a boolean, otherwise return an empty string
            return False if isinstance(result, bool) else ""
        return result
    # If the method doesn't exist, return False
    return False

# Process API calls and push result onto queue
def update_process(process_identifier, stop_flag, updater_func, updater_args, interval, queue):
    try:
        while not stop_flag.is_set():
            try:
                result = updater_func(*updater_args)
                queue.put(result)
                # Synchronize sleep with stop_flag.wait() for a specific interval
                stop_flag.wait(interval)
            except KeyboardInterrupt:
                break  # Exit the loop if KeyboardInterrupt occurs
    except Exception as e:
        logger.error(f"Exception occurred in {process_identifier} update process: {e}")
    logger.info(f"{process_identifier} process stopped.")

def text_render(display, text_surface, allowed_width, start_x, clip_area_x, clip_area_y):
    spacer_width = 25
    text_length = text_surface.get_width() + spacer_width
    # Scroll text if it's longer than allowed width
    if text_length - spacer_width > allowed_width:
        # Calculate the effective x-coordinate for scrolling in the right-to-left direction
        effective_x = (start_x % text_length) - text_length
        # Define the clipping area
        clip_area = pygame.Rect(clip_area_x, clip_area_y, allowed_width, text_surface.get_height())
        # Set the clipping region on the screen
        display.set_clip(clip_area)
        # Calculate the position to blit the text within the clipping area
        start_x = clip_area_x + effective_x
        # Ensure the text scrolls continuously
        while start_x < clip_area_x + allowed_width:
            display.blit(text_surface, (start_x, clip_area_y))
            start_x += text_length
        # Reset the clipping region
        display.set_clip(None)
    else:
        # Align the text in the middle
        text_rect = text_surface.get_rect()
        text_x = clip_area_x + (allowed_width - text_rect.width) // 2
        text_y = clip_area_y + (text_surface.get_height() - text_rect.height) // 2
        display.blit(text_surface, (text_x, text_y))

setup_logger()