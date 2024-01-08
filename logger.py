# Credit to https://stackoverflow.com/questions/15727420/using-logging-in-multiple-modules

from datetime import datetime
# import time
import os

## Init logging start 
import logging
import logging.handlers

def logger_init():
    try:
        # print("Start: " +__name__)
        foldername = "logs"
        filename = "error_logs.log"
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        logs_folder = os.path.join(script_dir, foldername)  # Path to the 'logs' folder
        error_log_file = os.path.join(logs_folder, datetime.now().strftime("%Y%m%d") + f"_{filename}")

        ## get logger
        logger = logging.getLogger() ## root logger
        logger.setLevel(logging.WARNING)

        # Create 'logs' folder if it doesn't exist
        os.makedirs(logs_folder, exist_ok=True)

        # Grant write permissions to the 'logs' folder and log file
        os.chmod(logs_folder, 0o777)  # Set write permissions for the 'logs' folder
            # with open(error_log_file, 'a'):  # Create/append to log file to ensure it exists
                # os.chmod(error_log_file, 0o666)  # Set write permissions for the log file

        # File handler
        # logfilename = datetime.now().strftime("%Y%m%d") + f"_{filename}"
        file = logging.handlers.TimedRotatingFileHandler(error_log_file, when='W0', interval=1, backupCount=4)
        fileformat = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        file.setLevel(logging.WARNING)
        file.setFormatter(fileformat)

        # Stream handler
        stream = logging.StreamHandler()
        streamformat = logging.Formatter("%(asctime)s [%(levelname)s]: %(name)s: %(message)s")
        stream.setLevel(logging.INFO)
        stream.setFormatter(streamformat)

        # Adding all handlers to the logs
        logger.addHandler(stream)
        logger.addHandler(file)
        
        # Log an initial message to confirm successful logger setup
        logger.info("Error log file created and logger configured successfully.")
    
    except FileNotFoundError as fnf_error:
        logger.error(f"File not found error: {fnf_error}")
    except PermissionError as perm_error:
        logger.error(f"Permission error: {perm_error}")
    except Exception as e:
        logger.error(f"Error: {e}")

# def logger_cleanup(path, days_to_keep):
#     lclogger = logging.getLogger(__name__)
#     logpath = f"{path}"
#     now = time.time()
#     for filename in os.listdir(logpath):
#         filestamp = os.stat(os.path.join(logpath, filename)).st_mtime
#         filecompare = now - days_to_keep * 86400
#         if  filestamp < filecompare:
#             lclogger.info("Delete old log " + filename)
#             try:
#                 os.remove(os.path.join(logpath, filename))
#             except Exception as e:
#                 lclogger.exception(e)
#                 continue