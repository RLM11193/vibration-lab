from flask import Flask, request, jsonify
import ephem
from datetime import datetime

app = Flask(__name__)

@app.route("/")
def home():
    return "Vibration Lab is running!"

@app.route("/ascendant", methods=["GET"])
def ascendant():
    # Example usage:
    # /ascendant?date=2025-08-13+07:30&lat=40.0&lon=-105.0
    date_str = request.args.get("date")
    lat = float(request.args.get("lat"))
    lon = float(request.args.get("lon"))

    dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M")

    observer = ephem.Observer()
    observer.lat, observer.lon = str(lat), str(lon)
    observer.date = dt

    asc = ephem.FixedBody()
    asc._ra, asc._dec = observer.radec_of(0, 0)  # eastern horizon point

    return jsonify({
        "date": date_str,
        "latitude": lat,
        "longitude": lon,
        "ascendant_ra": str(asc._ra),
        "ascendant_dec": str(asc._dec)
    })

if __name__ == "__main__":
    app.run(debug=True)
