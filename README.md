<p align="center">
  <img src="https://raw.githubusercontent.com/PrajwalShetty-114/CatBoost-Model/master/logo.png" alt="logo" width="120" height="120"/>
</p>

<p align="center">
  <h1>🚦 Smart Context Predictor — CatBoost Traffic Microservice</h1>

  <!-- Badges -->
  <p>
  <a href="https://www.python.org/"><img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&style=for-the-badge"/></a>
  <a href="https://flask.palletsprojects.com/"><img alt="Flask" src="https://img.shields.io/badge/Flask-3.0.0-lightgrey?logo=flask&style=for-the-badge"/></a>
  <a href="https://catboost.ai/"><img alt="CatBoost" src="https://img.shields.io/badge/CatBoost-%20Regressor-orange?logo=catboost&style=for-the-badge"/></a>
  <a href="https://www.docker.com/"><img alt="Docker" src="https://img.shields.io/badge/Docker-ready-blue?logo=docker&style=for-the-badge"/></a>
  <a href="https://render.com/"><img alt="Render" src="https://img.shields.io/badge/Deploy-Render-6f42c1?logo=render&style=for-the-badge"/></a>
  </p>

  <p><em>Lightweight Flask microservice serving a pre-trained CatBoost regression model for traffic volume & congestion prediction.</em></p>
</p>

---

**🧐 About the "Smart Context" Model**

- Purpose: Predicts traffic volume and congestion at a fine-grained road/intersection level using spatial coordinates + time context.
- Strength: The model was trained with CatBoost, which natively handles categorical features (notably road/intersection names). This makes the model robust with minimal manual feature engineering for roads and intersection names.
- Input signals: Current time-of-day, day-of-week and the nearest known road/intersection (mapped from Lat/Lng).

**Pure AI principle (Important)**: The service relies strictly on the CatBoost model's learned mapping from data — there are no hardcoded event multipliers or handcrafted scaling factors to simulate events. All event-like impacts must emerge from the training data and the model. The only deterministic post-processing is conversion from a daily raw model output into an hourly estimate and a small calibrated mapping to human-friendly congestion labels (see pipeline below).

---

**⚙️ How It Works (The Logic Pipeline)**

This service implements a concise 3-step prediction pipeline inside `app.py` (function: `predict()`):

1) Spatial Lookup — mapping coordinates to a Road Name (Nearest Neighbor) 📍
- The service keeps a small knowledge base `KNOWN_LOCATIONS` (in `app.py`) mapping human-friendly road/intersection names to representative coordinates.
- When a request provides latitude & longitude, `get_real_road_name(lat, lng)` computes squared Euclidean distance to each known coordinate and returns the closest name.
- This returned name is used as the categorical feature `Road_Intersection_Name` — CatBoost natively consumes this categorical label without manual encoding.

2) Baseline Prediction — model inference with CatBoost 🧠
- The server assembles a single-row DataFrame with features: `hour`, `day_of_week`, `is_weekend`, and `Road_Intersection_Name`.
- It loads the CatBoost model file `data/catboost_traffic_model.cbm` and calls `model.predict(...)` producing a raw daily volume estimate (the model was trained to predict total daily vehicle volume for the given road/time context).
- Raw prediction is clipped to be >= 0.

3) Smart Calibration — hourly mapping & human-friendly congestion levels ⚖️
- The code converts the model's daily estimate into an hourly estimate by dividing by 12.0:
  - `hourly_volume = max(0, raw_pred) / 12.0`
- Then it maps `hourly_volume` into congestion buckets using calibrated thresholds (derived from logged data):
  - Default: Low — `level = 0.2`, `label = "Low"`, `avgSpeed = 55`
  - Moderate: `hourly_volume > 1600` -> `level = 0.5`, `label = "Moderate"`, `avgSpeed = 40`
  - High: `hourly_volume > 2100` -> `level = 0.8`, `label = "High"`, `avgSpeed = 25`
  - Severe: `hourly_volume > 2600` -> `level = 0.95`, `label = "Severe"`, `avgSpeed = 10`
- The service also returns a simple `featureImportance` object in the response for transparency (labels: `Road`, `Time of Day`, `Event Impact` — example weights are used: `[0.6, 0.4, 0]`).

Notes:
- The mapping thresholds and averages are deterministic post-processing chosen to convert statistical model outputs into operationally meaningful categories — they do not inject event multipliers.
- The `Event Impact` importance slot is present for product-level UX but is unused in the core model (0 weight in the shipped model metadata).

---

**🔌 API Documentation**

Base URL: `http://<host>:8003/` (app listens on `0.0.0.0:8003` by default)

- POST `/predict/` — predict congestion & hourly volume
  - Content-Type: `application/json`
  - Body (required): JSON with `coordinates` object containing `lat` and `lng`.

Sample Request (JSON):

```json
{
  "coordinates": {
    "lat": 12.9552,
    "lng": 77.6984
  },
  "event": "concert_nearby"   
}
```

- `event` is accepted in the request for compatibility with upstream gateways, but note: the current microservice does not apply ad-hoc event multipliers — event signals must be reflected in the model's training data to impact predictions (Pure AI principle).

Sample Response (JSON):

```json
{
  "predictions": {
    "congestion": { "level": 0.5, "label": "Moderate" },
    "avgSpeed": 40,
    "predictedVolume": 1700
  },
  "featureImportance": {
    "labels": ["Road", "Time of Day", "Event Impact"],
    "data": [0.6, 0.4, 0]
  },
  "mappedLocation": "Marathahalli Bridge"
}
```

Fields explained:
- `predictions.congestion.level`: numeric severity [0..1]
- `predictions.congestion.label`: human-friendly label
- `predictions.avgSpeed`: estimated average speed (km/h) for congestion label
- `predictions.predictedVolume`: rounded hourly vehicle count estimate
- `featureImportance`: a lightweight explanation object
- `mappedLocation`: the canonical road/intersection name selected from `KNOWN_LOCATIONS`

---

**📐 Architecture Notes**

- This repository is a focused microservice providing a single purpose: mapping (coordinates + time) → congestion prediction.
- Intended Usage: called by an upstream Node.js Gateway (or API Gateway) which is responsible for authentication, routing, higher-level orchestration, and event enrichment. The microservice is NOT intended to be called directly by end users or browsers.
- Runtime: lightweight Flask application that loads a CatBoost model from `data/catboost_traffic_model.cbm` on startup.

---

**🛠️ Setup & Installation**

1) Clone repository

```bash
git clone https://github.com/PrajwalShetty-114/CatBoost-Model.git
cd CatBoost-Model
```

2) Python virtual environment (recommended `.venv`) — create & activate

```bash
# Create virtualenv (Unix/Windows powershell/cmd all supported)
python -m venv .venv

# Bash / Git Bash (Windows):
source .venv/Scripts/activate
# Or (Unix/WSL):
# source .venv/bin/activate

# PowerShell on Windows:
# .\.venv\Scripts\Activate.ps1
```

3) Git LFS (important) — model binary is large (`.cbm`) and should be stored with Git LFS

```bash
# Install Git LFS (system step, once per machine):
# https://git-lfs.github.com/ -> follow your OS installer

git lfs install
git lfs track "data/*.cbm"
git add .gitattributes
# After this any .cbm you `git add` will be committed to LFS
```

4) Install Python dependencies

```bash
pip install -r requirements.txt
```

5) Verify model file is present

```bash
ls -l data/catboost_traffic_model.cbm
```

6) Run the development server

```bash
python app.py
# or (production with gunicorn):
# gunicorn --bind 0.0.0.0:8003 app:app
```

---

**🐳 Docker & Deployment (Render)**

This project includes a `Dockerfile` (simple Docker instructions below). The service is suitable for container deployment (for example, Render or other container hosts).

Build & Run locally with Docker:

```bash
# Build image (from repo root)
docker build -t smart-context-predictor:latest .

# Run container forwarding port 8003
docker run -p 8003:8003 --env FLASK_ENV=production smart-context-predictor:latest
```

Render deployment notes:
- Use a private or public repo containing the `Dockerfile` and `data/catboost_traffic_model.cbm` (tracked with Git LFS).
- Configure Render to build the Docker image and expose port `8003`.

Example `Dockerfile` (reference):

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app
EXPOSE 8003
CMD ["python", "app.py"]
```

---

**🔒 Security & Operational Notes**

- The model file is binary and must be handled via Git LFS to avoid repository bloat.
- The microservice intentionally performs minimal input validation — in production place a gateway in front (Node.js Gateway) to sanitize input, rate-limit, and authenticate requests.
- Monitor memory usage on startup: loading CatBoost models can be memory-heavy; provision accordingly.

---

**🧪 Testing & Validation**

- Use the sample POST request above to validate and confirm responses.
- If the model file is missing, the service prints an error on startup and some endpoints may return 500.

---

**🧾 Development Tips**

- To change or extend `KNOWN_LOCATIONS`, edit `app.py` and keep the coordinate names consistent with the model's training labels.
- If you need to account for events or temporary incidents not present in training data, consider: 1) implementing an upstream event-enrichment service that provides historical examples for the model retraining, or 2) retraining the CatBoost model with event flags so that the model learns event impacts directly (preferred — keeps service Pure AI).

---

**Credits & Contact**

- Built as part of the Traffic Flow Prediction tooling.
- Maintainer: Prajwal Shetty — see repository for contact & issues.

---

<p align="center">Made with ❤️ · <strong>Smart Context Predictor</strong> · CatBoost powered</p>
