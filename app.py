from flask import Flask, render_template, jsonify
import requests
import os
from datetime import datetime
from dotenv import load_dotenv
import threading
import pytz

load_dotenv()

app = Flask(__name__)

# === Timezone setup ===
central_tz = pytz.timezone("America/Chicago")

# === CTA API setup ===
TRAIN_API_KEY = os.getenv("TRAIN_API_KEY")
TRAIN_BASE_URL = "https://lapi.transitchicago.com/api/1.0/ttarrivals.aspx?"
STATION_ID = "mapid=40540"  # Wilson
API_URL = f"{TRAIN_BASE_URL}key={TRAIN_API_KEY}&{STATION_ID}&outputType=JSON"
MAX_PER_DIRECTION = 2

# === Cache ===
cached_arrivals = {
    "Red": {"Howard": [], "95th": []},
    "Purple": {"Linden": [], "Loop": []}
}
last_updated = None
cache_lock = threading.Lock()


# === Function to fetch arrivals from CTA API ===
def get_arrivals():
    global cached_arrivals, last_updated
    now_utc = datetime.now(pytz.UTC)  # always get UTC first
    now_central = now_utc.astimezone(central_tz)  # convert to Central
    fetch_new = False

    with cache_lock:
        if last_updated is None or (now_central - last_updated).total_seconds() > 10:
            fetch_new = True

    if fetch_new:
        try:
            if not TRAIN_API_KEY:
                print("[ERROR] TRAIN_API_KEY is missing!")
                return cached_arrivals, last_updated

            response = requests.get(API_URL)
            response.raise_for_status()
            data = response.json()

            new_arrivals = {
                "Red": {"Howard": [], "95th": []},
                "Purple": {"Linden": [], "Loop": []}
            }

            if "ctatt" not in data or "eta" not in data["ctatt"]:
                print("[ERROR] Invalid API response")
                return cached_arrivals, last_updated

            for eta in data["ctatt"]["eta"]:
                route = eta.get("rt")
                dest = eta.get("destNm")
                arr_time_str = eta.get("arrT", "").split("T")[1] if eta.get("arrT") else None
                if not route or not dest or not arr_time_str:
                    continue

                minutes_away = (
                    datetime.combine(now_central.date(), datetime.strptime(arr_time_str, "%H:%M:%S").time())
                    - datetime.combine(now_central.date(), now_central.time())
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

            # Sort and limit
            for line in new_arrivals:
                for dest in new_arrivals[line]:
                    new_arrivals[line][dest] = sorted(new_arrivals[line][dest], key=lambda x: x["minutes"])[:MAX_PER_DIRECTION]

            # Update cache with Central Time
            with cache_lock:
                cached_arrivals = new_arrivals
                last_updated = now_central
                print(f"[INFO] Arrivals updated at {last_updated.strftime('%H:%M:%S')} Central Time")

        except Exception as e:
            print(f"[ERROR] Exception fetching arrivals: {e}")

    with cache_lock:
        return cached_arrivals, last_updated


# === Routes ===
@app.route("/")
def index():
    arrivals, updated_copy = get_arrivals()
    return render_template("index.html", arrivals=arrivals, last_updated=updated_copy)


@app.route("/arrivals_json")
def arrivals_json():
    arrivals, updated_copy = get_arrivals()
    timestamp_str = updated_copy.strftime('%H:%M:%S') if updated_copy else None
    return jsonify({"arrivals": arrivals, "last_updated": timestamp_str})
@app.route("/next_arrivals_text")
def next_arrivals_text():
    with cache_lock:
        arrivals_copy = cached_arrivals.copy()
    output = []
    for line, directions in arrivals_copy.items():
        for direction, trains in directions.items():
            for t in trains:
                output.append(f"{line} to {direction}: {t['minutes']} min ({t['status']})")
    return "\n".join(output), 200, {'Content-Type': 'text/plain'}
if __name__ == "__main__":
    # Start background thread to fetch arrivals every 10 seconds
    threading.Thread(target=fetch_arrivals, daemon=True).start()
    app.run(debug=True)