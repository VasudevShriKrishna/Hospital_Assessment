import json
import csv
import os
from django.conf import settings


def load_hospitals():
    file_path = os.path.join(settings.BASE_DIR, "hospitals.json")

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data["features"]


def load_earthquakes():
    file_path = os.path.join(settings.BASE_DIR, "earthquakes.csv")

    earthquakes = []

    with open(file_path, newline='', encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            earthquakes.append({
                "id": row["id"],
                "magnitude": float(row["magnitude"]),
                "latitude": float(row["latitude"]),
                "longitude": float(row["longitude"]),
                "depth": float(row["depth_km"]),
                "time": row["time"]
            })

    return earthquakes
