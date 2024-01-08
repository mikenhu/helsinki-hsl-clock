import google.transit.gtfs_realtime_pb2 as gtfs
# import multiprocessing
import concurrent.futures
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

except FileNotFoundError as fnf_error:
    print(f"File not found error: {fnf_error}")
except PermissionError as perm_error:
    print(f"Permission error: {perm_error}")
except Exception as e:
    print(f"Error: {e}")

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

# Utilize multicores to process data from API
def process_feed_multicores(fetch_func):
    # pool = multiprocessing.Pool(processes=4)
    # result = pool.apply(fetch_func)
    # pool.close()
    # pool.join()
    # return result
    with concurrent.futures.ProcessPoolExecutor(max_workers=4) as executor:
        result = executor.submit(fetch_func)
        return result.result()

def write_to_file(input, file_name):
    result_str = str(input)
    with open(file_name, 'w') as file:
        file.write(result_str)

# Parse data from config.ini file
class Transit_Config:
    def __init__(self, trip_update_url, service_alerts_url, stops, language, time_row_num):
        self.trip_update_url = trip_update_url
        self.service_alerts_url = service_alerts_url
        self.stops = stops
        self.language = language
        self.time_row_num = time_row_num
    
    @staticmethod
    def get_config():
        config = configparser.ConfigParser()
        config.read("config.ini")
        if "HSL-CONFIG" not in config:
            logging.error("No or badly formatted 'HSL-CONFIG' section found in config file.")
            sys.exit(1)  # Exit with an error code indicating failure

        config_options = ["trip_update_url", "service_alerts_url", "stops", "language", "time_row_num"]
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
        self.stops = json.loads(self.transit_config.stops)
        self.stop_status = {stop['direction_name']: [] for stop in self.stops}

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

        trips = self.stop_status

        for entity in feed.entity:
            if entity.HasField('trip_update'):
                route_id = entity.trip_update.trip.route_id
                for stop_time_update in entity.trip_update.stop_time_update:
                    stop_id = stop_time_update.stop_id
                    arrival_time = stop_time_update.arrival.time
                    arrival_time_dt = datetime.datetime.fromtimestamp(arrival_time)
                    for stop in self.stops:
                        if stop_id == stop['stop_id'] and route_id in stop['route_id']:
                            if arrival_time_dt > current_time:
                                trips[stop['direction_name']].append(arrival_time)
        
        return trips

    def _process_stop_times(self, stop_times, current_time):
        num = int(self.transit_config.time_row_num)
        stop_times = {
            stop_id: [
                # Convert timestamp to datetime, calculate waiting time, and format
                f"{int(time.total_seconds() / 60)} {'mins' if int(time.total_seconds() / 60) > 1 else 'min'}" if time.total_seconds() != 0 else None
                for time in sorted([datetime.datetime.fromtimestamp(timestamp) - current_time for timestamp in wait_times])[:num]
                # Process each stop's wait times
            ]
            for stop_id, wait_times in stop_times.items()  # Loop through each stop
        } # 'Kivenlahti': ['6 mins', '12 mins'], 'Vuosaari': ['1 min', '6 mins']}
        
        print(stop_times)
        return stop_times

    def transport_status(self):
        return process_feed_multicores(self.process_feed)

class HSL_Service_Alert:
    def __init__(self, transit_config):
        self.transit_config = transit_config
        self._informed_ids = self._get_route_ids()
    
    def _get_route_ids(self):
        stops = json.loads(self.transit_config.stops)
        stop_ids = set()
        route_ids = set()

        for stop in stops:
            stop_ids.add(stop["stop_id"])
            route_ids.update(stop["route_id"])

        return list(stop_ids | route_ids)

    def process_alert(self):
        feed = fetch_feed(self.transit_config.service_alerts_url)

        if feed:
            alert_message = self._extract_service_alert(feed)
        else:
            logger.warning("Service alert fetch did not return any data.")

        return alert_message

    def _extract_service_alert(self, feed):
        messages = set()

        for entity in feed.entity:
            if entity.HasField('alert'):
                alert = self._process_alert_entity(entity)
                if alert:
                    messages.add(alert)
        
        if len(messages) == 1:
            return next(iter(messages))
        elif len(messages) > 1:
            return ' '.join(messages)
        else:
            return None

    def _process_alert_entity(self, entity):
        for informed_entity in entity.alert.informed_entity:
            route_id = informed_entity.route_id
            stop_id = informed_entity.stop_id
            if route_id in self._informed_ids or stop_id in self._informed_ids:
                # start_time = datetime.datetime.fromtimestamp(entity.alert.active_period[0].start)
                # end_time = datetime.datetime.fromtimestamp(entity.alert.active_period[0].end)
                # active_period_str = f"({start_time:%d/%m/%Y %H:%M} - {end_time:%d/%m/%Y %H:%M})"

                for translation in entity.alert.description_text.translation:
                    if translation.language == self.transit_config.language.strip('\"'):
                        # alert_message = f"{translation.text} {active_period_str}"
                        alert_message = f"{translation.text}"
                        return alert_message
        
        return ""

    def service_alert(self):
        return process_feed_multicores(self.process_alert)