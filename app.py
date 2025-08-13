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

# Globals
cached_arrivals = {
    "Red": {"Howard": [], "95th": []},
    "Purple": {"Linden": [], "Loop": []}
}
last_updated = None
cache_lock = threading.Lock()

TRAIN_API_KEY = os.getenv("TRAIN_API_KEY")
TRAIN_BASE_URL = "https://lapi.transitchicago.com/api/1.0/ttarrivals.aspx?"
STATION_ID = "mapid=40540"
API_URL = f"{TRAIN_BASE_URL}key={TRAIN_API_KEY}&{STATION_ID}&outputType=JSON"
MAX_PER_DIRECTION = 2

def fetch_arrivals():
    global cached_arrivals, last_updated
    while True:
        try:
            # Check API key
            if not TRAIN_API_KEY:
                print("[ERROR] TRAIN_API_KEY is not set or accessible!")
                time.sleep(10)
                continue

            # Fetch from API
            response = requests.get(API_URL)
            print(f"[{datetime.now()}] Status Code: {response.status_code}")

            # Print first 500 chars of response for inspection
            print(f"[DEBUG] Response snippet: {response.text[:500]}")

            response.raise_for_status()  # Raise an exception for HTTP errors

            data = response.json()

            # Initialize new arrivals
            new_arrivals = {
                "Red": {"Howard": [], "95th": []},
                "Purple": {"Linden": [], "Loop": []}
            }

            now = datetime.now()

            if "ctatt" not in data or "eta" not in data["ctatt"]:
                print("[ERROR] 'ctatt' or 'eta' key missing in API response")
                time.sleep(10)
                continue

            for eta in data["ctatt"]["eta"]:
                route = eta.get("rt")
                dest = eta.get("destNm")
                arr_time_str = eta.get("arrT", "").split("T")[1] if eta.get("arrT") else None
                if not route or not dest or not arr_time_str:
                    print(f"[WARNING] Skipping incomplete entry: {eta}")
                    continue

                minutes_away = (
                    datetime.combine(now.date(), datetime.strptime(arr_time_str, "%H:%M:%S").time())
                    - datetime.combine(now.date(), now.time())
                ).seconds // 60

                status = "Scheduled" if eta.get("isSch") == "1" else "Tracked"
                last_train = True if route == "P" and eta.get("isFlt") == "1" else False
                holiday_train = True if route == "Red" and (eta.get("isSpcl") == "1" or "Holiday" in dest or "Santa" in dest) else False

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

            # Sort & limit
            for line in new_arrivals:
                for dest in new_arrivals[line]:
                    new_arrivals[line][dest] = sorted(new_arrivals[line][dest], key=lambda x: x["minutes"])[:MAX_PER_DIRECTION]

            # Update cache
            with cache_lock:
                cached_arrivals = new_arrivals
                last_updated = datetime.now()
                print(f"[INFO] Arrivals updated at {last_updated}")

        except Exception as e:
            print(f"[ERROR] Exception while fetching arrivals: {e}")

        # Wait 10 seconds
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