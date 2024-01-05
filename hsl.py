import google.transit.gtfs_realtime_pb2 as gtfs
import multiprocessing
import datetime
import requests
import json
import time
import socket
import configparser
import logging
import sys
import os

from logging.handlers import TimedRotatingFileHandler

# Get the directory path of the script
script_dir = os.path.dirname(os.path.abspath(__file__))
logs_folder = os.path.join(script_dir, 'logs')  # Path to the 'logs' folder
if not os.path.exists(logs_folder):
    os.makedirs(logs_folder)  # Create the 'logs' folder if it doesn't exist

# Define the file path for error logs within the 'logs' folder
error_log_file = os.path.join(logs_folder, 'error_logs.txt')

# Create 'logs' folder and grant write access to the folder and log file
try:
    os.makedirs(logs_folder, exist_ok=True)  # Create 'logs' folder if it doesn't exist
    os.chmod(logs_folder, 0o777)  # Set write permissions for the 'logs' folder
    with open(error_log_file, 'a'):  # Create/append to log file to ensure it exists
        os.chmod(error_log_file, 0o666)  # Set write permissions for the log file
except Exception as e:
    print(f"Error setting permissions: {e}")

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

try:
    # Log an initial message to confirm successful logger setup
    logger.info("Error log file created and logger configured successfully.")
except Exception as e:
    print(f"Error creating log file: {e}")

# API call
def fetch_feed(url):
    MAX_RETRIES = 10
    logger = logging.getLogger(__name__)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            session = requests.Session()
            feed = gtfs.FeedMessage()
            response = session.get(url)
            
            if response.status_code == 200:
                # print(f"Server status ({response.status_code})")
                feed.ParseFromString(response.content)
                return feed
            elif 500 <= response.status_code < 600:
                logger.warning(f"Server error ({response.status_code}): Retrying attempt {attempt}...")
            else:
                logger.error(f"Client error ({response.status_code}): Cannot fetch feed.")
                break  # Break the loop for non-retriable errors

        except requests.exceptions.RequestException as e:
            if isinstance(e, (socket.timeout, requests.exceptions.Timeout)):
                logger.error(f"Timeout error: {e}. Retrying attempt {attempt}...")
            elif isinstance(e, requests.exceptions.ConnectionError):
                logger.error(f"Connection error: {e}. Retrying attempt {attempt}...")
                time.sleep(5 ** attempt)  # Exponential backoff for connection errors
                continue  # Move to the next attempt with a new session
            else:
                logger.error(f"Request error: {e}.")
                sys.exit(1)
                break  # Break the loop for other request errors

        except Exception as e:
            logger.exception(f"Unexpected error: {e}.")
            logger.warning("Restarting Pi due to critical exception.")
            sys.exit(1)
            os.system("sudo reboot")  # Restart Pi for any exception
            break  # Break the loop for unexpected errors

        finally:
            session.close()  # Close the session after each attempt

    logger.error("Exceeded maximum retries. Returning empty feed.")
    return gtfs.FeedMessage()

# Circumvent a limitation in Python's multiprocessing module related to pickling
def execute_func(func):
    return func()

# Utilize multicores to process data from API
def process_feed_multicores(fetch_func):
    pool = multiprocessing.Pool(processes=4)
    result = pool.apply(execute_func, args=(fetch_func,))
    pool.close()
    pool.join()
    return result

# Parse data from config.ini file
class Transit_Config:
    def __init__(self, stop_id_with_names, route_id_metro, trip_update_url, service_alerts_url, language):
        self.stop_id_with_names = stop_id_with_names
        self.route_id_metro = route_id_metro
        self.trip_update_url = trip_update_url
        self.service_alerts_url = service_alerts_url
        self.language = language
    
    @staticmethod
    def get_config():
        config = configparser.ConfigParser()
        config.read("config.ini")
        if "HSL-CONFIG" not in config:
            logging.error("No or badly formatted 'HSL-CONFIG' section found in config file.")
            sys.exit(1)  # Exit with an error code indicating failure

        config_options = ["trip_update_url", "service_alerts_url", "stop_id_with_names", "route_id_metro", "language"]
        configured_values = {}
        for option in config_options:
            configured_value = config['HSL-CONFIG'].get(option)
            if not configured_value:
                logging.error(f"Missing {option} from config file, but it is required.")
                sys.exit(1)  # Exit with an error code indicating failure
            else:
                configured_values[option] = configured_value.strip()

        return Transit_Config(**configured_values)

class HSL_Trip_Update:
    def __init__(self, transit_config):
        self.transit_config = transit_config

    def process_feed(self):
        feed = fetch_feed(self.transit_config.trip_update_url)
        current_time = datetime.datetime.now()
        stop_times = self._extract_stop_times(feed, current_time)
        result = self._process_stop_times(stop_times, current_time)
        return result

    def _extract_stop_times(self, feed, current_time):
        if not feed:
            logger.warning("Trip status fetch did not return any data.")
            return {}

        stop_id_with_names = json.loads(self.transit_config.stop_id_with_names)
        stop_times = {stop_id_name: [] for stop_id_name in stop_id_with_names.values()}
        
        for entity in feed.entity:
            if entity.HasField('trip_update'):
                for stop_time_update in entity.trip_update.stop_time_update:
                    if stop_time_update.stop_id in stop_id_with_names:
                        arrival_time = stop_time_update.arrival.time
                        arrival_time_dt = datetime.datetime.fromtimestamp(arrival_time)
                        
                        if arrival_time_dt > current_time:
                            stop_times[stop_id_with_names[stop_time_update.stop_id]].append(arrival_time)
        
        return stop_times

    def _process_stop_times(self, stop_times, current_time):
        # stop_times = {
        #     stop_id: sorted([datetime.datetime.fromtimestamp(timestamp) - current_time for timestamp in wait_times])[:2
        #     for stop_id, wait_times in stop_times.items()
        # }

        # stop_times = {
        #     stop_id: [int(time.total_seconds() / 60) if time.total_seconds() != 0 else None for time in wait_times]
        #     for stop_id, wait_times in stop_times.items()
        # }

        # result = {
        #     i: {
        #         'Destination': dest,
        #         'Incoming': wait_times[0] if len(wait_times) >= 1 else None,
        #         'Next': wait_times[1] if len(wait_times) >= 2 else None
        #     }
        #     for i, (dest, wait_times) in enumerate(stop_times.items())
        # }

        stop_times2 = {
            stop_id: [
                # Convert timestamp to datetime, calculate waiting time, and format
                f"{int(time.total_seconds() / 60)} {'mins' if int(time.total_seconds() / 60) > 1 else 'min'}" if time.total_seconds() != 0 else None
                for time in sorted([datetime.datetime.fromtimestamp(timestamp) - current_time for timestamp in wait_times])[:3]
                # Process each stop's wait times
            ]
            for stop_id, wait_times in stop_times.items()  # Loop through each stop
        } # 'Kivenlahti': ['6 mins', '12 mins', '20 mins'], 'Vuosaari': ['1 min', '6 mins', '12 mins']}
        print(stop_times2)
        # return stop_times

        result = {
            i: {
                'Destination': dest,
                'Incoming': wait_times[0],
                'Next': wait_times[1]
            }
            for i, (dest, wait_times) in enumerate(stop_times2.items())
        }

        print(result)
        return result


    def metro_status(self):
        return process_feed_multicores(self.process_feed)

class HSL_Service_Alert:
    def __init__(self, transit_config):
        self.transit_config = transit_config

    def process_alert(self):
        feed = fetch_feed(self.transit_config.service_alerts_url)
        alert_message = ""

        if feed:
            alert_message = self._extract_service_alert(feed)
        else:
            logger.warning("Service alert fetch did not return any data.")

        return alert_message

    def _extract_service_alert(self, feed):
        for entity in feed.entity:
            if entity.HasField('alert'):
                alert_message = self._process_alert_entity(entity)
                if alert_message:
                    return alert_message

        return ""

    def _process_alert_entity(self, entity):
        for informed_entity in entity.alert.informed_entity:
            route_id = informed_entity.route_id
            if route_id.startswith(self.transit_config.route_id_metro.strip('\"')):
                start_time = datetime.datetime.fromtimestamp(entity.alert.active_period[0].start)
                end_time = datetime.datetime.fromtimestamp(entity.alert.active_period[0].end)
                active_period_str = f"({start_time:%d/%m/%Y %H:%M} - {end_time:%d/%m/%Y %H:%M})"

                for translation in entity.alert.description_text.translation:
                    if translation.language == self.transit_config.language.strip('\"'):
                        alert_message = f"{translation.text} {active_period_str}"
                        return alert_message

        return ""

    def service_alert(self):
        return process_feed_multicores(self.process_alert)
