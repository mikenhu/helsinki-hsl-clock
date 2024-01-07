import pygame
import multiprocessing

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
        print(f"Exception occurred in {process_identifier} update process: {e}")
    print(f"{process_identifier} process stopped.")