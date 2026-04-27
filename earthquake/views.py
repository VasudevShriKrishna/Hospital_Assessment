import requests
from django.shortcuts import render
from django.http import JsonResponse, FileResponse
from django.conf import settings
import math, os, json
import numpy as np
import joblib

import base64
from io import BytesIO
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from django.views.decorators.csrf import csrf_exempt
from .models import HistoricalEarthquake

WEATHER_API_KEY = "Use Your Own API Key"

#1. HOME PAGE
def index(request):
    """Renders the main map interface."""
    return render(request, "index.html")

# 2. NEAREST HOSPITAL SEARCH 
def nearest_hospital(request):
    """Reads hospitals.geojson and returns closest facilities."""
    try:
        lat = float(request.GET.get("lat"))
        lng = float(request.GET.get("lng"))
        file_path = os.path.join(settings.BASE_DIR, "static/data/hospitals.geojson")
        with open(file_path, encoding="utf-8") as f:
            hospitals_data = json.load(f)["features"]
        
        hospital_list = []
        for h in hospitals_data:
            if h.get("geometry"):
                h_lng, h_lat = h["geometry"]["coordinates"]
                R = 6371
                phi1, phi2 = math.radians(lat), math.radians(h_lat)
                dphi, dlambda = math.radians(h_lat - lat), math.radians(h_lng - lng)
                a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
                dist = 2 * R * math.asin(math.sqrt(a))
                hospital_list.append({
                    "name": h["properties"].get("NAME", "Emergency Facility"), 
                    "lat": h_lat, "lng": h_lng, "distance": round(dist, 2)
                })
        hospital_list.sort(key=lambda x: x["distance"])
        return JsonResponse(hospital_list[:6], safe=False)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

# ================= 3. SEISMIC MODEL & PREDICTION =================
MODEL_PATH = r"./ml_models/earthquake_pipeline_model.pkl"
try:
    seismic_brain = joblib.load(MODEL_PATH)
except:
    seismic_brain = None

def get_risk_level(intensity):
    if intensity < 2: return "MINIMAL"
    elif intensity < 4: return "LOW"
    elif intensity < 5.5: return "MODERATE"
    elif intensity < 7: return "HIGH"
    else: return "CRITICAL"

def get_expected_damage(intensity):
    damage_map = {"MINIMAL": "Negligible", "LOW": "Light", "MODERATE": "Moderate", "HIGH": "Heavy", "CRITICAL": "Major Failure"}
    return damage_map.get(get_risk_level(intensity), "Unknown")

def get_radius_km(magnitude, depth_km):
    depth_factor = max(0.3, 1 - (depth_km / 250))
    return (10 ** (0.4 * magnitude - 1)) * depth_factor

def get_nearest_history(request):
    try:
        lat, lng = float(request.GET.get('lat')), float(request.GET.get('lng'))
        user_mag = float(request.GET.get('mag', 6.0))
        earthquakes = HistoricalEarthquake.objects.filter(latitude__isnull=False, depth__isnull=False)
        
        nearest = None
        min_dist = float('inf')
        for eq in earthquakes:
            d = eq.distance_to(lat, lng)
            if d is not None and d < min_dist:
                min_dist, nearest = d, eq

        if not nearest or not seismic_brain:
            return JsonResponse({"error": "Data or Model unavailable"}, status=404)

        # AI Prediction
        feature_vector = [[user_mag, nearest.latitude, nearest.longitude, 
                          (getattr(nearest,"nst",0) or 0), (getattr(nearest,"gap",0) or 0), (getattr(nearest,"dmin",0) or 0), 
                          (getattr(nearest,"rms",0) or 0), (getattr(nearest,"horizontal_error",0) or 0), 
                          (getattr(nearest,"depth_error",0) or 0), (getattr(nearest,"mag_error",0) or 0), 
                          (getattr(nearest,"mag_nst",0) or 0), nearest.latitude*nearest.longitude, 
                          nearest.latitude**2, nearest.longitude**2]]
        
        predicted_depth = float(np.expm1(seismic_brain.predict(feature_vector)[0]))
        ai_intensity = float(np.clip((user_mag * 1.3) - (predicted_depth / 50.0), 1, 10))
        radius = float(get_radius_km(user_mag, predicted_depth))

        # --- ✨ PERFECT CONFIDENCE ENGINE ✨ ---
        # nst, gap, rms = float(getattr(nearest,"nst",20)), float(getattr(nearest,"gap",90)), float(getattr(nearest,"rms",0.5))
        nst = float(getattr(nearest, "nst", 20) or 20)
        gap = float(getattr(nearest, "gap", 90) or 90)
        rms = float(getattr(nearest, "rms", 0.5) or 0.5)        
        tele_p = min(20, (50-nst)*0.4) + min(10, (gap-90)*0.1) + min(10, (rms-0.5)*10)
        geo_p = min(30, (min_dist-50)*0.1)
        anom_p = min(15, (user_mag-6.5)*5) + min(15, (predicted_depth-30)*0.1)
        confidence = float(max(15, min(99.5, 100 - tele_p - geo_p - anom_p)))

        # 5. EXACT DISTANCE CALCULATION: Distance to ALL hospitals and filter by radius
        affected_hospitals = []
        file_path = os.path.join(settings.BASE_DIR, "static/data/hospitals.geojson")
        
        if os.path.exists(file_path):
            with open(file_path, encoding="utf-8") as f:
                hospitals_data = json.load(f)["features"]
            
            for h in hospitals_data:
                if h.get("geometry"):
                    h_lng, h_lat = h["geometry"]["coordinates"]
                    props = h["properties"]
                    
                    # Haversine distance from simulated EPICENTER to HOSPITAL
                    R = 6371
                    phi1, phi2 = math.radians(lat), math.radians(h_lat)
                    dphi = math.radians(h_lat - lat)
                    dlambda = math.radians(h_lng - lng)
                    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
                    h_dist = 2 * R * math.asin(math.sqrt(a))
                    
                    # Only include if inside the calculated impact radius
                    if h_dist <= radius:
                        affected_hospitals.append({
                            "name": props.get("NAME", "Unknown"),
                            "lat": h_lat,
                            "lng": h_lng,
                            "distance": float(round(h_dist, 2)), # ✅ FIX 3: CAST TO FLOAT
                            "beds": props.get("BEDS", 0) if props.get("BEDS") != -999 else 0,
                            "type": props.get("TYPE", "Unknown"),
                            "status": props.get("STATUS", "Unknown"),
                            "telephone": props.get("TELEPHONE", "N/A")
                        })
            
            # Sort hospitals by closest to epicenter
            affected_hospitals.sort(key=lambda x: x["distance"])

        # ✅ FIX 3: CAST ALL NUMBERS TO FLOAT/STR TO PREVENT FLOAT32 JSON CRASH
        return JsonResponse({
            "place": str(nearest.place),
            "mag": float(user_mag),
            "radius": float(round(radius, 2)),
            "intensity": float(round(ai_intensity, 2)),
            "risk_level": str(get_risk_level(ai_intensity)),
            "expected_damage": str(get_expected_damage(ai_intensity)),
            "dist_from_click": float(round(min_dist, 2)),
            "depth": float(round(predicted_depth, 2)),
            "confidence": float(round(confidence, 2)),
            "assessment": f"Earthquake of magnitude {user_mag} at predicted depth {predicted_depth:.1f}km is expected to cause {get_risk_level(ai_intensity)} damage.",
            "affected_hospitals": affected_hospitals,
            "total_beds_at_risk": sum(h['beds'] for h in affected_hospitals)
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

def get_weather_proxy(request):
    if WEATHER_API_KEY == "Your API key ":
        return JsonResponse({"weather": [{"main": "Clear"}], "warning": "API key missing"})

    url = f"https://api.openweathermap.org/data/2.5/weather?lat={request.GET.get('lat')}&lon={request.GET.get('lng')}&appid={WEATHER_API_KEY}&units=metric"
    try:
        response = requests.get(url, timeout=5)
        return JsonResponse(response.json())
    except Exception as e:
        return JsonResponse({"weather": [{"main": "Clear"}], "warning": str(e)})

# ================= 4. PDF REPORT =================
@csrf_exempt
def report(request):
    data = request.POST if request.method == "POST" else request.GET
    confidence_val = data.get("confidence", "0%")
    
    file_path = os.path.join(settings.BASE_DIR, "EQ_Safety_Report.pdf")
    doc = SimpleDocTemplate(file_path, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("EARTHQUAKE HAZARD ASSESSMENT", styles["Title"]))
    
    table_data = [
        ["PARAMETER", "DETAILS"],
        ["Target", data.get("place")], ["Magnitude", f"{data.get('mag')} Mw"],
        ["AI Predicted Depth", f"{data.get('depth')} km"],
        ["AI Intensity", data.get("intensity")], ["Designated Hospit    al", data.get("hname")],
        ["Travel Distance", f"{data.get('dist')} km"], ["Weather", data.get("weather")],
        ["Model Confidence", confidence_val]
    ]
    story.append(Table(table_data, colWidths=[180, 270], style=TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2C3E50")), ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('GRID', (0,0), (-1,-1), 1, colors.grey)
    ])))

    img_data_raw = data.get("map_image")
    if img_data_raw and ";base64," in img_data_raw:
        try:
            img_bytes = base64.b64decode(img_data_raw.split(';base64,')[1])
            story.append(Spacer(1, 20))
            story.append(RLImage(BytesIO(img_bytes), width=480, height=300))
        except:
            story.append(Paragraph("<i>(Map Image Unavailable)</i>", styles["Normal"]))

    doc.build(story)
    return FileResponse(open(file_path, "rb"), as_attachment=True, filename="Safety_Report.pdf")

