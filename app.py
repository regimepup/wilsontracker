import requests
import json
from datetime import datetime
import os
import threading
from dotenv import load_dotenv
from flask import Flask, render_template
import pytz

# Load environment variables (for API key)
load_dotenv()
TRAIN_API_KEY = os.getenv('TRAIN_API_KEY')
TRAIN_BASE_URL = 'https://lapi.transitchicago.com/api/1.0/ttarrivals.aspx?'
MAX_ARRIVALS = 'max=2'  # Limit arrivals to 2 per request

# Route configurations
ROUTES = {
    "Red": "rt=Red",
    "Purple": "rt=P"
}

# Wilson station information
STATION_ID = 'mapid=40540'
STOP_IDS = {
    "North": "stpid=30105",
    "South": "stpid=30106",
}

# Chicago timezone
CHICAGO_TZ = pytz.timezone("America/Chicago")

# Construct API URLs
def build_url(route, stop_id):
    return f"{TRAIN_BASE_URL}key={TRAIN_API_KEY}&{STATION_ID}&{ROUTES[route]}&{MAX_ARRIVALS}&{STOP_IDS[stop_id]}&outputType=JSON"

API_URLS = {
    "Howard": build_url("Red", "North"),
    "95th": build_url("Red", "South"),
    "Linden": build_url("Purple", "North"),
    "Loop": build_url("Purple", "South")
}

# Global cache for train arrival times
train_arrival_cache = {
    "Howard": [],
    "95th": [],
    "Linden": [],
    "Loop": []
}

# Function to fetch and process train arrivals
def get_arrivals(route_name, url):
    arrivals = []

    try:
        response = requests.get(url)
        data = json.loads(response.text)

        # Get current time in Chicago timezone
        now_chicago = datetime.now(CHICAGO_TZ)

        for eta in data['ctatt']['eta']:
            arrival_time_str = eta['arrT']
            print(f"Raw Arrival Time for {route_name}: {arrival_time_str}")  # Debugging

            # Parse API's arrival time (already in Chicago time)
            arrival_time_chicago = CHICAGO_TZ.localize(datetime.strptime(arrival_time_str, "%Y-%m-%dT%H:%M:%S"))

            # Calculate time difference in minutes
            time_difference = round((arrival_time_chicago - now_chicago).total_seconds() / 60)

            # Avoid showing negative values unless the difference is very small
            if time_difference < 1:
                arrivals.append("Due")
            else:
                arrivals.append(f"{time_difference} minutes")

    except Exception as e:
        print(f"Error fetching {route_name} arrivals: {e}")

    return arrivals

# Function to get all red line arrivals
def get_red_arrivals():
    return {
        "Howard": get_arrivals("Howard", API_URLS["Howard"]),
        "95th": get_arrivals("95th", API_URLS["95th"])
    }

# Function to get purple line arrivals
def get_purple_arrivals():
    return {
        "Linden": get_arrivals("Linden", API_URLS["Linden"]),
        "Loop": get_arrivals("Loop", API_URLS["Loop"])
    }

# Function to update the cached arrival times every 20 seconds
def update_cache():
    while True:
        print("Fetching new train arrivals...")
        red_arrivals = get_red_arrivals()
        purple_arrivals = get_purple_arrivals()

        # Update the global cache with the new data
        train_arrival_cache['Howard'] = red_arrivals['Howard']
        train_arrival_cache['95th'] = red_arrivals['95th']
        train_arrival_cache['Linden'] = purple_arrivals['Linden']
        train_arrival_cache['Loop'] = purple_arrivals['Loop']

        # Wait for 20 seconds before fetching again
        time.sleep(20)

# Flask app initialization
app = Flask(__name__)

# Start the background thread to update the cache
update_thread = threading.Thread(target=update_cache)
update_thread.daemon = True  # Daemon thread will stop when the main program stops
update_thread.start()

@app.route('/')
def index():
    # Fetch the cached arrival times
    train_times = {
        'Howard': train_arrival_cache['Howard'],
        '95th': train_arrival_cache['95th'],
        'Linden': train_arrival_cache['Linden'],
        'Loop': train_arrival_cache['Loop']
    }

    # Pass the train_times to the template
    return render_template('index.html', train_times=train_times)

if __name__ == "__main__":
    app.run(debug=True)
