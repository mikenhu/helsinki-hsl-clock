import datetime
import requests
import json
import time
import socket
import configparser
import logging
import sys

from google.transit import gtfs_realtime_pb2

def fetch_feed(url):
    MAX_RETRIES = 5
    for _ in range(MAX_RETRIES):
        try:
            with requests.Session() as session:
                feed = gtfs_realtime_pb2.FeedMessage()
                response = session.get(url)
                feed.ParseFromString(response.content)
                return feed
        except requests.exceptions.RequestException as e:
            if isinstance(e.reason, socket.timeout):
                print(f"Error fetching feed: {e}. Retrying...")
            else:
                print(f"Error fetching feed: {e}.")
            time.sleep(30)
        except Exception as e:
            print(f"Error parsing feed: {e}.")
            return gtfs_realtime_pb2.FeedMessage()
    print("Exceeded maximum retries. Returning empty feed.")
    return gtfs_realtime_pb2.FeedMessage()

class Transit_Config:
    def __init__(self, stop_id_with_names, route_id_metro, trip_update_url, service_alerts_url):
        self.stop_id_with_names = stop_id_with_names
        self.route_id_metro = route_id_metro
        self.trip_update_url = trip_update_url
        self.service_alerts_url = service_alerts_url
    
    @staticmethod
    def get_config():
        config = configparser.ConfigParser()
        config.read("config.ini")
        if "HSL-CONFIG" not in config:
            logging.error("No or badly formatted 'HSL-CONFIG' section found in config file.")
            sys.exit(1)  # Exit with an error code indicating failure

        config_options = ["trip_update_url", "service_alerts_url", "stop_id_with_names", "route_id_metro"]
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
        
    def metro_status(self):
        feed = fetch_feed(self.transit_config.trip_update_url)
        current_time = datetime.datetime.now()

        # Create a dictionary mapping stop IDs to wait times
        stop_id_with_names = json.loads(self.transit_config.stop_id_with_names)
        # Create a dictionary with the stop names as keys and an empty list as the value for each key
        stop_times = {stop_id_name: [] for stop_id_name in stop_id_with_names.values()}
        # Iterate through the entities in the feed message
        for entity in feed.entity:
            # Check if the entity has a field called 'trip_update'
            if entity.HasField('trip_update'):
                # If it does, iterate through the stop time updates for that trip
                for stop_time_update in entity.trip_update.stop_time_update:
                    # Check if the stop ID of the current stop time update is in the list of stop IDs with names
                    # and if the schedule relationship is "SCHEDULED"
                    if stop_time_update.stop_id in stop_id_with_names: # and stop_time_update.schedule_relationship == gtfs_realtime_pb2.TripUpdate.StopTimeUpdate.SCHEDULED:
                        # If it is, get the arrival time for the stop
                        arrival_time = stop_time_update.arrival.time
                        # Convert the arrival time to a datetime object
                        arrival_time_dt = datetime.datetime.fromtimestamp(arrival_time)
                        # Check if the arrival time is after the current time
                        if arrival_time_dt > current_time:
                            # If it is, add the arrival time to the list of arrival times for the stop in the stop_times dictionary
                            stop_times[stop_id_with_names[stop_time_update.stop_id]].append(arrival_time)

        # Convert wait times to human-readable format and limit to 2 wait times per stop
        stop_times = {
            stop_id: sorted([datetime.datetime.fromtimestamp(timestamp) - current_time for timestamp in wait_times])[:2]
            for stop_id, wait_times in stop_times.items()
        }

        # Convert wait times to minutes
        stop_times = {
            stop_id: [int(time.total_seconds() / 60) if time.total_seconds() != 0 else None for time in wait_times]
            for stop_id, wait_times in stop_times.items()
        }

        # Create result dictionary and check the length of wait_times
        # and set the value of Next to an empty string if there are not enough elements in the list
        result = {
            i: { 
                'Destination': dest, 
                'Incoming': wait_times[0] if len(wait_times) >= 1 else None, 
                'Next': wait_times[1] if len(wait_times) >= 2 else None
            }
            for i, (dest, wait_times) in enumerate(stop_times.items())
        }
        
        print (result)
        return result


class HSL_Service_Alert:

    def __init__(self, transit_config):
        self.transit_config = transit_config

    def service_alert(self):
        # fetch the service alerts feed
        feed = fetch_feed(self.transit_config.service_alerts_url)
        alert_message = ""

        # iterate over each entity in the feed
        for entity in feed.entity:
            # check if the entity has a field named 'alert'
            if entity.HasField('alert'):
                # iterate over the informed entities in the alert
                for informed_entity in entity.alert.informed_entity:
                    # get the route id of the informed entity
                    route_id = informed_entity.route_id
                    # check if the route id is part of the metro routes
                    if route_id.startswith(self.transit_config.route_id_metro):
                        # convert the start and end times to datetime objects
                        start_time = datetime.datetime.fromtimestamp(entity.alert.active_period[0].start)
                        end_time = datetime.datetime.fromtimestamp(entity.alert.active_period[0].end)
                        # format the start and end times as a single string
                        active_period_str = f"({start_time:%d/%m/%Y %H:%M} - {end_time:%d/%m/%Y %H:%M})"
                        # iterate over the translations of the description text for the alert
                        for translation in entity.alert.description_text.translation:
                            # check if the language of the translation is English
                            if translation.language == 'en':
                                # create the alert message by combining the translation text and the active period string
                                alert_message = f"{translation.text} {active_period_str}"
                                # exit the loop early since we have found the English translation we need
                                break
                        # exit the loop early since we have found an informed entity whose route id starts with the correct prefix
                        break
        
        print (alert_message)
        return alert_message
