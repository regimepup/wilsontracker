import requests
import json
from datetime import datetime, time
import os
from dotenv import load_dotenv
from flask import Flask, render_template

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

# Construct API URLs
def build_url(route, stop_id):
    return f"{TRAIN_BASE_URL}key={TRAIN_API_KEY}&{STATION_ID}&{ROUTES[route]}&{MAX_ARRIVALS}&{STOP_IDS[stop_id]}&outputType=JSON"


API_URLS = {
    "Howard": build_url("Red", "North"),
    "95th": build_url("Red", "South"),
    "Linden": build_url("Purple", "North"),
    "Loop": build_url("Purple", "South")
}

# Function to fetch and process train arrivals
def get_arrivals(route_name, url):
    arrivals = []

    try:
        response = requests.get(url)
        print(f"Fetching {route_name} from {url}")  # Debugging line
        print("Response Status Code:", response.status_code)  # Debugging line
        print("Response Text:", response.text)  # Debugging line
        data = json.loads(response.text)

        now = datetime.now()
        current_time = now.time()

        for eta in data['ctatt']['eta']:
            arrival_time_str = eta['arrT'].split('T')[1]  # Extract time (HH:MM:SS)
            arrival_time = datetime.strptime(arrival_time_str, "%H:%M:%S").time()

            # Calculate time difference in minutes
            time_difference = (datetime.combine(now.date(), arrival_time) - datetime.combine(now.date(),
                                                                                             current_time)).seconds // 60

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


# Flask app initialization
app = Flask(__name__)

@app.route('/')
def index():
    # Fetch the arrival times
    red_arrivals = get_red_arrivals()
    purple_arrivals = get_purple_arrivals()

    # Combine the data into a single dictionary
    train_times = {
        'Howard': red_arrivals['Howard'],
        '95th': red_arrivals['95th'],
        'Linden': purple_arrivals['Linden'],
        'Loop': purple_arrivals['Loop']
    }

    # Pass the train_times to the template
    return render_template('index.html', train_times=train_times)

if __name__ == "__main__":
    app.run(debug=True)
