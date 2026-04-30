#!/usr/bin/env python3
"""
Weather API – Flask (Python)

Features
---------
* GET /weather?city=<city>      – returns JSON (real or stub)
* Caches results in Redis for 12 hours
* Rate‑limited (default 60 req / minute per IP)
* Reads configuration from .env (API key, Redis URL, limits)
* /health endpoint for quick health checks
* / (root) returns a friendly JSON welcome message
"""

import json
import os
from datetime import datetime, timedelta

import requests
import redis
from flask import Flask, jsonify, request, abort, redirect, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv

# --------------------------------------------------------------
# 0️⃣ Load environment variables from .env (if present)
# --------------------------------------------------------------
load_dotenv()                     # populates os.getenv()
VC_API_KEY = os.getenv("VC_API_KEY", "").strip()
print(f"DEBUG: The API Key being used is: '{VC_API_KEY}'")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
RATE_LIMIT_WINDOW_MS = int(os.getenv("RATE_LIMIT_WINDOW_MS", "60000"))
RATE_LIMIT_MAX       = int(os.getenv("RATE_LIMIT_MAX", "60"))

# --------------------------------------------------------------
# 1️⃣ Create Flask app + rate limiter
# --------------------------------------------------------------
app = Flask(__name__)

limiter = Limiter(
    app=app, 
    key_func=get_remote_address, 
    default_limits=[f"{RATE_LIMIT_MAX}/{RATE_LIMIT_WINDOW_MS // 1000} second"]
)
# --------------------------------------------------------------
# 2️⃣ Initialise Redis client (decode_responses=True → strings)
# --------------------------------------------------------------
try:
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    # Test the connection (PING)
    redis_client.ping()
    print(f"✅  Connected to Redis at {REDIS_URL}")
except Exception as exc:
    redis_client = None
    print(f"⚠️  Could not connect to Redis ({REDIS_URL}) – caching disabled.")
    print(f"    Reason: {exc}")

# --------------------------------------------------------------
# 3️⃣ Helper: build Visual Crossing request URL
# --------------------------------------------------------------
VC_BASE_URL = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"

def build_vc_url(city: str) -> str:
    """
    Build the full URL for Visual Crossing.
    We ask for the *current* day only, metric units, JSON response.
    """
    today = datetime.utcnow().strftime("%Y-%m-%d")
    params = {
        "key": VC_API_KEY,
        "unitGroup": "metric",
        "include": "current",
        "contentType": "json",
    }
    # encode the city + date part
    city_part = f"{city}/{today}"
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{VC_BASE_URL}/{city_part}?{query}"

# --------------------------------------------------------------
# 4️⃣ Stub weather (used when no API key is supplied)
# --------------------------------------------------------------
def stub_weather(city: str) -> dict:
    return {
        "location": city,
        "current": {
            "temp": 20,
            "description": "Clear sky",
            "humidity": 60,
            "windSpeed": 5,
        },
        "forecast": []   # empty list – you could add dummy days if you wish
    }

# --------------------------------------------------------------
# 5️⃣ Core endpoint – GET /weather?city=<city>
# --------------------------------------------------------------
@app.route("/weather", methods=["GET"])
@limiter.limit("60 per minute")   # explicit for clarity (same as default)
def get_weather():
    city = request.args.get("city", "").strip()
    if not city:
        return jsonify({"error": "Missing required query param: city"}), 400

    cache_key = f"weather:{city.lower()}"

    # ------------------- 1️⃣ Try Redis cache -------------------
    try:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)  # sync client
        redis_client.ping()
        print(f"✅  Connected to Redis at {REDIS_URL}")
    except Exception as e:
        redis_client = None
        print(f"⚠️  Could not connect to Redis ({REDIS_URL}): {e}")

    # ------------------- 2️⃣ No cache → call external API -------------------
    if not VC_API_KEY:
        # No key → return stub data immediately
        weather = stub_weather(city)
        source = "stub"
    else:
        url = build_vc_url(city)
        try:
            resp = requests.get(url, timeout=8)   # 8‑second timeout
            resp.raise_for_status()             # raise on 4xx/5xx
            data = resp.json()

            # Pull out the fields we want (simplified)
            weather = {
                "location": data.get("resolvedAddress", city),
                "current": {
                    "temp": data["currentConditions"]["temp"],
                    "description": data["currentConditions"]["conditions"],
                    "humidity": data["currentConditions"]["humidity"],
                    "windSpeed": data["currentConditions"]["windspeed"],
                },
                # Optional 3‑day forecast (if you want)
                "forecast": [
                    {
                        "date": d["datetime"],
                        "tempHigh": d["tempmax"],
                        "tempLow": d["tempmin"],
                        "description": d["conditions"],
                    }
                    for d in data.get("days", [])[:3]
                ],
            }
            source = "api"
        except requests.exceptions.HTTPError as http_err:
            # Forward Visual Crossing's error message
            status = http_err.response.status_code
            
            # --- SAFE JSON EXTRACTION ---
            try:
                # Try to get the "message" field from the JSON response
                msg = http_err.response.json().get("message", http_err.response.reason)
            except Exception:
                # If the response isn't JSON (e.g. HTML error page), use the HTTP reason
                msg = http_err.response.reason
            # ---------------------------
            
            return jsonify({"error": f"Provider error {status}: {msg}"}), status


    # ------------------- 3️⃣ Store in Redis (12‑hour TTL) -------------------
    if redis_client:
        try:
            # TTL = 12 hours = 43200 seconds
            redis_client.setex(cache_key, 12 * 60 * 60, json.dumps(weather))
        except Exception as e:
            print(f"⚠️  Redis write error (ignored): {e}")

    # ------------------- 4️⃣ Respond to the client -------------------
    return jsonify({"source": source, "data": weather})

# --------------------------------------------------------------
# 6️⃣ Health‑check endpoint
# --------------------------------------------------------------
@app.route("/health", methods=["GET"])
def health():
    redis_status = "connected"
    if redis_client:
        try:
            redis_client.ping()
        except Exception:
            redis_status = "unavailable"
    else:
        redis_status = "disabled"

    return jsonify({
        "status": "ok",
        "redis": redis_status,
        "rate_limit": {
            "window_seconds": RATE_LIMIT_WINDOW_MS // 1000,
            "max_requests": RATE_LIMIT_MAX
        }
    })

# --------------------------------------------------------------
# 7️⃣ Root route – friendly welcome
# --------------------------------------------------------------
@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "message": "Welcome to the Python Weather API",
        "usage": "GET /weather?city=<city-name-or-code>",
        "health": "/health"
    })

# --------------------------------------------------------------
# 8️⃣ Global error handler (fallback)
# --------------------------------------------------------------
@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({"error": "Too many requests – please slow down"}), 429

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({"error": "Internal server error"}), 500


# --------------------------------------------------------------
# 9️⃣ Run the server
# --------------------------------------------------------------
if __name__ == "__main__":
    # Flask’s built‑in server is fine for development / demo purposes.
    # In production you’d use gunicorn, waitress, uWSGI, etc.
    app.run(host="0.0.0.0", port=5000, debug=True)
