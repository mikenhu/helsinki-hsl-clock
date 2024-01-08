import pygame
import logging

util_logger = logging.getLogger(__name__)

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
                util_logger.info("Keyboard interrupted")
                break  # Exit the loop if KeyboardInterrupt occurs
    except Exception as e:
        util_logger.error(f"Exception occurred in {process_identifier} update process: {e}")
    util_logger.warning(f"{process_identifier} process stopped.")
    
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