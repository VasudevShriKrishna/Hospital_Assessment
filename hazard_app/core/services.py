import os
import json
import csv
import math
import requests
from django.conf import settings
from django.core.cache import cache
from .utils import haversine

PROJECT_ROOT = settings.BASE_DIR


# -------------------------------------------------
# LOAD DATA
# -------------------------------------------------

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


# -------------------------------------------------
# HOSPITAL LOAD PREDICTION MODEL
# -------------------------------------------------

def predict_hospital_load(beds, hazard_score):
    """
    Simple demand surge model:
    Expected load increase proportional to hazard severity.
    """

    surge_factor = hazard_score / 100
    predicted_patients = beds * surge_factor * 0.6

    load_percent = min(100, round((predicted_patients / beds) * 100))

    return load_percent


# -------------------------------------------------
# AI RISK CLASSIFICATION
# -------------------------------------------------

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


# # -------------------------------------------------
# # IMPACT ZONE RADIUS
# # -------------------------------------------------

# def impact_radius(magnitude):
#     """
#     Empirical formula for visible impact radius.
#     """
#     return magnitude * 20  # km


# # -------------------------------------------------
# # COLOR SCALE BY MAGNITUDE
# # -------------------------------------------------

# def magnitude_color(mag):
#     if mag >= 6:
#         return "darkred"
#     elif mag >= 5:
#         return "red"
#     elif mag >= 4:
#         return "orange"
#     else:
#         return "yellow"




# import os
# import json
# import csv
# import requests
# from django.conf import settings
# from django.core.cache import cache
# from .utils import haversine

# PROJECT_ROOT = settings.BASE_DIR


# # -------------------------
# # LOAD DATA (CACHED)
# # -------------------------

# def load_hospitals():
#     cache_key = "hospitals_data"
#     hospitals = cache.get(cache_key)

#     if hospitals:
#         return hospitals

#     path = os.path.join(PROJECT_ROOT, "hospitals.json")

#     with open(path, "r", encoding="utf-8") as f:
#         data = json.load(f)

#     hospitals = []

#     for feature in data["features"]:
#         props = feature["properties"]
#         hospitals.append({
#             "name": props["NAME"],
#             "address": props["ADDRESS"],
#             "city": props["CITY"],
#             "state": props["STATE"],
#             "beds": props["BEDS"],
#             "facilities": props.get("FACILITIES", []),
#             "lat": props["LATITUDE"],
#             "lon": props["LONGITUDE"],
#         })

#     cache.set(cache_key, hospitals, 3600)
#     return hospitals


# def load_earthquakes():
#     cache_key = "earthquakes_data"
#     eqs = cache.get(cache_key)

#     if eqs:
#         return eqs

#     path = os.path.join(PROJECT_ROOT, "earthquakes.csv")
#     eqs = []

#     with open(path, newline='', encoding="utf-8") as csvfile:
#         reader = csv.DictReader(csvfile)
#         for row in reader:
#             eqs.append({
#                 "lat": float(row["latitude"]),
#                 "lon": float(row["longitude"]),
#                 "mag": float(row["mag"]),
#             })

#     cache.set(cache_key, eqs, 3600)
#     return eqs


# # -------------------------
# # NEAREST HOSPITAL
# # -------------------------

# def nearest_hospital(lat, lon):
#     hospitals = load_hospitals()

#     nearest = None
#     min_dist = float("inf")

#     for h in hospitals:
#         dist = haversine(lat, lon, h["lat"], h["lon"])
#         if dist < min_dist:
#             min_dist = dist
#             nearest = h

#     nearest["distance_km"] = round(min_dist, 2)
#     return nearest


# # -------------------------
# # EARTHQUAKE SCORE
# # -------------------------

# def earthquake_score(lat, lon):
#     eqs = load_earthquakes()
#     score = 0

#     for eq in eqs:
#         dist = haversine(lat, lon, eq["lat"], eq["lon"])
#         if dist <= 150:
#             score += eq["mag"] * (150 - dist) / 150

#     return min(100, round(score))


# # -------------------------
# # WEATHER SCORE
# # -------------------------

# def weather_score(lat, lon):
#     url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
#     response = requests.get(url)

#     if response.status_code != 200:
#         return 0, {}

#     data = response.json()["current_weather"]
#     temp = data["temperature"]
#     wind = data["windspeed"]

#     score = 0

#     if temp >= 40 or temp <= -5:
#         score += 40

#     if wind >= 60:
#         score += 40

#     return min(100, score), data


# # -------------------------
# # TOTAL HAZARD INDEX
# # -------------------------

# def hazard_index(lat, lon, hospital_distance):
#     eq = earthquake_score(lat, lon)
#     weather, weather_data = weather_score(lat, lon)

#     proximity_score = max(0, 100 - hospital_distance * 2)

#     total = (
#         0.4 * eq +
#         0.35 * weather +
#         0.25 * proximity_score
#     )

#     return round(total), weather_data

# def affected_hospitals(eq_lat, eq_lon, radius_km=100):
#     hospitals = load_hospitals()
#     affected = []

#     for h in hospitals:
#         dist = haversine(eq_lat, eq_lon, h["lat"], h["lon"])
#         if dist <= radius_km:
#             affected.append(h)

#     return affected


# def nearest_safe_hospitals(eq_lat, eq_lon, limit=5):
#     hospitals = load_hospitals()
#     distances = []

#     for h in hospitals:
#         dist = haversine(eq_lat, eq_lon, h["lat"], h["lon"])
#         distances.append((dist, h))

#     distances.sort(key=lambda x: x[0])

#     safe = [h for d, h in distances if d > 100][:limit]
#     return safe


# import os
# import json
# import csv
# import requests
# from django.conf import settings
# from .utils import haversine


# PROJECT_ROOT = settings.BASE_DIR


# def load_hospitals():
#     path = os.path.join(PROJECT_ROOT, "hospitals.json")

#     with open(path, "r", encoding="utf-8") as f:
#         data = json.load(f)

#     hospitals = []

#     for feature in data["features"]:
#         props = feature["properties"]
#         hospitals.append({
#             "name": props["NAME"],
#             "address": props["ADDRESS"],
#             "city": props["CITY"],
#             "state": props["STATE"],
#             "beds": props["BEDS"],
#             "lat": props["LATITUDE"],
#             "lon": props["LONGITUDE"],
#         })

#     return hospitals


# def load_earthquakes():
#     path = os.path.join(PROJECT_ROOT, "earthquakes.csv")
#     earthquakes = []

#     with open(path, newline='', encoding="utf-8") as csvfile:
#         reader = csv.DictReader(csvfile)
#         for row in reader:
#             earthquakes.append({
#                 "lat": float(row["latitude"]),
#                 "lon": float(row["longitude"]),
#                 "mag": float(row["mag"]),
#             })

#     return earthquakes


# def nearest_hospital(lat, lon):
#     hospitals = load_hospitals()

#     nearest = None
#     min_dist = float("inf")

#     for h in hospitals:
#         dist = haversine(lat, lon, h["lat"], h["lon"])
#         if dist < min_dist:
#             min_dist = dist
#             nearest = h

#     nearest["distance_km"] = min_dist
#     return nearest


# def earthquake_risk(lat, lon):
#     earthquakes = load_earthquakes()

#     for eq in earthquakes:
#         if haversine(lat, lon, eq["lat"], eq["lon"]) <= 100 and eq["mag"] >= 4:
#             return "HIGH"

#     return "LOW"


# def weather_data(lat, lon):
#     url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
#     response = requests.get(url)

#     if response.status_code == 200:
#         data = response.json()
#         weather = data["current_weather"]
#         return {
#             "temperature": weather["temperature"],
#             "windspeed": weather["windspeed"]
#         }

#     return {
#         "temperature": "N/A",
#         "windspeed": "N/A"
#     }
