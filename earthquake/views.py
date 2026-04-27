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
MODEL_PATH = r"G:\earthquake_today\earthquake_project\ml_models\earthquake_pipeline_model.pkl"
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
    # Graceful fallback if the API key is not yet set
    if WEATHER_API_KEY == "53719aca4723375a9e4d9dae1712951c":
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




# import requests
# from django.shortcuts import render
# from django.http import JsonResponse, FileResponse
# from django.conf import settings
# import math, os, json
# import numpy as np
# import joblib

# # PDF Generation Imports
# import base64
# from io import BytesIO
# from datetime import datetime
# from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
# from reportlab.lib.styles import getSampleStyleSheet
# from reportlab.lib.pagesizes import A4
# from reportlab.lib import colors
# from django.views.decorators.csrf import csrf_exempt

# # Import your model
# from .models import HistoricalEarthquake

# # 🚨 YOU MUST PASTE YOUR OPENWEATHERMAP API KEY HERE 🚨
# # Get it for free at: https://openweathermap.org/
# WEATHER_API_KEY = "53719aca4723375a9e4d9dae1712951c"

# # ================= 1. HOME PAGE =================
# def index(request):
#     """Renders the main map interface."""
#     return render(request, "index.html")

# # ================= 2. NEAREST HOSPITAL SEARCH =================
# def nearest_hospital(request):
#     """Reads hospitals.geojson and returns closest facilities."""
#     try:
#         lat = float(request.GET.get("lat"))
#         lng = float(request.GET.get("lng"))
#         file_path = os.path.join(settings.BASE_DIR, "static/data/hospitals.geojson")
#         with open(file_path, encoding="utf-8") as f:
#             hospitals_data = json.load(f)["features"]
        
#         hospital_list = []
#         for h in hospitals_data:
#             if h.get("geometry"):
#                 h_lng, h_lat = h["geometry"]["coordinates"]
#                 R = 6371
#                 phi1, phi2 = math.radians(lat), math.radians(h_lat)
#                 dphi, dlambda = math.radians(h_lat - lat), math.radians(h_lng - lng)
#                 a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
#                 dist = 2 * R * math.asin(math.sqrt(a))
#                 hospital_list.append({
#                     "name": h["properties"].get("NAME", "Emergency Facility"), 
#                     "lat": h_lat, "lng": h_lng, "distance": round(dist, 2)
#                 })
#         hospital_list.sort(key=lambda x: x["distance"])
#         return JsonResponse(hospital_list[:6], safe=False)
#     except Exception as e:
#         return JsonResponse({"error": str(e)}, status=400)

# # ================= 3. SEISMIC MODEL & PREDICTION =================
# MODEL_PATH = r"G:\earthquake_today\earthquake_project\ml_models\earthquake_pipeline_model.pkl"
# try:
#     seismic_brain = joblib.load(MODEL_PATH)
# except:
#     seismic_brain = None

# def get_risk_level(intensity):
#     if intensity < 2: return "MINIMAL"
#     elif intensity < 4: return "LOW"
#     elif intensity < 5.5: return "MODERATE"
#     elif intensity < 7: return "HIGH"
#     else: return "CRITICAL"

# def get_expected_damage(intensity):
#     damage_map = {"MINIMAL": "Negligible", "LOW": "Light", "MODERATE": "Moderate", "HIGH": "Heavy", "CRITICAL": "Major Failure"}
#     return damage_map.get(get_risk_level(intensity), "Unknown")

# def get_radius_km(magnitude, depth_km):
#     depth_factor = max(0.3, 1 - (depth_km / 250))
#     return (10 ** (0.4 * magnitude - 1)) * depth_factor

# def get_nearest_history(request):
#     try:
#         lat, lng = float(request.GET.get('lat')), float(request.GET.get('lng'))
#         user_mag = float(request.GET.get('mag', 6.0))
#         earthquakes = HistoricalEarthquake.objects.filter(latitude__isnull=False, depth__isnull=False)
        
#         nearest = None
#         min_dist = float('inf')
#         for eq in earthquakes:
#             d = eq.distance_to(lat, lng)
#             if d is not None and d < min_dist:
#                 min_dist, nearest = d, eq

#         if not nearest or not seismic_brain:
#             return JsonResponse({"error": "Data or Model unavailable"}, status=404)

#         # AI Prediction
#         feature_vector = [[user_mag, nearest.latitude, nearest.longitude, 
#                           getattr(nearest,"nst",0), getattr(nearest,"gap",0), getattr(nearest,"dmin",0), 
#                           getattr(nearest,"rms",0), getattr(nearest,"horizontal_error",0), 
#                           getattr(nearest,"depth_error",0), getattr(nearest,"mag_error",0), 
#                           getattr(nearest,"mag_nst",0), nearest.latitude*nearest.longitude, 
#                           nearest.latitude**2, nearest.longitude**2]]
        
#         predicted_depth = float(np.expm1(seismic_brain.predict(feature_vector)[0]))
#         ai_intensity = float(np.clip((user_mag * 1.3) - (predicted_depth / 50.0), 1, 10))
#         radius = float(get_radius_km(user_mag, predicted_depth))

#         # --- ✨ PERFECT CONFIDENCE ENGINE ✨ ---
#         nst, gap, rms = float(getattr(nearest,"nst",20)), float(getattr(nearest,"gap",90)), float(getattr(nearest,"rms",0.5))
#         tele_p = min(20, (50-nst)*0.4) + min(10, (gap-90)*0.1) + min(10, (rms-0.5)*10)
#         geo_p = min(30, (min_dist-50)*0.1)
#         anom_p = min(15, (user_mag-6.5)*5) + min(15, (predicted_depth-30)*0.1)
#         confidence = float(max(15, min(99.5, 100 - tele_p - geo_p - anom_p)))

#         return JsonResponse({
#             "place": nearest.place, "mag": user_mag, "radius": round(radius, 2),
#             "intensity": round(ai_intensity, 2), "risk_level": get_risk_level(ai_intensity),
#             "depth": round(predicted_depth, 2), "confidence": round(confidence, 2),
#             "expected_damage": get_expected_damage(ai_intensity)
#         })
#     except Exception as e:
#         return JsonResponse({"error": str(e)}, status=400)

# def get_weather_proxy(request):
#     # Graceful fallback if the API key is not yet set
#     if WEATHER_API_KEY == "53719aca4723375a9e4d9dae1712951c":
#         return JsonResponse({"weather": [{"main": "Clear"}], "warning": "API key missing"})

#     url = f"https://api.openweathermap.org/data/2.5/weather?lat={request.GET.get('lat')}&lon={request.GET.get('lng')}&appid={WEATHER_API_KEY}&units=metric"
#     try:
#         response = requests.get(url, timeout=5)
#         return JsonResponse(response.json())
#     except Exception as e:
#         return JsonResponse({"weather": [{"main": "Clear"}], "warning": str(e)})

# # ================= 4. PDF REPORT =================
# @csrf_exempt
# def report(request):
#     data = request.POST if request.method == "POST" else request.GET
#     confidence_val = data.get("confidence", "0%")
    
#     file_path = os.path.join(settings.BASE_DIR, "EQ_Safety_Report.pdf")
#     doc = SimpleDocTemplate(file_path, pagesize=A4)
#     styles = getSampleStyleSheet()
#     story = []

#     story.append(Paragraph("EARTHQUAKE HAZARD ASSESSMENT", styles["Title"]))
    
#     table_data = [
#         ["PARAMETER", "DETAILS"],
#         ["Target", data.get("place")], ["Magnitude", f"{data.get('mag')} Mw"],
#         ["AI Predicted Depth", f"{data.get('depth')} km"],
#         ["AI Intensity", data.get("intensity")], ["Designated Hospital", data.get("hname")],
#         ["Travel Distance", f"{data.get('dist')} km"], ["Weather", data.get("weather")],
#         ["Model Confidence", confidence_val]
#     ]
#     story.append(Table(table_data, colWidths=[180, 270], style=TableStyle([
#         ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2C3E50")), ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
#         ('GRID', (0,0), (-1,-1), 1, colors.grey)
#     ])))

#     img_data_raw = data.get("map_image")
#     if img_data_raw and ";base64," in img_data_raw:
#         try:
#             img_bytes = base64.b64decode(img_data_raw.split(';base64,')[1])
#             story.append(Spacer(1, 20))
#             story.append(RLImage(BytesIO(img_bytes), width=480, height=300))
#         except:
#             story.append(Paragraph("<i>(Map Image Unavailable)</i>", styles["Normal"]))

#     doc.build(story)
#     return FileResponse(open(file_path, "rb"), as_attachment=True, filename="Safety_Report.pdf")    




# import requests
# from django.shortcuts import render
# from django.http import JsonResponse, FileResponse
# from django.conf import settings
# import math, os, json
# import numpy as np
# import joblib

# # PDF Generation Imports
# import base64
# from io import BytesIO
# from datetime import datetime
# from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
# from reportlab.lib.styles import getSampleStyleSheet
# from reportlab.lib.pagesizes import A4
# from reportlab.lib import colors
# from django.views.decorators.csrf import csrf_exempt

# # Import your model
# from .models import HistoricalEarthquake

# # ================= 1. HOME PAGE =================
# def index(request):
#     """Renders the main map interface."""
#     return render(request, "index.html")

# # ================= 2. NEAREST HOSPITAL SEARCH =================
# def nearest_hospital(request):
#     """Reads hospitals.geojson and returns closest facilities via Haversine."""
#     try:
#         lat = float(request.GET.get("lat"))
#         lng = float(request.GET.get("lng"))
        
#         file_path = os.path.join(settings.BASE_DIR, "static/data/hospitals.geojson")
        
#         with open(file_path, encoding="utf-8") as f:
#             hospitals_data = json.load(f)["features"]
        
#         hospital_list = []
#         for h in hospitals_data:
#             if h.get("geometry"):
#                 h_lng, h_lat = h["geometry"]["coordinates"]
#                 name = h["properties"].get("NAME") or "Emergency Facility"
                
#                 # Haversine distance formula
#                 R = 6371
#                 phi1, phi2 = math.radians(lat), math.radians(h_lat)
#                 dphi = math.radians(h_lat - lat)
#                 dlambda = math.radians(h_lng - lng)
#                 a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
#                 dist = 2 * R * math.asin(math.sqrt(a))
                
#                 hospital_list.append({
#                     "name": name, "lat": h_lat, "lng": h_lng, "distance": round(dist, 2)
#                 })
        
#         hospital_list.sort(key=lambda x: x["distance"])
#         return JsonResponse(hospital_list[:6], safe=False)
#     except Exception as e:
#         return JsonResponse({"error": str(e)}, status=400)

# # ================= 3. SEISMIC MODEL & PREDICTION HELPERS =================
# MODEL_PATH = r"G:\earthquake_today\earthquake_project\ml_models\earthquake_pipeline_model.pkl"
# try:
#     seismic_brain = joblib.load(MODEL_PATH)
# except Exception as e:
#     print(f"⚠️ Warning: Model not loaded. Error: {e}")
#     seismic_brain = None

# def get_risk_level(intensity):
#     """Convert intensity score to risk level (high-level prediction)."""
#     if intensity < 2: return "MINIMAL"
#     elif intensity < 4: return "LOW"
#     elif intensity < 5.5: return "MODERATE"
#     elif intensity < 7: return "HIGH"
#     else: return "CRITICAL"

# def get_expected_damage(intensity):
#     """Provide expected structural damage assessment."""
#     damage_map = {
#         "MINIMAL": "Negligible - Not felt; No structural impact",
#         "LOW": "Light - Felt indoors; Minor non-structural damage",
#         "MODERATE": "Moderate - Some plaster cracking; Possible structural concerns",
#         "HIGH": "Heavy - Considerable damage; Structural damage likely",
#         "CRITICAL": "Very Heavy - Extensive damage; Major structural failure expected"
#     }
#     return damage_map.get(get_risk_level(intensity), "Unknown")

# def get_radius_km(magnitude, depth_km):
#     """
#     Calculate affected radius with depth consideration.
#     Deeper quakes affect smaller area; shallow quakes affect larger area.
#     """
#     depth_factor = max(0.3, 1 - (depth_km / 250))  # Deeper = smaller radius
#     base_radius = 10 ** (0.4 * magnitude - 1)  # Adjusted slightly to match UI visual radius
#     return base_radius * depth_factor

# def get_nearest_history(request):
#     """
#     Predict earthquake depth using ML model AND calculates affected hospitals
#     distance from the simulated epicenter within the danger radius.
#     """
#     try:
#         lat = float(request.GET.get('lat'))
#         lng = float(request.GET.get('lng'))
#         user_mag = float(request.GET.get('mag', 6.0))

#         # 1. Fetch all earthquakes and compute distances
#         earthquakes = HistoricalEarthquake.objects.filter(
#             latitude__isnull=False,
#             longitude__isnull=False,
#             depth__isnull=False
#         )

#         if not earthquakes.exists():
#             return JsonResponse({"error": "No historical earthquake data available."}, status=404)

#         nearest = None
#         min_distance = float('inf')
#         for eq in earthquakes:
#             dist = eq.distance_to(lat, lng)
#             if dist is not None and dist < min_distance:
#                 min_distance = dist
#                 nearest = eq

#         if nearest is None:
#             return JsonResponse({"error": "No historical earthquake data available."}, status=404)

#         if seismic_brain is None:
#             raise Exception("Model not loaded. Please train the model first.")
        
#         # 2. AI Inference: Predict DEPTH based on the nearest historical profile
#         lat_hist = nearest.latitude
#         lon_hist = nearest.longitude

#         feature_vector = [[
#             user_mag, lat_hist, lon_hist,
#             getattr(nearest, "nst", 0) or 0,
#             getattr(nearest, "gap", 0) or 0,
#             getattr(nearest, "dmin", 0) or 0,
#             getattr(nearest, "rms", 0) or 0,
#             getattr(nearest, "horizontal_error", 0) or 0,
#             getattr(nearest, "depth_error", 0) or 0,
#             getattr(nearest, "mag_error", 0) or 0,
#             getattr(nearest, "mag_nst", 0) or 0,
#             lat_hist * lon_hist,
#             lat_hist ** 2,
#             lon_hist ** 2
#         ]]

#         # MODEL PREDICTS LOG_DEPTH -> Convert back to real depth via expm1
#         log_depth_pred = seismic_brain.predict(feature_vector)[0]
#         predicted_depth = np.expm1(log_depth_pred)

#         # Calculate intensity based on magnitude and PREDICTED depth
#         depth_penalty = predicted_depth / 50.0
#         ai_intensity = float(np.clip((user_mag * 1.3) - depth_penalty, 1, 10))
        
#         # 3. Calculate affected radius using PREDICTED DEPTH
#         radius = get_radius_km(user_mag, predicted_depth)
        
#         # 4. Determine risk level
#         risk_level = get_risk_level(ai_intensity)
#         damage_assessment = get_expected_damage(ai_intensity)
        
#         # --- ✨ DATA SCIENCE CONFIDENCE ENGINE ✨ ---
#         # Start at 100% and apply strict data science penalties.

#         # 1. Telemetry Quality Penalty (Max 40 points lost)
#         # Assumes 'nearest' is the closest HistoricalEarthquake object matched in your view
#         nst = float(getattr(nearest, "nst", 20) or 20)
#         gap = float(getattr(nearest, "gap", 90) or 90)
#         rms = float(getattr(nearest, "rms", 0.5) or 0.5)

#         nst_penalty = min(20.0, max(0.0, (50.0 - nst) * 0.4))    # Penalty if under 50 stations
#         gap_penalty = min(10.0, max(0.0, (gap - 90.0) * 0.1))    # Penalty if gap is over 90 degrees
#         rms_penalty = min(10.0, max(0.0, (rms - 0.5) * 10.0))    # Penalty if high RMS error
#         telemetry_penalty = nst_penalty + gap_penalty + rms_penalty

#         # 2. Geographic Familiarity Penalty (Max 30 points lost)
#         # 'min_distance' is the distance to the nearest known historical quake
#         geo_penalty = min(30.0, max(0.0, (min_distance - 50.0) * 0.1))

#         # 3. Statistical Anomaly Penalty (Max 30 points lost)
#         # High magnitudes and extreme depths are rare, meaning less training data exists.
#         mag_penalty = min(15.0, max(0.0, (user_mag - 6.5) * 5.0))
#         depth_penalty_conf = min(15.0, max(0.0, (predicted_depth - 30.0) * 0.1))
#         anomaly_penalty = mag_penalty + depth_penalty_conf

#         # Final Perfect Confidence Score
#         raw_confidence = 100.0 - telemetry_penalty - geo_penalty - anomaly_penalty
#         confidence = float(max(15.0, min(99.5, raw_confidence))) # Cap safely between 15% and 99.5%
#         # ------------------------------------------

#         # 5. EXACT DISTANCE CALCULATION: Distance to ALL hospitals and filter by radius
#         affected_hospitals = []
#         file_path = os.path.join(settings.BASE_DIR, "static/data/hospitals.geojson")
        
#         if os.path.exists(file_path):
#             with open(file_path, encoding="utf-8") as f:
#                 hospitals_data = json.load(f)["features"]
            
#             for h in hospitals_data:
#                 if h.get("geometry"):
#                     h_lng, h_lat = h["geometry"]["coordinates"]
#                     props = h["properties"]
                    
#                     # Haversine distance from simulated EPICENTER to HOSPITAL
#                     R = 6371
#                     phi1, phi2 = math.radians(lat), math.radians(h_lat)
#                     dphi = math.radians(h_lat - lat)
#                     dlambda = math.radians(h_lng - lng)
#                     a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
#                     h_dist = 2 * R * math.asin(math.sqrt(a))
                    
#                     # Only include if inside the calculated impact radius
#                     if h_dist <= radius:
#                         affected_hospitals.append({
#                             "name": props.get("NAME", "Unknown"),
#                             "lat": h_lat,
#                             "lng": h_lng,
#                             "distance": round(h_dist, 2), # ACCURATE DISTANCE
#                             "beds": props.get("BEDS", 0) if props.get("BEDS") != -999 else 0,
#                             "type": props.get("TYPE", "Unknown"),
#                             "status": props.get("STATUS", "Unknown"),
#                             "telephone": props.get("TELEPHONE", "N/A")
#                         })
            
#             # Sort hospitals by closest to epicenter
#             affected_hospitals.sort(key=lambda x: x["distance"])

#         return JsonResponse({
#             "place": nearest.place,
#             "mag": user_mag,
#             "radius": round(radius, 2),
#             "intensity": ai_intensity,
#             "risk_level": risk_level,
#             "expected_damage": damage_assessment,
#             "dist_from_click": round(min_distance, 2),
#             "depth": float(predicted_depth), # RETURN AI PREDICTED DEPTH
#             "confidence": confidence,
#             "assessment": f"Earthquake of magnitude {user_mag} at predicted depth {predicted_depth:.1f}km is expected to cause {risk_level} damage.",
#             "affected_hospitals": affected_hospitals,
#             "total_beds_at_risk": sum(h['beds'] for h in affected_hospitals)
#         })
#     except Exception as e:
#         return JsonResponse({"error": str(e)}, status=400)

# def get_weather_proxy(request):
#     lat = request.GET.get('lat')
#     lng = request.GET.get('lng')
#     api_key = '53719aca4723375a9e4d9dae1712951c'
#     url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lng}&appid={api_key}&units=metric"
#     try:
#         response = requests.get(url, timeout=5)
#         return JsonResponse(response.json())
#     except Exception as e:
#         return JsonResponse({'error': str(e)}, status=500)

# # ================= 4. PDF REPORT GENERATOR =================
# @csrf_exempt
# def report(request):
#     """
#     Generates a Seismic Safety PDF report.
#     The Table is placed ABOVE the Map Image.
#     """
#     # 1. Capture Data from POST or GET
#     data = request.POST if request.method == "POST" else request.GET
    
#     place = data.get("place", "Simulated Area")
#     mag = data.get("mag", "0.0")
#     data_dist = float(data.get("dist_from_click", "0")) 
#     h_name = data.get("hname", "Emergency Facility")
#     travel_dist = data.get("dist", "0.0")
#     weather = data.get("weather", "Clear")
#     h_lat = data.get("hlat", "0")
#     h_lng = data.get("hlng", "0")
#     ai_intensity = data.get("intensity", "0.0")
#     depth = data.get("depth", "0.0")
#     confidence_val = data.get("confidence", "0%") # ✅ CAPTURE CONFIDENCE FROM JS

#     # 2. Generate Google Maps Navigation Link
#     google_maps_url = f"https://www.google.com/maps/dir/?api=1&destination={h_lat},{h_lng}&travelmode=driving"
#     link_html = f'<a href="{google_maps_url}" color="blue"><u>Open Live GPS Navigation</u></a>'
    
#     # 3. PDF Document Setup
#     file_path = os.path.join(settings.BASE_DIR, "EQ_Safety_Report.pdf")
#     doc = SimpleDocTemplate(file_path, pagesize=A4)
#     styles = getSampleStyleSheet()
#     story = []

#     # --- PDF CONTENT: HEADER ---
#     story.append(Paragraph("EARTHQUAKE HAZARD ASSESSMENT REPORT", styles["Title"]))
#     story.append(Spacer(1, 10))
#     current_date = datetime.now().strftime("%d/%m/%Y")
#     story.append(Paragraph(f"Generated on: {current_date}", styles["Normal"]))
#     story.append(Spacer(1, 20))

#     # --- 4. DATA TABLE (NOW AT THE TOP) ---
    
#     # ✅ SAFE EXTRACTION & FORMATTING LOGIC
#     if not confidence_val:
#         # Fallback only if JS fails to send it
#         confidence_val = f"{max(0, 100 - (data_dist * 2))}%"
    
#     # Clean the string safely (removes % sign so we can do math)
#     try:
#         clean_conf = float(str(confidence_val).replace('%', '').strip())
#     except ValueError:
#         clean_conf = 0.0

#     accuracy_rating = f"{confidence_val} (High)" if clean_conf > 80 else f"{confidence_val} (Moderate/Low)"
#     table_data = [
#         ["ASSESSMENT PARAMETER", "VALUE / DETAILS"],
#         ["Target Region", place],
#         ["Simulated Magnitude", f"{mag} Mw"],
#         ["AI Predicted Depth", f"{depth} km"],
#         ["AI Intensity Rating", f"{ai_intensity}"],
#         ["Structural Risk", "HIGH" if float(ai_intensity) > 5.5 else "LOW/MODERATE"],
#         ["Designated Hospital", h_name],
#         ["Route Distance", f"{travel_dist} km"],
#         ["Current Weather", weather],
#         ["Model Confidence", accuracy_rating],
#         ["Navigation Link", Paragraph(link_html, styles["Normal"])] 
#     ]

#     report_table = Table(table_data, colWidths=[180, 270])
#     report_table.setStyle(TableStyle([
#         ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
#         ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
#         ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
#         ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
#         ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
#         ('GRID', (0, 0), (-1, -1), 1, colors.grey),
#         ('TEXTCOLOR', (1, 5), (1, 5), colors.red if float(ai_intensity) > 5.5 else colors.green),
#     ]))
    
#     story.append(report_table)
#     story.append(Spacer(1, 25)) # Space between Table and Image

#     # --- 5. MAP IMAGE (NOW AT THE BOTTOM) ---
#     map_image_data = data.get("map_image") 
#     if map_image_data and ";base64," in map_image_data:
#         try:
#             format, imgstr = map_image_data.split(';base64,') 
#             img_data = base64.b64decode(imgstr)
#             map_img = RLImage(BytesIO(img_data), width=480, height=300)
            
#             story.append(Paragraph("<b>Spatial Analysis Snapshot (Routes & Heatmap):</b>", styles["Heading3"]))
#             story.append(Spacer(1, 8))
#             story.append(map_img) 
#         except Exception as e:
#             story.append(Paragraph(f"<i>(Visual context snapshot unavailable: {e})</i>", styles["Normal"]))

#     # Final Step: Build the PDF
#     doc.build(story)
    
#     return FileResponse(
#         open(file_path, "rb"), 
#         as_attachment=True, 
#         filename=f"Seismic_Safety_Report_{place[:15]}.pdf"
#     )







# import requests
# from django.shortcuts import render
# from django.http import JsonResponse, FileResponse
# from django.conf import settings
# import math, os, json
# import numpy as np
# import joblib

# # PDF Generation Imports
# import base64
# from io import BytesIO
# from datetime import datetime
# from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
# from reportlab.lib.styles import getSampleStyleSheet
# from reportlab.lib.pagesizes import A4
# from reportlab.lib import colors
# from django.views.decorators.csrf import csrf_exempt

# # Import your model
# from .models import HistoricalEarthquake

# # ================= 1. HOME PAGE =================
# def index(request):
#     """Renders the main map interface."""
#     return render(request, "index.html")

# # ================= 2. NEAREST HOSPITAL SEARCH =================
# def nearest_hospital(request):
#     """Reads hospitals.geojson and returns closest facilities via Haversine."""
#     try:
#         lat = float(request.GET.get("lat"))
#         lng = float(request.GET.get("lng"))
        
#         file_path = os.path.join(settings.BASE_DIR, "static/data/hospitals.geojson")
        
#         with open(file_path, encoding="utf-8") as f:
#             hospitals_data = json.load(f)["features"]
        
#         hospital_list = []
#         for h in hospitals_data:
#             if h.get("geometry"):
#                 h_lng, h_lat = h["geometry"]["coordinates"]
#                 name = h["properties"].get("NAME") or "Emergency Facility"
                
#                 # Haversine distance formula
#                 R = 6371
#                 phi1, phi2 = math.radians(lat), math.radians(h_lat)
#                 dphi = math.radians(h_lat - lat)
#                 dlambda = math.radians(h_lng - lng)
#                 a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
#                 dist = 2 * R * math.asin(math.sqrt(a))
                
#                 hospital_list.append({
#                     "name": name, "lat": h_lat, "lng": h_lng, "distance": round(dist, 2)
#                 })
        
#         hospital_list.sort(key=lambda x: x["distance"])
#         return JsonResponse(hospital_list[:6], safe=False)
#     except Exception as e:
#         return JsonResponse({"error": str(e)}, status=400)

# # ================= 3. SEISMIC MODEL & PREDICTION HELPERS =================
# MODEL_PATH = r"G:\earthquake_today\earthquake_project\ml_models\earthquake_pipeline_model.pkl"
# try:
#     seismic_brain = joblib.load(MODEL_PATH)
# except Exception as e:
#     print(f"⚠️ Warning: Model not loaded. Error: {e}")
#     seismic_brain = None

# def get_risk_level(intensity):
#     """Convert intensity score to risk level (high-level prediction)."""
#     if intensity < 2: return "MINIMAL"
#     elif intensity < 4: return "LOW"
#     elif intensity < 5.5: return "MODERATE"
#     elif intensity < 7: return "HIGH"
#     else: return "CRITICAL"

# def get_expected_damage(intensity):
#     """Provide expected structural damage assessment."""
#     damage_map = {
#         "MINIMAL": "Negligible - Not felt; No structural impact",
#         "LOW": "Light - Felt indoors; Minor non-structural damage",
#         "MODERATE": "Moderate - Some plaster cracking; Possible structural concerns",
#         "HIGH": "Heavy - Considerable damage; Structural damage likely",
#         "CRITICAL": "Very Heavy - Extensive damage; Major structural failure expected"
#     }
#     return damage_map.get(get_risk_level(intensity), "Unknown")

# def get_radius_km(magnitude, depth_km):
#     """
#     Calculate affected radius with depth consideration.
#     Deeper quakes affect smaller area; shallow quakes affect larger area.
#     """
#     depth_factor = max(0.3, 1 - (depth_km / 250))  # Deeper = smaller radius
#     base_radius = 10 ** (0.4 * magnitude - 1)  # Adjusted slightly to match UI visual radius
#     return base_radius * depth_factor

# def get_nearest_history(request):
#     """
#     Predict earthquake depth using ML model AND calculates affected hospitals
#     distance from the simulated epicenter within the danger radius.
#     """
#     try:
#         lat = float(request.GET.get('lat'))
#         lng = float(request.GET.get('lng'))
#         user_mag = float(request.GET.get('mag', 6.0))

#         # 1. Fetch all earthquakes and compute distances
#         earthquakes = HistoricalEarthquake.objects.filter(
#             latitude__isnull=False,
#             longitude__isnull=False,
#             depth__isnull=False
#         )

#         if not earthquakes.exists():
#             return JsonResponse({"error": "No historical earthquake data available."}, status=404)

#         nearest = None
#         min_distance = float('inf')
#         for eq in earthquakes:
#             dist = eq.distance_to(lat, lng)
#             if dist is not None and dist < min_distance:
#                 min_distance = dist
#                 nearest = eq

#         if nearest is None:
#             return JsonResponse({"error": "No historical earthquake data available."}, status=404)

#         if seismic_brain is None:
#             raise Exception("Model not loaded. Please train the model first.")
        
#         # 2. AI Inference: Predict DEPTH based on the nearest historical profile
#         lat_hist = nearest.latitude
#         lon_hist = nearest.longitude

#         feature_vector = [[
#             user_mag, lat_hist, lon_hist,
#             getattr(nearest, "nst", 0) or 0,
#             getattr(nearest, "gap", 0) or 0,
#             getattr(nearest, "dmin", 0) or 0,
#             getattr(nearest, "rms", 0) or 0,
#             getattr(nearest, "horizontal_error", 0) or 0,
#             getattr(nearest, "depth_error", 0) or 0,
#             getattr(nearest, "mag_error", 0) or 0,
#             getattr(nearest, "mag_nst", 0) or 0,
#             lat_hist * lon_hist,
#             lat_hist ** 2,
#             lon_hist ** 2
#         ]]

#         # MODEL PREDICTS LOG_DEPTH -> Convert back to real depth via expm1
#         log_depth_pred = seismic_brain.predict(feature_vector)[0]
#         predicted_depth = np.expm1(log_depth_pred)

#         # Calculate intensity based on magnitude and PREDICTED depth
#         # Shallow quakes hit harder, deep quakes dissipate energy
#         depth_penalty = predicted_depth / 50.0
#         ai_intensity = float(np.clip((user_mag * 1.3) - depth_penalty, 1, 10))
        
#         # 3. Calculate affected radius using PREDICTED DEPTH
#         radius = get_radius_km(user_mag, predicted_depth)
        
#         # 4. Determine risk level
#         risk_level = get_risk_level(ai_intensity)
#         damage_assessment = get_expected_damage(ai_intensity)
        
#         # ✨ FIX: Calculate Dynamic Model Confidence
#         # High magnitudes (rare events) and deep quakes introduce more prediction uncertainty
#         base_confidence = 96.5
#         mag_penalty = (user_mag - 5.0) * 2.8 if user_mag > 5.0 else 0
#         depth_penalty_conf = predicted_depth / 40.0
#         confidence = max(65.0, min(99.0, base_confidence - mag_penalty - depth_penalty_conf))

#         # 5. EXACT DISTANCE CALCULATION: Distance to ALL hospitals and filter by radius
#         affected_hospitals = []
#         file_path = os.path.join(settings.BASE_DIR, "static/data/hospitals.geojson")
        
#         if os.path.exists(file_path):
#             with open(file_path, encoding="utf-8") as f:
#                 hospitals_data = json.load(f)["features"]
            
#             for h in hospitals_data:
#                 if h.get("geometry"):
#                     h_lng, h_lat = h["geometry"]["coordinates"]
#                     props = h["properties"]
                    
#                     # Haversine distance from simulated EPICENTER to HOSPITAL
#                     R = 6371
#                     phi1, phi2 = math.radians(lat), math.radians(h_lat)
#                     dphi = math.radians(h_lat - lat)
#                     dlambda = math.radians(h_lng - lng)
#                     a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
#                     h_dist = 2 * R * math.asin(math.sqrt(a))
                    
#                     # Only include if inside the calculated impact radius
#                     if h_dist <= radius:
#                         affected_hospitals.append({
#                             "name": props.get("NAME", "Unknown"),
#                             "lat": h_lat,
#                             "lng": h_lng,
#                             "distance": round(h_dist, 2), # ACCURATE DISTANCE
#                             "beds": props.get("BEDS", 0) if props.get("BEDS") != -999 else 0,
#                             "type": props.get("TYPE", "Unknown"),
#                             "status": props.get("STATUS", "Unknown"),
#                             "telephone": props.get("TELEPHONE", "N/A")
#                         })
            
#             # Sort hospitals by closest to epicenter
#             affected_hospitals.sort(key=lambda x: x["distance"])

#         return JsonResponse({
#             "place": nearest.place,
#             "mag": user_mag,
#             "radius": round(radius, 2),
#             "intensity": ai_intensity,
#             "risk_level": risk_level,
#             "expected_damage": damage_assessment,
#             "dist_from_click": round(min_distance, 2),
#             "depth": float(predicted_depth), # RETURN AI PREDICTED DEPTH
#             "confidence": confidence,
#             "assessment": f"Earthquake of magnitude {user_mag} at predicted depth {predicted_depth:.1f}km is expected to cause {risk_level} damage.",
#             "affected_hospitals": affected_hospitals,
#             "total_beds_at_risk": sum(h['beds'] for h in affected_hospitals)
#         })
#     except Exception as e:
#         return JsonResponse({"error": str(e)}, status=400)

# def get_weather_proxy(request):
#     lat = request.GET.get('lat')
#     lng = request.GET.get('lng')
#     api_key = '53719aca4723375a9e4d9dae1712951c'
#     url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lng}&appid={api_key}&units=metric"
#     try:
#         response = requests.get(url, timeout=5)
#         return JsonResponse(response.json())
#     except Exception as e:
#         return JsonResponse({'error': str(e)}, status=500)

# # ================= 4. PDF REPORT GENERATOR =================
# @csrf_exempt
# def report(request):
#     """
#     Generates a Seismic Safety PDF report.
#     The Table is placed ABOVE the Map Image.
#     """
#     # 1. Capture Data from POST or GET
#     data = request.POST if request.method == "POST" else request.GET
    
#     place = data.get("place", "Simulated Area")
#     mag = data.get("mag", "0.0")
#     data_dist = float(data.get("dist_from_click", "0")) 
#     h_name = data.get("hname", "Emergency Facility")
#     travel_dist = data.get("dist", "0.0")
#     weather = data.get("weather", "Clear")
#     h_lat = data.get("hlat", "0")
#     h_lng = data.get("hlng", "0")
#     ai_intensity = data.get("intensity", "0.0")
#     depth = data.get("depth", "0.0") # ✅ ADDED: Grabbing Depth from JS

#     # 2. Generate Google Maps Navigation Link
#     google_maps_url = f"https://www.google.com/maps/dir/?api=1&destination={h_lat},{h_lng}&travelmode=driving"
#     link_html = f'<a href="{google_maps_url}" color="blue"><u>Open Live GPS Navigation</u></a>'
    
#     # 3. PDF Document Setup
#     file_path = os.path.join(settings.BASE_DIR, "EQ_Safety_Report.pdf")
#     doc = SimpleDocTemplate(file_path, pagesize=A4)
#     styles = getSampleStyleSheet()
#     story = []

#     # --- PDF CONTENT: HEADER ---
#     story.append(Paragraph("EARTHQUAKE HAZARD ASSESSMENT REPORT", styles["Title"]))
#     story.append(Spacer(1, 10))
#     current_date = datetime.now().strftime("%d/%m/%Y")
#     story.append(Paragraph(f"Generated on: {current_date}", styles["Normal"]))
#     story.append(Spacer(1, 20))

#     # --- 4. DATA TABLE (NOW AT THE TOP) ---
#     confidence_val = max(0, 100 - (data_dist * 2))
#     accuracy_rating = f"{int(confidence_val)}% (Moderate)"
#     if confidence_val > 80: accuracy_rating = f"{int(confidence_val)}% (High)"

#     table_data = [
#         ["ASSESSMENT PARAMETER", "VALUE / DETAILS"],
#         ["Target Region", place],
#         ["Simulated Magnitude", f"{mag} Mw"],
#         ["AI Predicted Depth", f"{depth} km"], # ✅ ADDED: Displaying Depth in the PDF Table
#         ["AI Intensity Rating", f"{ai_intensity}"],
#         ["Structural Risk", "HIGH" if float(ai_intensity) > 5.5 else "LOW/MODERATE"],
#         ["Designated Hospital", h_name],
#         ["Route Distance", f"{travel_dist} km"],
#         ["Current Weather", weather],
#         ["Model Confidence", accuracy_rating],
#         ["Navigation Link", Paragraph(link_html, styles["Normal"])] 
#     ]

#     report_table = Table(table_data, colWidths=[180, 270])
#     report_table.setStyle(TableStyle([
#         ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
#         ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
#         ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
#         ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
#         ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
#         ('GRID', (0, 0), (-1, -1), 1, colors.grey),
#         ('TEXTCOLOR', (1, 5), (1, 5), colors.red if float(ai_intensity) > 5.5 else colors.green),
#     ]))
    
#     story.append(report_table)
#     story.append(Spacer(1, 25)) # Space between Table and Image

#     # --- 5. MAP IMAGE (NOW AT THE BOTTOM) ---
#     map_image_data = data.get("map_image") 
#     if map_image_data and ";base64," in map_image_data:
#         try:
#             format, imgstr = map_image_data.split(';base64,') 
#             img_data = base64.b64decode(imgstr)
#             map_img = RLImage(BytesIO(img_data), width=480, height=300)
            
#             story.append(Paragraph("<b>Spatial Analysis Snapshot (Routes & Evacuation Zones):</b>", styles["Heading3"]))
#             story.append(Spacer(1, 8))
#             story.append(map_img) 
#         except Exception as e:
#             story.append(Paragraph(f"<i>(Visual context snapshot unavailable: {e})</i>", styles["Normal"]))

#     # Final Step: Build the PDF
#     doc.build(story)
    
#     return FileResponse(
#         open(file_path, "rb"), 
#         as_attachment=True, 
#         filename=f"Seismic_Safety_Report.pdf"
#     )

# by mag of accuracy score



# import requests
# from django.shortcuts import render
# from django.http import JsonResponse, FileResponse
# from django.conf import settings
# import math, os, json
# import numpy as np
# import joblib

# # PDF Generation Imports
# import base64
# from io import BytesIO
# from datetime import datetime
# from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
# from reportlab.lib.styles import getSampleStyleSheet
# from reportlab.lib.pagesizes import A4
# from reportlab.lib import colors
# from django.views.decorators.csrf import csrf_exempt

# # Import your model
# from .models import HistoricalEarthquake

# # ================= 1. HOME PAGE =================
# def index(request):
#     """Renders the main map interface."""
#     return render(request, "index.html")

# # ================= 2. NEAREST HOSPITAL SEARCH =================
# def nearest_hospital(request):
#     """Reads hospitals.geojson and returns closest facilities via Haversine."""
#     try:
#         lat = float(request.GET.get("lat"))
#         lng = float(request.GET.get("lng"))
        
#         file_path = os.path.join(settings.BASE_DIR, "static/data/hospitals.geojson")
        
#         with open(file_path, encoding="utf-8") as f:
#             hospitals_data = json.load(f)["features"]
        
#         hospital_list = []
#         for h in hospitals_data:
#             if h.get("geometry"):
#                 h_lng, h_lat = h["geometry"]["coordinates"]
#                 name = h["properties"].get("NAME") or "Emergency Facility"
                
#                 # Haversine distance formula
#                 R = 6371
#                 phi1, phi2 = math.radians(lat), math.radians(h_lat)
#                 dphi = math.radians(h_lat - lat)
#                 dlambda = math.radians(h_lng - lng)
#                 a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
#                 dist = 2 * R * math.asin(math.sqrt(a))
                
#                 hospital_list.append({
#                     "name": name, "lat": h_lat, "lng": h_lng, "distance": round(dist, 2)
#                 })
        
#         hospital_list.sort(key=lambda x: x["distance"])
#         return JsonResponse(hospital_list[:6], safe=False)
#     except Exception as e:
#         return JsonResponse({"error": str(e)}, status=400)

# # ================= 3. SEISMIC MODEL & PREDICTION HELPERS =================
# MODEL_PATH = r"G:\earthquake_today\earthquake_project\ml_models\earthquake_pipeline_model.pkl"
# try:
#     seismic_brain = joblib.load(MODEL_PATH)
# except Exception as e:
#     print(f"⚠️ Warning: Model not loaded. Error: {e}")
#     seismic_brain = None

# def get_risk_level(intensity):
#     """Convert intensity score to risk level (high-level prediction)."""
#     if intensity < 2: return "MINIMAL"
#     elif intensity < 4: return "LOW"
#     elif intensity < 5.5: return "MODERATE"
#     elif intensity < 7: return "HIGH"
#     else: return "CRITICAL"

# def get_expected_damage(intensity):
#     """Provide expected structural damage assessment."""
#     damage_map = {
#         "MINIMAL": "Negligible - Not felt; No structural impact",
#         "LOW": "Light - Felt indoors; Minor non-structural damage",
#         "MODERATE": "Moderate - Some plaster cracking; Possible structural concerns",
#         "HIGH": "Heavy - Considerable damage; Structural damage likely",
#         "CRITICAL": "Very Heavy - Extensive damage; Major structural failure expected"
#     }
#     return damage_map.get(get_risk_level(intensity), "Unknown")

# def get_radius_km(magnitude, depth_km):
#     """
#     Calculate affected radius with depth consideration.
#     Deeper quakes affect smaller area; shallow quakes affect larger area.
#     """
#     depth_factor = max(0.3, 1 - (depth_km / 250))  # Deeper = smaller radius
#     base_radius = 10 ** (0.4 * magnitude - 1)  # Adjusted slightly to match UI visual radius
#     return base_radius * depth_factor

# def get_nearest_history(request):
#     """
#     Predict earthquake depth using ML model AND calculates affected hospitals
#     distance from the simulated epicenter within the danger radius.
#     """
#     try:
#         lat = float(request.GET.get('lat'))
#         lng = float(request.GET.get('lng'))
#         user_mag = float(request.GET.get('mag', 6.0))

#         # 1. Fetch all earthquakes and compute distances
#         earthquakes = HistoricalEarthquake.objects.filter(
#             latitude__isnull=False,
#             longitude__isnull=False,
#             depth__isnull=False
#         )

#         if not earthquakes.exists():
#             return JsonResponse({"error": "No historical earthquake data available."}, status=404)

#         nearest = None
#         min_distance = float('inf')
#         for eq in earthquakes:
#             dist = eq.distance_to(lat, lng)
#             if dist is not None and dist < min_distance:
#                 min_distance = dist
#                 nearest = eq

#         if nearest is None:
#             return JsonResponse({"error": "No historical earthquake data available."}, status=404)

#         if seismic_brain is None:
#             raise Exception("Model not loaded. Please train the model first.")
        
#         # 2. AI Inference: Predict DEPTH based on the nearest historical profile
#         lat_hist = nearest.latitude
#         lon_hist = nearest.longitude

#         feature_vector = [[
#             user_mag, lat_hist, lon_hist,
#             getattr(nearest, "nst", 0) or 0,
#             getattr(nearest, "gap", 0) or 0,
#             getattr(nearest, "dmin", 0) or 0,
#             getattr(nearest, "rms", 0) or 0,
#             getattr(nearest, "horizontal_error", 0) or 0,
#             getattr(nearest, "depth_error", 0) or 0,
#             getattr(nearest, "mag_error", 0) or 0,
#             getattr(nearest, "mag_nst", 0) or 0,
#             lat_hist * lon_hist,
#             lat_hist ** 2,
#             lon_hist ** 2
#         ]]

#         # MODEL PREDICTS LOG_DEPTH -> Convert back to real depth via expm1
#         log_depth_pred = seismic_brain.predict(feature_vector)[0]
#         predicted_depth = np.expm1(log_depth_pred)

#         # Calculate intensity based on magnitude and PREDICTED depth
#         # Shallow quakes hit harder, deep quakes dissipate energy
#         depth_penalty = predicted_depth / 50.0
#         ai_intensity = float(np.clip((user_mag * 1.3) - depth_penalty, 1, 10))
        
#         # 3. Calculate affected radius using PREDICTED DEPTH
#         radius = get_radius_km(user_mag, predicted_depth)
        
#         # 4. Determine risk level
#         risk_level = get_risk_level(ai_intensity)
#         damage_assessment = get_expected_damage(ai_intensity)
#         confidence = min(100, max(0, 100 - (min_distance * 2)))

#         # 5. EXACT DISTANCE CALCULATION: Distance to ALL hospitals and filter by radius
#         affected_hospitals = []
#         file_path = os.path.join(settings.BASE_DIR, "static/data/hospitals.geojson")
        
#         if os.path.exists(file_path):
#             with open(file_path, encoding="utf-8") as f:
#                 hospitals_data = json.load(f)["features"]
            
#             for h in hospitals_data:
#                 if h.get("geometry"):
#                     h_lng, h_lat = h["geometry"]["coordinates"]
#                     props = h["properties"]
                    
#                     # Haversine distance from simulated EPICENTER to HOSPITAL
#                     R = 6371
#                     phi1, phi2 = math.radians(lat), math.radians(h_lat)
#                     dphi = math.radians(h_lat - lat)
#                     dlambda = math.radians(h_lng - lng)
#                     a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
#                     h_dist = 2 * R * math.asin(math.sqrt(a))
                    
#                     # Only include if inside the calculated impact radius
#                     if h_dist <= radius:
#                         affected_hospitals.append({
#                             "name": props.get("NAME", "Unknown"),
#                             "lat": h_lat,
#                             "lng": h_lng,
#                             "distance": round(h_dist, 2), # ACCURATE DISTANCE
#                             "beds": props.get("BEDS", 0) if props.get("BEDS") != -999 else 0,
#                             "type": props.get("TYPE", "Unknown"),
#                             "status": props.get("STATUS", "Unknown"),
#                             "telephone": props.get("TELEPHONE", "N/A")
#                         })
            
#             # Sort hospitals by closest to epicenter
#             affected_hospitals.sort(key=lambda x: x["distance"])

#         return JsonResponse({
#             "place": nearest.place,
#             "mag": user_mag,
#             "radius": round(radius, 2),
#             "intensity": ai_intensity,
#             "risk_level": risk_level,
#             "expected_damage": damage_assessment,
#             "dist_from_click": round(min_distance, 2),
#             "depth": float(predicted_depth), # RETURN AI PREDICTED DEPTH
#             "confidence": confidence,
#             "assessment": f"Earthquake of magnitude {user_mag} at predicted depth {predicted_depth:.1f}km is expected to cause {risk_level} damage.",
#             "affected_hospitals": affected_hospitals,
#             "total_beds_at_risk": sum(h['beds'] for h in affected_hospitals)
#         })
#     except Exception as e:
#         return JsonResponse({"error": str(e)}, status=400)

# def get_weather_proxy(request):
#     lat = request.GET.get('lat')
#     lng = request.GET.get('lng')
#     api_key = '53719aca4723375a9e4d9dae1712951c'
#     url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lng}&appid={api_key}&units=metric"
#     try:
#         response = requests.get(url, timeout=5)
#         return JsonResponse(response.json())
#     except Exception as e:
#         return JsonResponse({'error': str(e)}, status=500)

# # ================= 4. PDF REPORT GENERATOR =================
# @csrf_exempt
# def report(request):
#     """
#     Generates a Seismic Safety PDF report.
#     The Table is placed ABOVE the Map Image.
#     """
#     # 1. Capture Data from POST or GET
#     data = request.POST if request.method == "POST" else request.GET
    
#     place = data.get("place", "Simulated Area")
#     mag = data.get("mag", "0.0")
#     data_dist = float(data.get("dist_from_click", "0")) 
#     h_name = data.get("hname", "Emergency Facility")
#     travel_dist = data.get("dist", "0.0")
#     weather = data.get("weather", "Clear")
#     h_lat = data.get("hlat", "0")
#     h_lng = data.get("hlng", "0")
#     ai_intensity = data.get("intensity", "0.0")

#     # 2. Generate Google Maps Navigation Link
#     google_maps_url = f"https://www.google.com/maps/dir/?api=1&destination={h_lat},{h_lng}&travelmode=driving"
#     link_html = f'<a href="{google_maps_url}" color="blue"><u>Open Live GPS Navigation</u></a>'
    
#     # 3. PDF Document Setup
#     file_path = os.path.join(settings.BASE_DIR, "EQ_Safety_Report.pdf")
#     doc = SimpleDocTemplate(file_path, pagesize=A4)
#     styles = getSampleStyleSheet()
#     story = []

#     # --- PDF CONTENT: HEADER ---
#     story.append(Paragraph("EARTHQUAKE HAZARD ASSESSMENT REPORT", styles["Title"]))
#     story.append(Spacer(1, 10))
#     current_date = datetime.now().strftime("%d/%m/%Y")
#     story.append(Paragraph(f"Generated on: {current_date}", styles["Normal"]))
#     story.append(Spacer(1, 20))

#     # --- 4. DATA TABLE (NOW AT THE TOP) ---
#     confidence_val = max(0, 100 - (data_dist * 2))
#     accuracy_rating = f"{int(confidence_val)}% (Moderate)"
#     if confidence_val > 80: accuracy_rating = f"{int(confidence_val)}% (High)"

#     table_data = [
#         ["ASSESSMENT PARAMETER", "VALUE / DETAILS"],
#         ["Target Region", place],
#         ["Simulated Magnitude", f"{mag} Mw"],
#         ["AI Intensity Rating", f"{ai_intensity}"],
#         ["Structural Risk", "HIGH" if float(ai_intensity) > 5.5 else "LOW/MODERATE"],
#         ["Designated Hospital", h_name],
#         ["Route Distance", f"{travel_dist} km"],
#         ["Current Weather", weather],
#         ["Model Confidence", accuracy_rating],
#         ["Navigation Link", Paragraph(link_html, styles["Normal"])] 
#     ]

#     report_table = Table(table_data, colWidths=[180, 270])
#     report_table.setStyle(TableStyle([
#         ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
#         ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
#         ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
#         ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
#         ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
#         ('GRID', (0, 0), (-1, -1), 1, colors.grey),
#         ('TEXTCOLOR', (1, 4), (1, 4), colors.red if float(ai_intensity) > 5.5 else colors.green),
#     ]))
    
#     story.append(report_table)
#     story.append(Spacer(1, 25)) # Space between Table and Image

#     # --- 5. MAP IMAGE (NOW AT THE BOTTOM) ---
#     map_image_data = data.get("map_image") 
#     if map_image_data and ";base64," in map_image_data:
#         try:
#             format, imgstr = map_image_data.split(';base64,') 
#             img_data = base64.b64decode(imgstr)
#             map_img = RLImage(BytesIO(img_data), width=480, height=300)
            
#             story.append(Paragraph("<b>Spatial Analysis Snapshot (Routes & Heatmap):</b>", styles["Heading3"]))
#             story.append(Spacer(1, 8))
#             story.append(map_img) 
#         except Exception as e:
#             story.append(Paragraph(f"<i>(Visual context snapshot unavailable: {e})</i>", styles["Normal"]))

#     # Final Step: Build the PDF
#     doc.build(story)
    
#     return FileResponse(
#         open(file_path, "rb"), 
#         as_attachment=True, 
#         filename=f"Seismic_Safety_Report_{place[:15]}.pdf"
#     )





# import requests
# from django.shortcuts import render
# from django.http import JsonResponse, FileResponse
# from django.conf import settings
# import math, os, json
# import numpy as np
# import joblib

# # PDF Generation Imports
# from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
# from reportlab.lib.styles import getSampleStyleSheet
# from reportlab.lib.pagesizes import A4
# from reportlab.lib import colors

# # Import your model
# from .models import HistoricalEarthquake

# # ================= 1. HOME PAGE =================
# def index(request):
#     """Renders the main map interface."""
#     return render(request, "index.html")

# # ================= 2. NEAREST HOSPITAL SEARCH =================
# def nearest_hospital(request):
#     """Reads hospitals.geojson and returns closest facilities via Haversine."""
#     try:
#         lat = float(request.GET.get("lat"))
#         lng = float(request.GET.get("lng"))
        
#         file_path = os.path.join(settings.BASE_DIR, "static/data/hospitals.geojson")
        
#         with open(file_path, encoding="utf-8") as f:
#             hospitals_data = json.load(f)["features"]
        
#         hospital_list = []
#         for h in hospitals_data:
#             if h.get("geometry"):
#                 h_lng, h_lat = h["geometry"]["coordinates"]
#                 name = h["properties"].get("NAME") or "Emergency Facility"
                
#                 # Haversine distance formula
#                 R = 6371
#                 phi1, phi2 = math.radians(lat), math.radians(h_lat)
#                 dphi = math.radians(h_lat - lat)
#                 dlambda = math.radians(h_lng - lng)
#                 a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
#                 dist = 2 * R * math.asin(math.sqrt(a))
                
#                 hospital_list.append({
#                     "name": name, "lat": h_lat, "lng": h_lng, "distance": round(dist, 2)
#                 })
        
#         hospital_list.sort(key=lambda x: x["distance"])
#         return JsonResponse(hospital_list[:6], safe=False)
#     except Exception as e:
#         return JsonResponse({"error": str(e)}, status=400)

# # ================= 3. SEISMIC MODEL & PREDICTION HELPERS =================
# MODEL_PATH = r"G:\earthquake_today\earthquake_project\ml_models\earthquake_pipeline_model.pkl"
# try:
#     seismic_brain = joblib.load(MODEL_PATH)
# except Exception as e:
#     print(f"⚠️ Warning: Model not loaded. Error: {e}")
#     seismic_brain = None

# def get_risk_level(intensity):
#     """Convert intensity score to risk level (high-level prediction)."""
#     if intensity < 2: return "MINIMAL"
#     elif intensity < 4: return "LOW"
#     elif intensity < 5.5: return "MODERATE"
#     elif intensity < 7: return "HIGH"
#     else: return "CRITICAL"

# def get_expected_damage(intensity):
#     """Provide expected structural damage assessment."""
#     damage_map = {
#         "MINIMAL": "Negligible - Not felt; No structural impact",
#         "LOW": "Light - Felt indoors; Minor non-structural damage",
#         "MODERATE": "Moderate - Some plaster cracking; Possible structural concerns",
#         "HIGH": "Heavy - Considerable damage; Structural damage likely",
#         "CRITICAL": "Very Heavy - Extensive damage; Major structural failure expected"
#     }
#     return damage_map.get(get_risk_level(intensity), "Unknown")

# def get_radius_km(magnitude, depth_km):
#     """
#     Calculate affected radius with depth consideration.
#     Deeper quakes affect smaller area; shallow quakes affect larger area.
#     """
#     depth_factor = max(0.3, 1 - (depth_km / 250))  # Deeper = smaller radius
#     base_radius = 10 ** (0.4 * magnitude - 1)  # Adjusted slightly to match UI visual radius
#     return base_radius * depth_factor

# def get_nearest_history(request):
#     """
#     Predict earthquake depth using ML model AND calculates affected hospitals
#     distance from the simulated epicenter within the danger radius.
#     """
#     try:
#         lat = float(request.GET.get('lat'))
#         lng = float(request.GET.get('lng'))
#         user_mag = float(request.GET.get('mag', 6.0))

#         # 1. Fetch all earthquakes and compute distances
#         earthquakes = HistoricalEarthquake.objects.filter(
#             latitude__isnull=False,
#             longitude__isnull=False,
#             depth__isnull=False
#         )

#         if not earthquakes.exists():
#             return JsonResponse({"error": "No historical earthquake data available."}, status=404)

#         nearest = None
#         min_distance = float('inf')
#         for eq in earthquakes:
#             dist = eq.distance_to(lat, lng)
#             if dist is not None and dist < min_distance:
#                 min_distance = dist
#                 nearest = eq

#         if nearest is None:
#             return JsonResponse({"error": "No historical earthquake data available."}, status=404)

#         if seismic_brain is None:
#             raise Exception("Model not loaded. Please train the model first.")
        
#         # 2. AI Inference: Predict DEPTH based on the nearest historical profile
#         lat_hist = nearest.latitude
#         lon_hist = nearest.longitude

#         feature_vector = [[
#             user_mag, lat_hist, lon_hist,
#             getattr(nearest, "nst", 0) or 0,
#             getattr(nearest, "gap", 0) or 0,
#             getattr(nearest, "dmin", 0) or 0,
#             getattr(nearest, "rms", 0) or 0,
#             getattr(nearest, "horizontal_error", 0) or 0,
#             getattr(nearest, "depth_error", 0) or 0,
#             getattr(nearest, "mag_error", 0) or 0,
#             getattr(nearest, "mag_nst", 0) or 0,
#             lat_hist * lon_hist,
#             lat_hist ** 2,
#             lon_hist ** 2
#         ]]

#         # MODEL PREDICTS LOG_DEPTH -> Convert back to real depth via expm1
#         log_depth_pred = seismic_brain.predict(feature_vector)[0]
#         predicted_depth = np.expm1(log_depth_pred)

#         # Calculate intensity based on magnitude and PREDICTED depth
#         # Shallow quakes hit harder, deep quakes dissipate energy
#         depth_penalty = predicted_depth / 50.0
#         ai_intensity = float(np.clip((user_mag * 1.3) - depth_penalty, 1, 10))
        
#         # 3. Calculate affected radius using PREDICTED DEPTH
#         radius = get_radius_km(user_mag, predicted_depth)
        
#         # 4. Determine risk level
#         risk_level = get_risk_level(ai_intensity)
#         damage_assessment = get_expected_damage(ai_intensity)
#         confidence = min(100, max(0, 100 - (min_distance * 2)))

#         # 5. EXACT DISTANCE CALCULATION: Distance to ALL hospitals and filter by radius
#         affected_hospitals = []
#         file_path = os.path.join(settings.BASE_DIR, "static/data/hospitals.geojson")
        
#         if os.path.exists(file_path):
#             with open(file_path, encoding="utf-8") as f:
#                 hospitals_data = json.load(f)["features"]
            
#             for h in hospitals_data:
#                 if h.get("geometry"):
#                     h_lng, h_lat = h["geometry"]["coordinates"]
#                     props = h["properties"]
                    
#                     # Haversine distance from simulated EPICENTER to HOSPITAL
#                     R = 6371
#                     phi1, phi2 = math.radians(lat), math.radians(h_lat)
#                     dphi = math.radians(h_lat - lat)
#                     dlambda = math.radians(h_lng - lng)
#                     a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
#                     h_dist = 2 * R * math.asin(math.sqrt(a))
                    
#                     # Only include if inside the calculated impact radius
#                     if h_dist <= radius:
#                         affected_hospitals.append({
#                             "name": props.get("NAME", "Unknown"),
#                             "lat": h_lat,
#                             "lng": h_lng,
#                             "distance": round(h_dist, 2), # ACCURATE DISTANCE
#                             "beds": props.get("BEDS", 0) if props.get("BEDS") != -999 else 0,
#                             "type": props.get("TYPE", "Unknown"),
#                             "status": props.get("STATUS", "Unknown"),
#                             "telephone": props.get("TELEPHONE", "N/A")
#                         })
            
#             # Sort hospitals by closest to epicenter
#             affected_hospitals.sort(key=lambda x: x["distance"])

#         return JsonResponse({
#             "place": nearest.place,
#             "mag": user_mag,
#             "radius": round(radius, 2),
#             "intensity": ai_intensity,
#             "risk_level": risk_level,
#             "expected_damage": damage_assessment,
#             "dist_from_click": round(min_distance, 2),
#             "depth": float(predicted_depth), # RETURN AI PREDICTED DEPTH
#             "confidence": confidence,
#             "assessment": f"Earthquake of magnitude {user_mag} at predicted depth {predicted_depth:.1f}km is expected to cause {risk_level} damage.",
#             "affected_hospitals": affected_hospitals,
#             "total_beds_at_risk": sum(h['beds'] for h in affected_hospitals)
#         })
#     except Exception as e:
#         return JsonResponse({"error": str(e)}, status=400)

# def get_weather_proxy(request):
#     lat = request.GET.get('lat')
#     lng = request.GET.get('lng')
#     api_key = '53719aca4723375a9e4d9dae1712951c'
#     url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lng}&appid={api_key}&units=metric"
#     try:
#         response = requests.get(url, timeout=5)
#         return JsonResponse(response.json())
#     except Exception as e:
#         return JsonResponse({'error': str(e)}, status=500)





# # import requests
# # from django.shortcuts import render
# # from django.http import JsonResponse, FileResponse
# # from django.conf import settings
# # import math, os, json
# # import numpy as np
# # import joblib
# # # PDF Generation Imports
# # from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
# # from reportlab.lib.styles import getSampleStyleSheet
# # from reportlab.lib.pagesizes import A4
# # from reportlab.lib import colors

# # # Import your model
# # from .models import HistoricalEarthquake

# # # ================= 1. HOME PAGE =================
# # def index(request):
# #     """Renders the main map interface."""
# #     return render(request, "index.html")


# # # ================= 2. NEAREST HOSPITAL SEARCH =================
# # def nearest_hospital(request):
# #     """Reads hospitals.geojson and returns closest facilities via Haversine."""
# #     try:
# #         lat = float(request.GET.get("lat"))
# #         lng = float(request.GET.get("lng"))
        
# #         file_path = os.path.join(settings.BASE_DIR, "static/data/hospitals.geojson")
        
# #         with open(file_path, encoding="utf-8") as f:
# #             hospitals_data = json.load(f)["features"]
        
# #         hospital_list = []
# #         for h in hospitals_data:
# #             if h.get("geometry"):
# #                 h_lng, h_lat = h["geometry"]["coordinates"]
# #                 name = h["properties"].get("NAME") or "Emergency Facility"
                
# #                 # Haversine distance formula
# #                 R = 6371
# #                 phi1, phi2 = math.radians(lat), math.radians(h_lat)
# #                 dphi = math.radians(h_lat - lat)
# #                 dlambda = math.radians(h_lng - lng)
# #                 a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
# #                 dist = 2 * R * math.asin(math.sqrt(a))
                
# #                 hospital_list.append({
# #                     "name": name, "lat": h_lat, "lng": h_lng, "distance": round(dist, 2)
# #                 })

# #         hospital_list.sort(key=lambda x: x["distance"])
# #         return JsonResponse(hospital_list[:6], safe=False)
# #     except Exception as e:
# #         return JsonResponse({"error": str(e)}, status=400)

# # # ================= 3. SEISMIC MODEL & PREDICTION HELPERS =================
# # MODEL_PATH = r"G:\earthquake_today\earthquake_project\ml_models\earthquake_pipeline_model.pkl"
# # try:
# #     seismic_brain = joblib.load(MODEL_PATH)
# # except Exception as e:
# #     print(f"⚠️ Warning: Model not loaded. Error: {e}")
# #     seismic_brain = None

# # def get_risk_level(intensity):
# #     """Convert intensity score to risk level (high-level prediction)."""
# #     if intensity < 2: return "MINIMAL"
# #     elif intensity < 4: return "LOW"
# #     elif intensity < 5.5: return "MODERATE"
# #     elif intensity < 7: return "HIGH"
# #     else: return "CRITICAL"

# # def get_expected_damage(intensity):
# #     """Provide expected structural damage assessment."""
# #     damage_map = {
# #         "MINIMAL": "Negligible - Not felt; No structural impact",
# #         "LOW": "Light - Felt indoors; Minor non-structural damage",
# #         "MODERATE": "Moderate - Some plaster cracking; Possible structural concerns",
# #         "HIGH": "Heavy - Considerable damage; Structural damage likely",
# #         "CRITICAL": "Very Heavy - Extensive damage; Major structural failure expected"
# #     }
# #     return damage_map.get(get_risk_level(intensity), "Unknown")

# # def get_radius_km(magnitude, depth_km):
# #     """
# #     Calculate affected radius with depth consideration.
# #     Deeper quakes affect smaller area; shallow quakes affect larger area.
# #     """
# #     depth_factor = max(0.3, 1 - (depth_km / 250))  # Deeper = smaller radius
# #     base_radius = 10 ** (0.5 * magnitude - 1.2)
# #     return base_radius * depth_factor

# # def get_nearest_history(request):
# #     """
# #     Predict earthquake impact using ML model AND calculates affected hospitals
# #     distance from the simulated epicenter within the danger radius.
# #     """
# #     try:
# #         lat = float(request.GET.get('lat'))
# #         lng = float(request.GET.get('lng'))
# #         user_mag = float(request.GET.get('mag', 6.0))

# #         # 1. Fetch all earthquakes and compute distances
# #         earthquakes = HistoricalEarthquake.objects.filter(
# #             latitude__isnull=False,
# #             longitude__isnull=False,
# #             depth__isnull=False
# #         )

# #         if not earthquakes.exists():
# #             return JsonResponse({"error": "No historical earthquake data available."}, status=404)

# #         nearest = None
# #         min_distance = float('inf')
# #         for eq in earthquakes:
# #             dist = eq.distance_to(lat, lng)
# #             if dist is not None and dist < min_distance:
# #                 min_distance = dist
# #                 nearest = eq

# #         if nearest is None:
# #             return JsonResponse({"error": "No historical earthquake data available."}, status=404)

# #         if seismic_brain is None:
# #             raise Exception("Model not loaded. Please train the model first.")
        
# #         # 2. AI Inference: Build full feature vector expected by XGBoost model
# #         lat_hist = nearest.latitude
# #         lon_hist = nearest.longitude

# #         feature_vector = [[
# #             user_mag, lat_hist, lon_hist,
# #             getattr(nearest, "nst", 0) or 0,
# #             getattr(nearest, "gap", 0) or 0,
# #             getattr(nearest, "dmin", 0) or 0,
# #             getattr(nearest, "rms", 0) or 0,
# #             getattr(nearest, "horizontalError", 0) or 0,
# #             getattr(nearest, "depthError", 0) or 0,
# #             getattr(nearest, "magError", 0) or 0,
# #             getattr(nearest, "magNst", 0) or 0,
# #             lat_hist * lon_hist,
# #             lat_hist ** 2,
# #             lon_hist ** 2
# #         ]]

# #         ai_intensity = seismic_brain.predict(feature_vector)[0]
# #         ai_intensity = float(np.clip(ai_intensity, 1, 10))
        
# #         # 3. Calculate affected radius
# #         radius = get_radius_km(user_mag, nearest.depth)
        
# #         # 4. Determine risk level
# #         risk_level = get_risk_level(ai_intensity)
# #         damage_assessment = get_expected_damage(ai_intensity)
# #         confidence = min(100, max(0, 100 - (min_distance * 2)))

# #         # 5. NEW: Calculate distance to ALL hospitals and filter by radius
# #         affected_hospitals = []
# #         file_path = os.path.join(settings.BASE_DIR, "static/data/hospitals.geojson")
        
# #         if os.path.exists(file_path):
# #             with open(file_path, encoding="utf-8") as f:
# #                 hospitals_data = json.load(f)["features"]
            
# #             for h in hospitals_data:
# #                 if h.get("geometry"):
# #                     h_lng, h_lat = h["geometry"]["coordinates"]
# #                     props = h["properties"]
                    
# #                     # Haversine distance from EPICENTER to HOSPITAL
# #                     R = 6371
# #                     phi1, phi2 = math.radians(lat), math.radians(h_lat)
# #                     dphi = math.radians(h_lat - lat)
# #                     dlambda = math.radians(h_lng - lng)
# #                     a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
# #                     h_dist = 2 * R * math.asin(math.sqrt(a))
                    
# #                     # Only include if inside the calculated impact radius
# #                     if h_dist <= radius:
# #                         affected_hospitals.append({
# #                             "name": props.get("NAME", "Unknown"),
# #                             "lat": h_lat,
# #                             "lng": h_lng,
# #                             "distance": round(h_dist, 2),
# #                             "beds": props.get("BEDS", 0) if props.get("BEDS") != -999 else 0,
# #                             "type": props.get("TYPE", "Unknown"),
# #                             "status": props.get("STATUS", "Unknown"),
# #                             "telephone": props.get("TELEPHONE", "N/A")
# #                         })
            
# #             # Sort hospitals by closest to epicenter
# #             affected_hospitals.sort(key=lambda x: x["distance"])

# #         return JsonResponse({
# #             "place": nearest.place,
# #             "mag": user_mag,
# #             "radius": round(radius, 2),
# #             "intensity": ai_intensity,
# #             "risk_level": risk_level,
# #             "expected_damage": damage_assessment,
# #             "dist_from_click": round(min_distance, 2),
# #             "depth": float(nearest.depth) if nearest.depth else None,
# #             "confidence": confidence,
# #             "assessment": f"Earthquake of magnitude {user_mag} at depth {nearest.depth}km is predicted to cause {risk_level} damage potential.",
# #             "affected_hospitals": affected_hospitals,
# #             "total_beds_at_risk": sum(h['beds'] for h in affected_hospitals)
# #         })
# #     except Exception as e:
# #         return JsonResponse({"error": str(e)}, status=400)

# # def get_weather_proxy(request):
# #     lat = request.GET.get('lat')
# #     lng = request.GET.get('lng')
# #     api_key = '53719aca4723375a9e4d9dae1712951c'
# #     url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lng}&appid={api_key}&units=metric"
# #     try:
# #         response = requests.get(url, timeout=5)
# #         return JsonResponse(response.json())
# #     except Exception as e:
# #         return JsonResponse({'error': str(e)}, status=500)





# # # ================= 2. NEAREST HOSPITAL SEARCH =================
# # def nearest_hospital(request):
# #     """Reads hospitals.geojson and returns closest facilities via Haversine."""
# #     try:
# #         lat = float(request.GET.get("lat"))
# #         lng = float(request.GET.get("lng"))
        
# #         file_path = os.path.join(settings.BASE_DIR, "static/data/hospitals.geojson")
        
# #         with open(file_path, encoding="utf-8") as f:
# #             hospitals_data = json.load(f)["features"]
        
# #         hospital_list = []
# #         for h in hospitals_data:
# #             if h.get("geometry"):
# #                 h_lng, h_lat = h["geometry"]["coordinates"]
# #                 name = h["properties"].get("NAME") or "Emergency Facility"
                
# #                 # Haversine distance formula
# #                 R = 6371
# #                 phi1, phi2 = math.radians(lat), math.radians(h_lat)
# #                 dphi = math.radians(h_lat - lat)
# #                 dlambda = math.radians(h_lng - lng)
# #                 a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
# #                 dist = 2 * R * math.asin(math.sqrt(a))
                
# #                 hospital_list.append({
# #                     "name": name, "lat": h_lat, "lng": h_lng, "distance": round(dist, 2)
# #                 })
        
# #         hospital_list.sort(key=lambda x: x["distance"])
# #         return JsonResponse(hospital_list[:6], safe=False)
# #     except Exception as e:
# #         return JsonResponse({"error": str(e)}, status=400)

# # # ================= 3. SEISMIC MODEL & PREDICTION HELPERS =================
# # MODEL_PATH = r"G:\earthquake_today\earthquake_project\ml_models\earthquake_pipeline_model.pkl"
# # try:
# #     seismic_brain = joblib.load(MODEL_PATH)
# # except Exception as e:
# #     print(f"⚠️ Warning: Model not loaded. Error: {e}")
# #     seismic_brain = None

# # def get_risk_level(intensity):
# #     """Convert intensity score to risk level (high-level prediction)."""
# #     if intensity < 2:
# #         return "MINIMAL"
# #     elif intensity < 4:
# #         return "LOW"
# #     elif intensity < 5.5:
# #         return "MODERATE"
# #     elif intensity < 7:
# #         return "HIGH"
# #     else:
# #         return "CRITICAL"

# # def get_expected_damage(intensity):
# #     """Provide expected structural damage assessment."""
# #     damage_map = {
# #         "MINIMAL": "Negligible - Not felt; No structural impact",
# #         "LOW": "Light - Felt indoors; Minor non-structural damage",
# #         "MODERATE": "Moderate - Some plaster cracking; Possible structural concerns",
# #         "HIGH": "Heavy - Considerable damage; Structural damage likely",
# #         "CRITICAL": "Very Heavy - Extensive damage; Major structural failure expected"
# #     }
# #     return damage_map.get(get_risk_level(intensity), "Unknown")

# # def get_radius_km(magnitude, depth_km):
# #     """
# #     Calculate affected radius with depth consideration.
# #     Deeper quakes affect smaller area; shallow quakes affect larger area.
# #     """
# #     depth_factor = max(0.3, 1 - (depth_km / 250))  # Deeper = smaller radius
# #     base_radius = 10 ** (0.5 * magnitude - 1.2)
# #     return base_radius * depth_factor

# # def get_nearest_history(request):
# #     """
# #     Predict earthquake impact using ML model.
# #     Features: magnitude (from user input) + depth (from nearest historical earthquake)
# #     """
# #     try:
# #         lat = float(request.GET.get('lat'))
# #         lng = float(request.GET.get('lng'))
# #         user_mag = float(request.GET.get('mag', 6.0))

# #         # 1. Fetch all earthquakes and compute distances
# #         earthquakes = HistoricalEarthquake.objects.filter(
# #             latitude__isnull=False,
# #             longitude__isnull=False,
# #             depth__isnull=False
# #         )

# #         if not earthquakes.exists():
# #             return JsonResponse({"error": "No historical earthquake data available. Please load earthquake data first."}, status=404)

# #         # Find nearest earthquake
# #         nearest = None
# #         min_distance = float('inf')
        
# #         for eq in earthquakes:
# #             dist = eq.distance_to(lat, lng)
# #             if dist is not None and dist < min_distance:
# #                 min_distance = dist
# #                 nearest = eq

# #         if nearest is None:
# #             return JsonResponse({"error": "No historical earthquake data available."}, status=404)

# #         if seismic_brain is None:
# #             raise Exception("Model not loaded. Please train the model first.")
        
# #         # # 2. AI Inference: Predict intensity (damage potential)
# #         # # Using only mag and depth - the two features the model expects
# #         # ai_intensity = seismic_brain.predict([[user_mag, nearest.depth]])[0]
# #         # 2. AI Inference: Build full feature vector expected by XGBoost model

# #         # Basic geographic + seismic features from nearest historical record
# #         lat = nearest.latitude
# #         lon = nearest.longitude

# #         # Feature engineering (must match training)
# #         lat_lon_interaction = lat * lon
# #         lat_squared = lat ** 2
# #         lon_squared = lon ** 2

# #         # Some historical records may have null optional fields → default to 0
# #         feature_vector = [[
# #             user_mag,                     # mag (user simulated magnitude)
# #             lat,                           # latitude
# #             lon,                           # longitude
# #             getattr(nearest, "nst", 0) or 0,
# #             getattr(nearest, "gap", 0) or 0,
# #             getattr(nearest, "dmin", 0) or 0,
# #             getattr(nearest, "rms", 0) or 0,
# #             getattr(nearest, "horizontalError", 0) or 0,
# #             getattr(nearest, "depthError", 0) or 0,
# #             getattr(nearest, "magError", 0) or 0,
# #             getattr(nearest, "magNst", 0) or 0,
# #             lat_lon_interaction,
# #             lat_squared,
# #             lon_squared
# #         ]]

# #         ai_intensity = seismic_brain.predict(feature_vector)[0]

# #         # Ensure intensity is in valid range (1-10)
# #         ai_intensity = float(np.clip(ai_intensity, 1, 10))
        
# #         # 3. Calculate affected radius (depth-adjusted)
# #         radius = get_radius_km(user_mag, nearest.depth)
        
# #         # 4. Determine risk level (high-level prediction)
# #         risk_level = get_risk_level(ai_intensity)
# #         damage_assessment = get_expected_damage(ai_intensity)
        
# #         # 5. Calculate confidence based on historical data proximity
# #         confidence = max(0, 100 - (min_distance * 2))
# #         confidence = min(100, max(0, confidence))

# #         return JsonResponse({
# #             "place": nearest.place,
# #             "mag": user_mag,
# #             "radius": round(radius, 2),
# #             "intensity": ai_intensity,
# #             "risk_level": risk_level,
# #             "expected_damage": damage_assessment,
# #             "dist_from_click": round(min_distance, 2),
# #             "depth": float(nearest.depth) if nearest.depth  else None ,
# #             "confidence": confidence,
# #             "assessment": f"Earthquake of magnitude {user_mag} at depth {nearest.depth}km is predicted to cause {risk_level} damage potential."
# #         })
# #     except Exception as e:
# #         return JsonResponse({"error": str(e)}, status=400)

# # def get_weather_proxy(request):
# #     lat = request.GET.get('lat')
# #     lng = request.GET.get('lng')
    
# #     # Replace with your actual OpenWeatherMap API Key
# #     api_key = '53719aca4723375a9e4d9dae1712951c'
    
# #     url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lng}&appid={api_key}&units=metric"
    
# #     try:
# #         response = requests.get(url, timeout=5)
# #         data = response.json()
# #         return JsonResponse(data)
# #     except Exception as e:
# #         return JsonResponse({'error': str(e)}, status=500)

# # ================= 4. PDF REPORT GENERATOR (Updated) =================
# import base64
# import os
# from io import BytesIO

# from django.conf import settings
# from django.http import FileResponse
# from django.views.decorators.csrf import csrf_exempt

# # ReportLab Imports for PDF generation
# from reportlab.lib import colors
# from reportlab.platypus import Image as RLImage, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# @csrf_exempt
# def report(request):
#     """
#     Generates a Seismic Safety PDF report.
#     The Table is placed ABOVE the Map Image.
#     """
#     # 1. Capture Data from POST or GET
#     data = request.POST if request.method == "POST" else request.GET
    
#     place = data.get("place", "Simulated Area")
#     mag = data.get("mag", "0.0")
#     data_dist = float(data.get("dist_from_click", "0")) 
#     h_name = data.get("hname", "Emergency Facility")
#     travel_dist = data.get("dist", "0.0")
#     weather = data.get("weather", "Clear")
#     h_lat = data.get("hlat", "0")
#     h_lng = data.get("hlng", "0")
#     ai_intensity = data.get("intensity", "0.0")

#     # 2. Generate Google Maps Navigation Link
#     google_maps_url = f"https://www.google.com/maps/dir/?api=1&destination={h_lat},{h_lng}&travelmode=driving"
#     link_html = f'<a href="{google_maps_url}" color="blue"><u>Open Live GPS Navigation</u></a>'
    
#     # 3. PDF Document Setup
#     file_path = os.path.join(settings.BASE_DIR, "EQ_Safety_Report.pdf")
#     doc = SimpleDocTemplate(file_path, pagesize=A4)
#     styles = getSampleStyleSheet()
#     story = []

#     # --- PDF CONTENT: HEADER ---
#     story.append(Paragraph("EARTHQUAKE HAZARD ASSESSMENT REPORT", styles["Title"]))
#     story.append(Spacer(1, 10))
#     story.append(Paragraph(f"Generated on: 24/02/2026", styles["Normal"]))
#     story.append(Spacer(1, 20))

#     # --- 4. DATA TABLE (NOW AT THE TOP) ---
#     confidence_val = max(0, 100 - (data_dist * 2))
#     accuracy_rating = f"{int(confidence_val)}% (Moderate)"
#     if confidence_val > 80: accuracy_rating = f"{int(confidence_val)}% (High)"

#     table_data = [
#         ["ASSESSMENT PARAMETER", "VALUE / DETAILS"],
#         ["Target Region", place],
#         ["Simulated Magnitude", f"{mag} Mw"],
#         ["AI Intensity Rating", f"{ai_intensity}"],
#         ["Structural Risk", "HIGH" if float(ai_intensity) > 5.5 else "LOW/MODERATE"],
#         ["Designated Hospital", h_name],
#         ["Route Distance", f"{travel_dist} km"],
#         ["Current Weather", weather],
#         ["Model Confidence", accuracy_rating],
#         ["Navigation Link", Paragraph(link_html, styles["Normal"])] 
#     ]

#     report_table = Table(table_data, colWidths=[180, 270])
#     report_table.setStyle(TableStyle([
#         ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
#         ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
#         ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
#         ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
#         ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
#         ('GRID', (0, 0), (-1, -1), 1, colors.grey),
#         ('TEXTCOLOR', (1, 4), (1, 4), colors.red if float(ai_intensity) > 5.5 else colors.green),
#     ]))
    
#     story.append(report_table)
#     story.append(Spacer(1, 25)) # Space between Table and Image

#     # --- 5. MAP IMAGE (NOW AT THE BOTTOM) ---
#     map_image_data = data.get("map_image") 
#     if map_image_data and ";base64," in map_image_data:
#         try:
#             format, imgstr = map_image_data.split(';base64,') 
#             img_data = base64.b64decode(imgstr)
#             map_img = RLImage(BytesIO(img_data), width=480, height=300)
            
#             story.append(Paragraph("<b>Spatial Analysis Snapshot (Routes & Heatmap):</b>", styles["Heading3"]))
#             story.append(Spacer(1, 8))
#             story.append(map_img) 
#         except Exception as e:
#             story.append(Paragraph(f"<i>(Visual context snapshot unavailable: {e})</i>", styles["Normal"]))

#     # Final Step: Build the PDF
#     doc.build(story)
    
#     return FileResponse(
#         open(file_path, "rb"), 
#         as_attachment=True, 
#         filename=f"Seismic_Safety_Report_{place[:15]}.pdf"
#     )
