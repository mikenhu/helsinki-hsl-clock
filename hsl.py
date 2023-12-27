import datetime
import requests
import json
import time
import socket

from google.transit import gtfs_realtime_pb2

def fetch_feed(url):
    with requests.Session() as session:
        while True:
            try:
                feed = gtfs_realtime_pb2.FeedMessage()
                response = session.get(url)
                feed.ParseFromString(response.content)
                return feed
            except requests.exceptions.RequestException as e:
                # If there was a network error, print an error message and try again
                if isinstance(e.reason, socket.timeout):
                    print(f"Error fetching feed: {e}")
                    print("Trying again in 30 seconds...")
                    time.sleep(30)
                else:
                    # If there was a different error, print an error message and return an empty feed
                    print(f"Error fetching feed: {e}")
                    return gtfs_realtime_pb2.FeedMessage()
            except Exception as e:
                # If there was a different error, print an error message and return an empty feed
                print(f"Error parsing feed: {e}")
                return gtfs_realtime_pb2.FeedMessage()

class HSL_Trip_Update:

    def __init__(self, stop_id_with_names, route_id_metro, trip_update_url):
        self.stop_id_with_names = stop_id_with_names
        self.route_id_metro = route_id_metro
        self.trip_update_url = trip_update_url

    def get_metro_feed(self):
        with requests.Session() as session:
            while True:
                try:
                    feed = fetch_feed(self.trip_update_url)
                    return feed
                except requests.exceptions.RequestException as e:
                    # If there was a network error, print an error message and try again
                    print(f"Error fetching metro feed: {e}")
                    print("Trying again in 30 seconds...")
                    time.sleep(30)
                except Exception as e:
                    # If there was a different error, print an error message and return an empty feed
                    print(f"Error parsing metro feed: {e}")
                    return gtfs_realtime_pb2.FeedMessage()

    def metro_status(self):
        feed = self.get_metro_feed()
        current_time = datetime.datetime.now()

        # Create a dictionary mapping stop IDs to wait times
        stop_id_with_names = json.loads(self.stop_id_with_names)
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
                'Coming': wait_times[0] if len(wait_times) >= 1 else None, 
                'Next': wait_times[1] if len(wait_times) >= 2 else None
            }
            for i, (dest, wait_times) in enumerate(stop_times.items())
        }
        
        print (result)
        return result


class HSL_Service_Alert:

    def __init__(self, route_id_metro, service_alerts_url):
        self.route_id_metro = route_id_metro
        self.service_alerts_url = service_alerts_url

    def get_service_alert(self): 
        with requests.Session() as session:
            while True:
                try:
                    feed = fetch_feed(self.service_alerts_url)
                    return feed
                except requests.exceptions.RequestException as e:
                    # If there was a network error, print an error message and try again
                    print(f"Error fetching service alerts feed: {e}")
                    print("Trying again in 30 seconds...")
                    time.sleep(30)
                except Exception as e:
                    # If there was a different error, print an error message and return an empty feed
                    print(f"Error parsing service alerts feed: {e}")
                    return gtfs_realtime_pb2.FeedMessage()

    def service_alert(self):
        # fetch the service alerts feed
        feed = self.get_service_alert()
        alert_message = set()

        # iterate over each entity in the feed
        for entity in feed.entity:
            # check if the entity has a field named 'alert'
            if entity.HasField('alert'):
                # iterate over the informed entities in the alert
                for informed_entity in entity.alert.informed_entity:
                    # get the route id of the informed entity
                    route_id = informed_entity.route_id
                    # check if the route id is part of the metro routes
                    if route_id.startswith(self.route_id_metro):
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
                                alert = f"{translation.text} {active_period_str}"
                                # add the alert message
                                alert_message.add(alert)
                                # exit the loop early since we have found the English translation we need
                                break
                        # exit the loop early since we have found an informed entity whose route id starts with the correct prefix
                        break

        return alert_message
