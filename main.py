import requests
import json
import time as t
from datetime import datetime, time
from dotenv import load_dotenv
import os

# General settings
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
    schedule_status = []

    try:
        response = requests.get(url)
        data = json.loads(response.text)

        now = datetime.now()
        current_time = now.time()

        for eta in data['ctatt']['eta']:
            arrival_time_str = eta['arrT'].split('T')[1]  # Extract time (HH:MM:SS)
            arrival_time = datetime.strptime(arrival_time_str, "%H:%M:%S").time()

            # Calculate time difference in minutes
            time_difference = (datetime.combine(now.date(), arrival_time) - datetime.combine(now.date(),
                                                                                             current_time)).seconds // 60

            # Append formatted time difference
            arrivals.append(f"{time_difference} minutes")

            # Append schedule status
            schedule_status.append("Scheduled" if eta['isSch'] == '1' else "Tracked")

        print(f"{route_name} Arrivals: {arrivals}")
        print(f"{route_name} Schedule Status: {schedule_status}")

    except Exception as e:
        print(f"Error fetching {route_name} arrivals: {e}")


# Function to get all red line arrivals
def get_red_arrivals():
    get_arrivals("Howard", API_URLS["Howard"])
    get_arrivals("95th", API_URLS["95th"])


# Function to get purple line arrivals with time-based filtering
def get_purple_arrivals():
    now = datetime.now()
    current_time = now.time()

    # Define the time ranges
    morning_start, morning_end = time(5, 2), time(9, 10)
    afternoon_start, afternoon_end = time(14, 8), time(18, 18)

    # Check if it's Monday-Friday and within the time range
    if now.weekday() < 5 and (
            morning_start <= current_time <= morning_end or afternoon_start <= current_time <= afternoon_end):
        get_arrivals("Loop", API_URLS["Loop"])
        get_arrivals("Linden", API_URLS["Linden"])
    else:
        print("Purple Line arrivals not available outside of service hours.")


# Loop to fetch data every 20 seconds
while True:
    print("\nFetching train arrivals...")
    get_red_arrivals()
    get_purple_arrivals()
    t.sleep(20)  # Wait 20 seconds before fetching again
