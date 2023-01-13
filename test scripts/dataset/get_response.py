import json
import google.transit.gtfs_realtime_pb2 as gtfs_realtime
import urllib.request
import google.protobuf.json_format as json_format

# URL of the GTFS-RT feed
url = "https://realtime.hsl.fi/realtime/trip-updates/v2/hsl"

def get_gtfs_rt_feed():
  # Send a request to the GTFS-RT feed and parse the response
  response = urllib.request.urlopen(url)
  feed = gtfs_realtime.FeedMessage()
  feed.ParseFromString(response.read())

  return feed

# Convert the GTFS-RT feed to a JSON object
def gtfs_rt_to_json(feed):
  return json.loads(json_format.MessageToJson(feed))

# Get the GTFS-RT feed and convert it to a JSON object
feed = get_gtfs_rt_feed()
gtfs_rt_json = gtfs_rt_to_json(feed)

# Save the JSON object to a file
with open("gtfs-rt.json", "w") as f:
  json.dump(gtfs_rt_json, f, indent=2)
