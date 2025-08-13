from flask import Flask, render_template
import requests
import os
from datetime import datetime
from dotenv import load_dotenv
import threading
import time
from flask import jsonify

load_dotenv()

app = Flask(__name__)

TRAIN_API_KEY = os.getenv('TRAIN_API_KEY')
TRAIN_BASE_URL = 'https://lapi.transitchicago.com/api/1.0/ttarrivals.aspx?'
STATION_ID = 'mapid=40540'  # Wilson
API_URL = f"{TRAIN_BASE_URL}key={TRAIN_API_KEY}&{STATION_ID}&outputType=JSON"
MAX_PER_DIRECTION = 2

# === Shared cache for arrivals ===
cached_arrivals = {
    "Red": {"Howard": [], "95th": []},
    "Purple": {"Linden": [], "Loop": []}
}
last_updated = None

# === Lock for thread safety ===
cache_lock = threading.Lock()


def fetch_arrivals():
    """Fetch arrivals from CTA API and update cached_arrivals."""
    global cached_arrivals, last_updated  # <-- add last_updated here
    while True:
        try:
            response = requests.get(API_URL)
            data = response.json()
            now = datetime.now()

            new_arrivals = {
                "Red": {"Howard": [], "95th": []},
                "Purple": {"Linden": [], "Loop": []}
            }

            for eta in data['ctatt']['eta']:
                route = eta['rt']
                dest = eta['destNm']
                arr_time_str = eta['arrT'].split('T')[1]
                minutes_away = (
                    datetime.combine(now.date(), datetime.strptime(arr_time_str, "%H:%M:%S").time())
                    - datetime.combine(now.date(), now.time())
                ).seconds // 60

                status = "Scheduled" if eta['isSch'] == '1' else "Tracked"
                last_train = True if route == "P" and eta.get('isFlt') == '1' else False
                holiday_train = True if route == "Red" and (eta.get('isSpcl') == '1' or "Holiday" in dest or "Santa" in dest) else False

                train_data = {
                    "minutes": minutes_away,
                    "status": status,
                    "last_train": last_train,
                    "holiday_train": holiday_train
                }

                if route == "Red":
                    if "Howard" in dest:
                        new_arrivals["Red"]["Howard"].append(train_data)
                    elif "95th" in dest:
                        new_arrivals["Red"]["95th"].append(train_data)
                elif route == "P":
                    if "Linden" in dest:
                        new_arrivals["Purple"]["Linden"].append(train_data)
                    elif "Loop" in dest:
                        new_arrivals["Purple"]["Loop"].append(train_data)

            # Sort & limit to MAX_PER_DIRECTION
            for line in new_arrivals:
                for dest in new_arrivals[line]:
                    new_arrivals[line][dest] = sorted(new_arrivals[line][dest], key=lambda x: x["minutes"])[:MAX_PER_DIRECTION]

            # Update the cached data atomically and store last updated timestamp
            with cache_lock:
                cached_arrivals = new_arrivals
                last_updated = datetime.now()  # <-- this is the line to add

        except Exception as e:
            print(f"Error fetching arrivals: {e}")

        # Wait 10 seconds before the next request
        time.sleep(10)



@app.route("/")
def index():
    with cache_lock:
        arrivals = cached_arrivals.copy()
        updated_copy = last_updated
    return render_template("index.html", arrivals=arrivals, last_updated=updated_copy)
@app.route("/arrivals_json")
def arrivals_json():
    with cache_lock:
        arrivals_copy = cached_arrivals.copy()
        updated_copy = last_updated
    # Format timestamp for frontend
    timestamp_str = updated_copy.strftime('%H:%M:%S') if updated_copy else None
    return jsonify({"arrivals": arrivals_copy, "last_updated": timestamp_str})

if __name__ == "__main__":
    # Start background thread to fetch arrivals every 10 seconds
    threading.Thread(target=fetch_arrivals, daemon=True).start()
    app.run(debug=True)