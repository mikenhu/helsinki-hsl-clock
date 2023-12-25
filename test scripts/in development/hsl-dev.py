import datetime
import urllib.request
import json

from google.transit import gtfs_realtime_pb2

# Get the stop ids, stop names, and route ids from https://transitfeeds.com/p/helsinki-regional-transport/735/latest/route
stop_id_with_names = {
    '1541601': 'Vuosari', 
    '1541602': 'Kivenlahti'
    }

# Metro route ID starts with 31M
route_id_metro = "31M"

# GTFS-RT feeds for HSL https://hsldevcom.github.io/gtfs_rt/
trip_update_url = "https://realtime.hsl.fi/realtime/trip-updates/v2/hsl"
service_alerts_url = "https://realtime.hsl.fi/realtime/service-alerts/v2/hsl"

def fetch_feed(url):
    feed = gtfs_realtime_pb2.FeedMessage()
    response = urllib.request.urlopen(url)
    feed.ParseFromString(response.read())
    return feed

class HSL_Trip_Update:
    def __init__(self, trip_update_url):
        self.trip_update_url = trip_update_url

    def get_metro_feed(self):
        return fetch_feed(self.trip_update_url)

    def metro_status(self):
        feed = self.get_metro_feed()
        current_time = datetime.datetime.now()

        # Create a dictionary mapping stop IDs to wait times
        # Create a dictionary with the stop names as keys and an empty list as the value for each key
        stop_times = {stop_id_name: [] for stop_id_name in stop_id_with_names.values()}
        # Iterate through the entities in the feed message
        for entity in feed.entity:
            # Check if the entity has a field called 'trip_update'
            if entity.HasField('trip_update'):
                # If it does, iterate through the stop time updates for that trip
                for stop_time_update in entity.trip_update.stop_time_update:
                    # Check if the stop ID of the current stop time update is in the list of stop IDs with names
                    if stop_time_update.stop_id in stop_id_with_names and stop_time_update.schedule_relationship == gtfs_realtime_pb2.TripUpdate.StopTimeUpdate.SCHEDULED:
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
            stop_id: [int(time.total_seconds() / 60) for time in wait_times]
            for stop_id, wait_times in stop_times.items()
        }

        # Create result dictionary
        result = {
            i: { 'Destination': dest, 'Coming': wait_times[0], 'Next': wait_times[1] }
            for i, (dest, wait_times) in enumerate(stop_times.items())
        }

        return result

    # Print messages for testing
    def print_metro_status(self):
        metro_status = self.metro_status()
        print(metro_status)
    
    # Write as json file
    def print_metro_status_to_file(self):
        stop_times = self.metro_status()

        # Serialize the data using json.dumps
        data = json.dumps(stop_times)

        # Write the serialized data to a file
        with open('stop_times.json', 'w') as f:
            f.write(data)

class HSL_Service_Alert:
    def __init__(self, service_alerts_url):
        self.service_alerts_url = service_alerts_url

    def get_service_alerts(self):
        return fetch_feed(self.service_alerts_url)

    def metro_alerts(self):
        # fetch the service alerts feed
        feed = self.get_service_alerts()
        # create a set to store unique alert messages
        alert_messages = set()

        # iterate over each entity in the feed
        for entity in feed.entity:
            # check if the entity has a field named 'alert'
            if entity.HasField('alert'):
                # iterate over the informed entities in the alert
                for informed_entity in entity.alert.informed_entity:
                    # get the route id of the informed entity
                    route_id = informed_entity.route_id
                    # check if the route id is part of the metro routes
                    if route_id.startswith(route_id_metro):
                        # get the start time of the active period for the alert and format it as a string
                        start_time = datetime.datetime.fromtimestamp(entity.alert.active_period[0].start).strftime('%d/%m/%Y %H:%M')
                        # get the end time of the active period for the alert and format it as a string
                        end_time = datetime.datetime.fromtimestamp(entity.alert.active_period[0].end).strftime('%d/%m/%Y %H:%M')
                        # iterate over the translations of the description text for the alert
                        for translation in entity.alert.description_text.translation:
                            # check if the language of the translation is English
                            if translation.language == 'en':          
                                # create the alert message by combining the translation text, start time, and end time
                                alert = (f"{translation.text} ({start_time} - {end_time})")
                                # add the alert message to the set of alert messages
                                alert_messages.add(alert)

        # return a list of the unique alert messages
        return (list(alert_messages))

    # Print messages for testing
    def print_metro_alert(self):
        alert = self.metro_alerts()
        print(alert)

hsl = HSL_Trip_Update(trip_update_url)

hsl.print_metro_status()

hsl_alert = HSL_Service_Alert(service_alerts_url)

hsl_alert.print_metro_alert()

# hsl.print_metro_status_to_file()
