import os
import json
import csv
import math
import requests
from django.conf import settings
from django.core.cache import cache
from .utils import haversine

PROJECT_ROOT = settings.BASE_DIR

# LOAD DATA
def load_hospitals():
    cache_key = "hospitals_data"
    hospitals = cache.get(cache_key)
    if hospitals:
        return hospitals

    path = os.path.join(PROJECT_ROOT, "hospitals.json")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    hospitals = []
    for feature in data["features"]:
        p = feature["properties"]
        hospitals.append({
            "name": p["NAME"],
            "city": p["CITY"],
            "state": p["STATE"],
            "beds": p["BEDS"],
            "facilities": p.get("FACILITIES", []),
            "lat": p["LATITUDE"],
            "lon": p["LONGITUDE"],
        })

    cache.set(cache_key, hospitals, 3600)
    return hospitals


def load_earthquakes():
    cache_key = "earthquake_data"
    eqs = cache.get(cache_key)
    if eqs:
        return eqs

    path = os.path.join(PROJECT_ROOT, "earthquakes.csv")
    eqs = []

    with open(path, newline='', encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            eqs.append({
                "lat": float(row["latitude"]),
                "lon": float(row["longitude"]),
                "mag": float(row["mag"]),
                "place": row.get("place", "Unknown")
            })

    cache.set(cache_key, eqs, 3600)
    return eqs


# HOSPITAL LOAD PREDICTION MODEL
def predict_hospital_load(beds, hazard_score):
    """
    Simple demand surge model:
    Expected load increase proportional to hazard severity.
    """

    surge_factor = hazard_score / 100
    predicted_patients = beds * surge_factor * 0.6

    load_percent = min(100, round((predicted_patients / beds) * 100))

    return load_percent

# AI RISK CLASSIFICATION
def ai_risk_classification(eq_mag, distance_km, load_percent):

    risk_score = 0

    risk_score += eq_mag * 10
    risk_score += max(0, 100 - distance_km)
    risk_score += load_percent

    if risk_score > 180:
        return "CRITICAL"
    elif risk_score > 120:
        return "HIGH"
    elif risk_score > 70:
        return "MODERATE"
    else:
        return "LOW"
