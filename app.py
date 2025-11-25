# catboost-api/app.py

from flask import Flask, request, jsonify
from flask_cors import CORS
from catboost import CatBoostRegressor
import pandas as pd
import numpy as np
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

# --- 1. Load Model ---
MODEL_PATH = os.path.join("data", "catboost_traffic_model.cbm")
model = CatBoostRegressor()

try:
    model.load_model(MODEL_PATH)
    print(f"✅ CatBoost model loaded successfully from {MODEL_PATH}")
except Exception as e:
    print(f"❌ FATAL: Error loading model: {e}")

# --- 2. Knowledge Base (Coordinates -> Road Name) ---
# Using CLEAN names (matching your CSV/Training Data)
KNOWN_LOCATIONS = {
    "100 Feet Road":       (12.9081, 77.6476),
    "Anil Kumble Circle":  (12.9756, 77.6066),
    "Ballari Road":        (13.0068, 77.5813),
    "CMH Road":            (12.9790, 77.6408),
    "Hebbal Flyover":      (13.0354, 77.5971),
    "Hosur Road":          (12.9345, 77.6101),
    "ITPL Main Road":      (12.9893, 77.7282),
    "Jayanagar 4th Block": (12.9295, 77.5794),
    "Marathahalli Bridge": (12.9552, 77.6984),
    "Sarjapur Road":       (12.9245, 77.6493),
    "Silk Board Junction": (12.9172, 77.6228),
    "Sony World Junction": (12.9363, 77.6265),
    "South End Circle":    (12.9368, 77.5757),
    "Trinity Circle":      (12.9729, 77.6147),
    "Tumkur Road":         (13.0292, 77.5399),
    "Yeshwanthpur Circle": (13.0263, 77.5507)
}

def get_real_road_name(lat, lng):
    closest_road = None
    min_distance = float('inf')
    for name, (road_lat, road_lng) in KNOWN_LOCATIONS.items():
        dist = (lat - road_lat)**2 + (lng - road_lng)**2
        if dist < min_distance:
            min_distance = dist
            closest_road = name
    return closest_road

# --- 3. Prediction Endpoint ---
@app.route('/predict/', methods=['POST'])
def predict():
    try:
        data = request.get_json()
        
        # Inputs
        lat = data['coordinates']['lat']
        lng = data['coordinates']['lng']
        
        # Features
        road_name = get_real_road_name(lat, lng)
        
        now = datetime.now()
        input_features = pd.DataFrame({
            'hour': [now.hour],
            'day_of_week': [now.weekday()],
            'is_weekend': [1 if now.weekday() >= 5 else 0],
            'Road_Intersection_Name': [road_name]
        })

        # Raw Prediction (Daily Volume)
        raw_pred = model.predict(input_features)[0]
        raw_pred = max(0, float(raw_pred))

        # Convert to Hourly (Div by 12)
        hourly_volume = raw_pred / 12.0

        # --- CALIBRATED THRESHOLDS (Based on your Log Data) ---
        # Your Range: ~1500 to ~2800
        
        # Default: Clear Roads
        congestion_level = 0.2
        congestion_label = "Low"
        avg_speed = 55

        # 1. Moderate Traffic (> 1,600 cars)
        # Matches: Yeshwanthpur, Marathahalli
        if hourly_volume > 1600:
            congestion_level = 0.5
            congestion_label = "Moderate"
            avg_speed = 40
            
        # 2. Heavy Traffic (> 2,100 cars)
        # Matches: ITPL, South End Circle
        if hourly_volume > 2100:
            congestion_level = 0.8
            congestion_label = "High"
            avg_speed = 25
            
        # 3. Severe Gridlock (> 2,600 cars)
        # Matches: Hebbal Flyover, Anil Kumble Circle
        if hourly_volume > 2600:
            congestion_level = 0.95
            congestion_label = "Severe"
            avg_speed = 10

        response = {
            "predictions": {
                "congestion": {
                    "level": congestion_level,
                    "label": congestion_label
                },
                "avgSpeed": avg_speed,
                "predictedVolume": round(hourly_volume) 
            },
            "featureImportance": {
                "labels": ["Road", "Time of Day", "Event Impact"],
                "data": [0.6, 0.4, 0] 
            },
            "mappedLocation": road_name
        }
        
        return jsonify(response)

    except Exception as e:
        print("Error:", e)
        return jsonify({"error": str(e)}), 500
@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "CatBoost API is running"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8003)