import requests
import json
import time as t
from datetime import datetime
from dotenv import load_dotenv
import os

# === Load API Key ===
load_dotenv()
TRAIN_API_KEY = os.getenv('TRAIN_API_KEY')
TRAIN_BASE_URL = 'https://lapi.transitchicago.com/api/1.0/ttarrivals.aspx?'
MAX_PER_DIRECTION = 2  # Limit to 2 per direction
STATION_ID = 'mapid=40540'  # Wilson

# Build API URL for the station
API_URL = f"{TRAIN_BASE_URL}key={TRAIN_API_KEY}&{STATION_ID}&outputType=JSON"

def get_station_arrivals():
    try:
        response = requests.get(API_URL)
        data = response.json()

        now = datetime.now()
        arrivals_by_direction = {}

        for eta in data['ctatt']['eta']:
            route = eta['rt']
            dest = eta['destNm']
            minutes_away = (
                datetime.combine(now.date(), datetime.strptime(eta['arrT'].split('T')[1], "%H:%M:%S").time())
                - datetime.combine(now.date(), now.time())
            ).seconds // 60

            status = "Scheduled" if eta['isSch'] == '1' else "Tracked"

            # --- Purple Line Last Train ---
            last_train_flag = ""
            if route == "P" and eta.get('isFlt') == '1':
                last_train_flag = " (LAST TRAIN)"

            # --- Red Line Holiday Train ---
            holiday_flag = ""
            if route == "Red" and (eta.get('isSpcl') == '1' or
                                   "Holiday" in dest or
                                   "Santa" in dest):
                holiday_flag = " (HOLIDAY TRAIN)"

            key = f"{route} → {dest}"
            if key not in arrivals_by_direction:
                arrivals_by_direction[key] = []
            arrivals_by_direction[key].append((minutes_away, status, last_train_flag, holiday_flag))

        # Sort by time and limit to MAX_PER_DIRECTION
        for key in arrivals_by_direction:
            arrivals_by_direction[key] = sorted(arrivals_by_direction[key], key=lambda x: x[0])[:MAX_PER_DIRECTION]

        # Display results
        for k, arrivals in arrivals_by_direction.items():
            display_times = [
                f"{m} min ({s}){lt}{hf}"
                for m, s, lt, hf in arrivals
            ]
            print(f"{k}: {', '.join(display_times)}")

    except Exception as e:
        print(f"Error fetching arrivals: {e}")

# Loop to fetch every 20 seconds
while True:
    print("\nFetching train arrivals...")
    get_station_arrivals()
    t.sleep(20)