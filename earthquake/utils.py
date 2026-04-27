# # import numpy as np

# # def haversine(lat1, lon1, lat2, lon2):
# #     """Calculate the great circle distance in kilometers between two points on the Earth."""
# #     R = 6371  # Earth radius in km

# #     lat1, lon1, lat2, lon2 = map(np.radians,
# #         [lat1, lon1, lat2, lon2])

# #     dlat = lat2 - lat1
# #     dlon = lon2 - lon1

# #     a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2

# #     c = 2 * np.arcsin(np.sqrt(a))

# #     return R * c


# now my code is this :

# views.py : import requests
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
#     """Renders the main map interface."""
#     return render(request, "index.html")

# # ================= 2. NEAREST HOSPITAL SEARCH =================
# def nearest_hospital(request):
#     """Reads hospitals.geojson and returns closest facilities via Haversine."""
#     try:
#         lat = float(request.GET.get("lat"))
#         lng = float(request.GET.get("lng"))
#         
#         file_path = os.path.join(settings.BASE_DIR, "static/data/hospitals.geojson")
#         
#         with open(file_path, encoding="utf-8") as f:
#             hospitals_data = json.load(f)["features"]
#         
#         hospital_list = []
#         for h in hospitals_data:
#             if h.get("geometry"):
#                 h_lng, h_lat = h["geometry"]["coordinates"]
#                 name = h["properties"].get("NAME") or "Emergency Facility"
#                 
#                 # Haversine distance formula
#                 R = 6371
#                 phi1, phi2 = math.radians(lat), math.radians(h_lat)
#                 dphi = math.radians(h_lat - lat)
#                 dlambda = math.radians(h_lng - lng)
#                 a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
#                 dist = 2 * R * math.asin(math.sqrt(a))
#                 
#                 hospital_list.append({
#                     "name": name, "lat": h_lat, "lng": h_lng, "distance": round(dist, 2)
#                 })
#         
#         hospital_list.sort(key=lambda x: x["distance"])
#         return JsonResponse(hospital_list[:6], safe=False)
#     except Exception as e:
#         return JsonResponse({"error": str(e)}, status=400)

# # ================= 3. SEISMIC MODEL & PREDICTION HELPERS =================
# MODEL_PATH = r"G:\earthquake_today\earthquake_project\ml_models\earthquake_pipeline_model.pkl"
# try:
#     seismic_brain = joblib.load(MODEL_PATH)
# except Exception as e:
#     print(f"⚠️ Warning: Model not loaded. Error: {e}")
#     seismic_brain = None

# def get_risk_level(intensity):
#     """Convert intensity score to risk level (high-level prediction)."""
#     if intensity < 2: return "MINIMAL"
#     elif intensity < 4: return "LOW"
#     elif intensity < 5.5: return "MODERATE"
#     elif intensity < 7: return "HIGH"
#     else: return "CRITICAL"

# def get_expected_damage(intensity):
#     """Provide expected structural damage assessment."""
#     damage_map = {
#         "MINIMAL": "Negligible - Not felt; No structural impact",
#         "LOW": "Light - Felt indoors; Minor non-structural damage",
#         "MODERATE": "Moderate - Some plaster cracking; Possible structural concerns",
#         "HIGH": "Heavy - Considerable damage; Structural damage likely",
#         "CRITICAL": "Very Heavy - Extensive damage; Major structural failure expected"
#     }
#     return damage_map.get(get_risk_level(intensity), "Unknown")

# def get_radius_km(magnitude, depth_km):
#     """
#     Calculate affected radius with depth consideration.
#     Deeper quakes affect smaller area; shallow quakes affect larger area.
#     """
#     depth_factor = max(0.3, 1 - (depth_km / 250))  # Deeper = smaller radius
#     base_radius = 10 ** (0.4 * magnitude - 1)  # Adjusted slightly to match UI visual radius
#     return base_radius * depth_factor

# def get_nearest_history(request):
#     """
#     Predict earthquake depth using ML model AND calculates affected hospitals
#     distance from the simulated epicenter within the danger radius.
#     """
#     try:
#         lat = float(request.GET.get('lat'))
#         lng = float(request.GET.get('lng'))
#         user_mag = float(request.GET.get('mag', 6.0))

#         # 1. Fetch all earthquakes and compute distances
#         earthquakes = HistoricalEarthquake.objects.filter(
#             latitude__isnull=False,
#             longitude__isnull=False,
#             depth__isnull=False
#         )

#         if not earthquakes.exists():
#             return JsonResponse({"error": "No historical earthquake data available."}, status=404)

#         nearest = None
#         min_distance = float('inf')
#         for eq in earthquakes:
#             dist = eq.distance_to(lat, lng)
#             if dist is not None and dist < min_distance:
#                 min_distance = dist
#                 nearest = eq

#         if nearest is None:
#             return JsonResponse({"error": "No historical earthquake data available."}, status=404)

#         if seismic_brain is None:
#             raise Exception("Model not loaded. Please train the model first.")
#         
#         # 2. AI Inference: Predict DEPTH based on the nearest historical profile
#         lat_hist = nearest.latitude
#         lon_hist = nearest.longitude

#         feature_vector = [[
#             user_mag, lat_hist, lon_hist,
#             getattr(nearest, "nst", 0) or 0,
#             getattr(nearest, "gap", 0) or 0,
#             getattr(nearest, "dmin", 0) or 0,
#             getattr(nearest, "rms", 0) or 0,
#             getattr(nearest, "horizontal_error", 0) or 0,
#             getattr(nearest, "depth_error", 0) or 0,
#             getattr(nearest, "mag_error", 0) or 0,
#             getattr(nearest, "mag_nst", 0) or 0,
#             lat_hist * lon_hist,
#             lat_hist ** 2,
#             lon_hist ** 2
#         ]]

#         # MODEL PREDICTS LOG_DEPTH -> Convert back to real depth via expm1
#         log_depth_pred = seismic_brain.predict(feature_vector)[0]
#         predicted_depth = np.expm1(log_depth_pred)

#         # Calculate intensity based on magnitude and PREDICTED depth
#         depth_penalty = predicted_depth / 50.0
#         ai_intensity = float(np.clip((user_mag * 1.3) - depth_penalty, 1, 10))
#         
#         # 3. Calculate affected radius using PREDICTED DEPTH
#         radius = get_radius_km(user_mag, predicted_depth)
#         
#         # 4. Determine risk level
#         risk_level = get_risk_level(ai_intensity)
#         damage_assessment = get_expected_damage(ai_intensity)
#         
#         # --- ✨ DATA SCIENCE CONFIDENCE ENGINE ✨ ---
#         # Start at 100% and apply strict data science penalties.

#         # 1. Telemetry Quality Penalty (Max 40 points lost)
#         # Assumes 'nearest' is the closest HistoricalEarthquake object matched in your view
#         nst = float(getattr(nearest, "nst", 20) or 20)
#         gap = float(getattr(nearest, "gap", 90) or 90)
#         rms = float(getattr(nearest, "rms", 0.5) or 0.5)

#         nst_penalty = min(20.0, max(0.0, (50.0 - nst) * 0.4))    # Penalty if under 50 stations
#         gap_penalty = min(10.0, max(0.0, (gap - 90.0) * 0.1))    # Penalty if gap is over 90 degrees
#         rms_penalty = min(10.0, max(0.0, (rms - 0.5) * 10.0))    # Penalty if high RMS error
#         telemetry_penalty = nst_penalty + gap_penalty + rms_penalty

#         # 2. Geographic Familiarity Penalty (Max 30 points lost)
#         # 'min_distance' is the distance to the nearest known historical quake
#         geo_penalty = min(30.0, max(0.0, (min_distance - 50.0) * 0.1))

#         # 3. Statistical Anomaly Penalty (Max 30 points lost)
#         # High magnitudes and extreme depths are rare, meaning less training data exists.
#         mag_penalty = min(15.0, max(0.0, (user_mag - 6.5) * 5.0))
#         depth_penalty_conf = min(15.0, max(0.0, (predicted_depth - 30.0) * 0.1))
#         anomaly_penalty = mag_penalty + depth_penalty_conf

#         # Final Perfect Confidence Score
#         raw_confidence = 100.0 - telemetry_penalty - geo_penalty - anomaly_penalty
#         confidence = float(max(15.0, min(99.5, raw_confidence))) # Cap safely between 15% and 99.5%
#         # ------------------------------------------

#         # 5. EXACT DISTANCE CALCULATION: Distance to ALL hospitals and filter by radius
#         affected_hospitals = []
#         file_path = os.path.join(settings.BASE_DIR, "static/data/hospitals.geojson")
#         
#         if os.path.exists(file_path):
#             with open(file_path, encoding="utf-8") as f:
#                 hospitals_data = json.load(f)["features"]
#             
#             for h in hospitals_data:
#                 if h.get("geometry"):
#                     h_lng, h_lat = h["geometry"]["coordinates"]
#                     props = h["properties"]
#                     
#                     # Haversine distance from simulated EPICENTER to HOSPITAL
#                     R = 6371
#                     phi1, phi2 = math.radians(lat), math.radians(h_lat)
#                     dphi = math.radians(h_lat - lat)
#                     dlambda = math.radians(h_lng - lng)
#                     a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
#                     h_dist = 2 * R * math.asin(math.sqrt(a))
#                     
#                     # Only include if inside the calculated impact radius
#                     if h_dist <= radius:
#                         affected_hospitals.append({
#                             "name": props.get("NAME", "Unknown"),
#                             "lat": h_lat,
#                             "lng": h_lng,
#                             "distance": round(h_dist, 2), # ACCURATE DISTANCE
#                             "beds": props.get("BEDS", 0) if props.get("BEDS") != -999 else 0,
#                             "type": props.get("TYPE", "Unknown"),
#                             "status": props.get("STATUS", "Unknown"),
#                             "telephone": props.get("TELEPHONE", "N/A")
#                         })
#             
#             # Sort hospitals by closest to epicenter
#             affected_hospitals.sort(key=lambda x: x["distance"])

#         return JsonResponse({
#             "place": nearest.place,
#             "mag": user_mag,
#             "radius": round(radius, 2),
#             "intensity": ai_intensity,
#             "risk_level": risk_level,
#             "expected_damage": damage_assessment,
#             "dist_from_click": round(min_distance, 2),
#             "depth": float(predicted_depth), # RETURN AI PREDICTED DEPTH
#             "confidence": confidence,
#             "assessment": f"Earthquake of magnitude {user_mag} at predicted depth {predicted_depth:.1f}km is expected to cause {risk_level} damage.",
#             "affected_hospitals": affected_hospitals,
#             "total_beds_at_risk": sum(h['beds'] for h in affected_hospitals)
#         })
#     except Exception as e:
#         return JsonResponse({"error": str(e)}, status=400)

# def get_weather_proxy(request):
#     lat = request.GET.get('lat')
#     lng = request.GET.get('lng')
#     api_key = 'your api key'
#     url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lng}&appid={api_key}&units=metric"
#     try:
#         response = requests.get(url, timeout=5)
#         return JsonResponse(response.json())
#     except Exception as e:
#         return JsonResponse({'error': str(e)}, status=500)

# # ================= 4. PDF REPORT GENERATOR =================
# @csrf_exempt
# def report(request):
#     """
#     Generates a Seismic Safety PDF report.
#     The Table is placed ABOVE the Map Image.
#     """
#     # 1. Capture Data from POST or GET
#     data = request.POST if request.method == "POST" else request.GET
#     
#     place = data.get("place", "Simulated Area")
#     mag = data.get("mag", "0.0")
#     data_dist = float(data.get("dist_from_click", "0")) 
#     h_name = data.get("hname", "Emergency Facility")
#     travel_dist = data.get("dist", "0.0")
#     weather = data.get("weather", "Clear")
#     h_lat = data.get("hlat", "0")
#     h_lng = data.get("hlng", "0")
#     ai_intensity = data.get("intensity", "0.0")
#     depth = data.get("depth", "0.0")
#     confidence_val = data.get("confidence", "0%") # ✅ CAPTURE CONFIDENCE FROM JS

#     # 2. Generate Google Maps Navigation Link
#     google_maps_url = f"https://www.google.com/maps/dir/?api=1&destination={h_lat},{h_lng}&travelmode=driving"
#     link_html = f'<a href="{google_maps_url}" color="blue"><u>Open Live GPS Navigation</u></a>'
#     
#     # 3. PDF Document Setup
#     file_path = os.path.join(settings.BASE_DIR, "EQ_Safety_Report.pdf")
#     doc = SimpleDocTemplate(file_path, pagesize=A4)
#     styles = getSampleStyleSheet()
#     story = []

#     # --- PDF CONTENT: HEADER ---
#     story.append(Paragraph("EARTHQUAKE HAZARD ASSESSMENT REPORT", styles["Title"]))
#     story.append(Spacer(1, 10))
#     current_date = datetime.now().strftime("%d/%m/%Y")
#     story.append(Paragraph(f"Generated on: {current_date}", styles["Normal"]))
#     story.append(Spacer(1, 20))

#     # --- 4. DATA TABLE (NOW AT THE TOP) ---
#     
#     # ✅ SAFE EXTRACTION & FORMATTING LOGIC
#     if not confidence_val:
#         # Fallback only if JS fails to send it
#         confidence_val = f"{max(0, 100 - (data_dist * 2))}%"
#     
#     # Clean the string safely (removes % sign so we can do math)
#     try:
#         clean_conf = float(str(confidence_val).replace('%', '').strip())
#     except ValueError:
#         clean_conf = 0.0

#     accuracy_rating = f"{confidence_val} (High)" if clean_conf > 80 else f"{confidence_val} (Moderate/Low)"
#     table_data = [
#         ["ASSESSMENT PARAMETER", "VALUE / DETAILS"],
#         ["Target Region", place],
#         ["Simulated Magnitude", f"{mag} Mw"],
#         ["AI Predicted Depth", f"{depth} km"],
#         ["AI Intensity Rating", f"{ai_intensity}"],
#         ["Structural Risk", "HIGH" if float(ai_intensity) > 5.5 else "LOW/MODERATE"],
#         ["Designated Hospital", h_name],
#         ["Route Distance", f"{travel_dist} km"],
#         ["Current Weather", weather],
#         ["Model Confidence", accuracy_rating],
#         ["Navigation Link", Paragraph(link_html, styles["Normal"])] 
#     ]

#     report_table = Table(table_data, colWidths=[180, 270])
#     report_table.setStyle(TableStyle([
#         ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
#         ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
#         ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
#         ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
#         ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
#         ('GRID', (0, 0), (-1, -1), 1, colors.grey),
#         ('TEXTCOLOR', (1, 5), (1, 5), colors.red if float(ai_intensity) > 5.5 else colors.green),
#     ]))
#     
#     story.append(report_table)
#     story.append(Spacer(1, 25)) # Space between Table and Image

#     # --- 5. MAP IMAGE (NOW AT THE BOTTOM) ---
#     map_image_data = data.get("map_image") 
#     if map_image_data and ";base64," in map_image_data:
#         try:
#             format, imgstr = map_image_data.split(';base64,') 
#             img_data = base64.b64decode(imgstr)
#             map_img = RLImage(BytesIO(img_data), width=480, height=300)
#             
#             story.append(Paragraph("<b>Spatial Analysis Snapshot (Routes & Heatmap):</b>", styles["Heading3"]))
#             story.append(Spacer(1, 8))
#             story.append(map_img) 
#         except Exception as e:
#             story.append(Paragraph(f"<i>(Visual context snapshot unavailable: {e})</i>", styles["Normal"]))

#     # Final Step: Build the PDF
#     doc.build(story)
#     
#     return FileResponse(
#         open(file_path, "rb"), 
#         as_attachment=True, 
#         filename=f"Seismic_Safety_Report_{place[:15]}.pdf"
#     )


# urls.py : # earthquake/urls.py
# from django.urls import path
# from . import views

# urlpatterns = [
#     path('', views.index, name='index'),
#     path('nearest_hospital/', views.nearest_hospital, name='nearest_hospital'),
#     
#     # Matches JS: fetch(`/get_nearest_history/?lat=...`)
#     path('get_nearest_history/', views.get_nearest_history, name='get_nearest_history'),
#     
#     # Matches JS: form.action = '/report/';
#     path('report/', views.report, name='report'), 
#     
#     # 🚨 FIX: Changed to match JS fetch(`/get_weather_proxy/?lat=...`)
#     path('get_weather_proxy/', views.get_weather_proxy, name='weather_proxy'),
# ]

# templates folder index.html code: <!DOCTYPE html>
# <html lang="en">
# <head>
#     <meta charset="UTF-8">
#     <meta name="viewport" content="width=device-width, initial-scale=1.0">
#     <title>Hospital Command Center</title>
#     
#     <!-- CDNs -->
#     <script src="https://cdn.tailwindcss.com"></script>
#     <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
#     <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" />
#     
#     <!-- Routing & Image Generation CDNs (No Heatmap) -->
#     <link rel="stylesheet" href="https://unpkg.com/leaflet-routing-machine/dist/leaflet-routing-machine.css" />
#     <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
#     <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
#     <script src="https://unpkg.com/leaflet-routing-machine/dist/leaflet-routing-machine.js"></script>
#     <script src="https://unpkg.com/leaflet-image@0.4.0/leaflet-image.js"></script>

#     <style>
#         /* CSS Variables for Dynamic Color Theme */
#         :root { --dynamic-color: #22c55e; }

#         /* Custom UI Enhancements & Animations */
#         body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #05080f; color: #f1f5f9; }
#         .custom-scrollbar::-webkit-scrollbar { width: 4px; }
#         .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
#         .custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 10px; }
#         
#         /* Map Styles */
#         .leaflet-container { background: #05080f !important; }
#         .leaflet-control-zoom { border: none !important; margin: 40px !important; margin-bottom: 16px !important; z-index: 30 !important; }
#         .leaflet-control-zoom-in, .leaflet-control-zoom-out { background: rgba(11, 16, 26, 0.9) !important; color: white !important; border: 1px solid rgba(255,255,255,0.1) !important; backdrop-filter: blur(10px); border-radius: 12px !important; width: 44px !important; height: 44px !important; line-height: 44px !important; margin-bottom: 8px !important; box-shadow: 0 15px 30px rgba(0,0,0,0.5) !important; font-weight: 900 !important; font-size: 18px !important; }
#         .leaflet-tooltip { background: #0b101a !important; color: white !important; border: 1px solid rgba(255,255,255,0.1) !important; border-radius: 8px !important; font-size: 10px !important; font-weight: 800 !important; box-shadow: 0 10px 20px rgba(0,0,0,0.5) !important; padding: 6px 10px !important; pointer-events: none; }
#         
#         /* Hide Default Routing Box */
#         .leaflet-routing-container { display: none !important; }

#         /* CRT Scanlines */
#         .scanlines {
#             background: linear-gradient(to bottom, rgba(255,255,255,0), rgba(255,255,255,0) 50%, rgba(0,0,0,0.2) 50%, rgba(0,0,0,0.2));
#             background-size: 100% 4px;
#         }

#         /* Shockwave Animations tied to Dynamic Color */
#         .shockwave-container { position: relative; width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; }
#         .sw-core { width: 12px; height: 12px; background: var(--dynamic-color); border-radius: 50%; box-shadow: 0 0 15px var(--dynamic-color); z-index: 10; transition: background 0.3s, box-shadow 0.3s; }
#         .sw-ring { position: absolute; width: 100%; height: 100%; border-radius: 50%; border: 2px solid var(--dynamic-color); opacity: 0; animation: ripple 3s linear infinite; transition: border-color 0.3s; }
#         .sw-delay-1 { animation-delay: 0s; } .sw-delay-2 { animation-delay: 1s; } .sw-delay-3 { animation-delay: 2s; }
#         @keyframes ripple { 0% { transform: scale(0.2); opacity: 1; border-width: 4px; } 100% { transform: scale(5); opacity: 0; border-width: 0px; } }
#         
#         .impact-circle-anim { animation: pulse-opacity 3s ease-in-out infinite alternate; }
#         @keyframes pulse-opacity { 0% { fill-opacity: 0.1; } 100% { fill-opacity: 0.25; } }

#         /* Range Slider Styling */
#         .range-slider { appearance: none; }
#         .range-slider::-webkit-slider-thumb {
#             appearance: none; width: 24px; height: 24px; border-radius: 50%;
#             background: var(--dynamic-color); cursor: pointer; border: 4px solid #121824;
#             box-shadow: 0 0 15px var(--dynamic-color); transition: 0.2s;
#         }
#         .range-slider::-webkit-slider-thumb:hover { transform: scale(1.2); }

#         /* Theme utility classes */
#         .theme-text { color: var(--dynamic-color); transition: color 0.3s ease; }
#         .theme-bg { background-color: var(--dynamic-color); transition: background-color 0.3s ease; }
#         .theme-border { border-color: var(--dynamic-color); transition: border-color 0.3s ease; }
#         .theme-gradient { background-image: linear-gradient(to bottom right, var(--dynamic-color), rgba(0,0,0,0.5)); transition: background-image 0.3s ease;}
#         
#         /* Safe Hospital Custom Marker */
#         .safe-hospital-marker { background:#27ae60; color:white; border-radius:50%; width:24px; height:24px; text-align:center; line-height:22px; font-weight:bold; border:2px solid white; box-shadow: 0 0 10px rgba(39,174,96,0.8); cursor: pointer;}
#     </style>
# </head>
# <body class="flex w-full h-screen overflow-hidden selection:bg-blue-500/30">

#     <!-- LEFT COMMAND PANEL -->
#     <div id="ui-theme-container" class="w-[420px] min-w-[420px] bg-[#0b101a]/95 border-r border-white/10 flex flex-col z-20 shadow-[0_0_50px_rgba(0,0,0,0.5)] backdrop-blur-2xl relative text-orange-500">
#         
#         <!-- Header -->
#         <div class="relative overflow-hidden p-7 bg-gradient-to-b from-white/5 to-transparent border-b border-white/5">
#             <div class="flex items-center gap-4">
#                 <div class="p-3 rounded-xl border border-white/10 shadow-[0_0_20px_rgba(0,0,0,0.3)] theme-gradient">
#                     <i class="fa-solid fa-radar text-white text-xl animate-[spin_4s_linear_infinite]"></i>
#                 </div>
#                 <div>
#                     <h1 class="text-xl font-black text-white tracking-tight leading-none uppercase drop-shadow-md">Tactical Command</h1>
#                     <p class="text-[10px] font-black uppercase tracking-[0.3em] mt-1 theme-text">Disaster Response Grid</p>
#                 </div>
#             </div>
#         </div>

#         <!-- Tab Selection -->
#         <div class="flex px-7 pt-4 gap-4">
#             <button id="tab-sim" class="flex-1 py-3 text-[10px] font-black uppercase tracking-widest border-b-2 theme-border text-white drop-shadow-[0_0_8px_rgba(255,255,255,0.5)] transition-all duration-300" onclick="window.switchTab('simulation')">Telemetry</button>
#             <button id="tab-ana" class="flex-1 py-3 text-[10px] font-black uppercase tracking-widest border-b-2 border-transparent text-slate-600 hover:text-slate-400 transition-all duration-300" onclick="window.switchTab('analytics')">Analytics</button>
#         </div>

#         <div class="flex-1 overflow-y-auto custom-scrollbar p-7 space-y-6">
#             
#             <!-- SIMULATION TAB -->
#             <div id="content-sim" class="space-y-6 transition-opacity duration-500">
#                 <!-- Controls -->
#                 <div class="bg-[#121824] p-6 rounded-2xl border border-white/5 shadow-inner relative overflow-hidden group">
#                     <div class="absolute top-0 left-0 w-1 h-full theme-bg"></div>
#                     
#                     <div class="flex justify-between items-center mb-4">
#                         <label class="text-[10px] font-black uppercase text-slate-400 tracking-[0.2em] flex items-center gap-2">
#                             <i class="fa-solid fa-wave-square theme-text"></i> Seismic Magnitude
#                         </label>
#                         <span class="text-2xl font-black theme-text drop-shadow-lg"><span id="mag-display">6.50</span> <small class="text-[10px] text-slate-500">Mw</small></span>
#                     </div>
#                     
#                     <input type="range" id="mag-slider" min="0.025" max="10" step="0.025" value="6.5" class="w-full h-1.5 bg-slate-800 rounded-lg cursor-pointer range-slider">

#                     <!-- Predicted Depth Grid Column -->
#                     <div class="grid grid-cols-3 gap-2 mt-6">
#                         <div class="bg-[#0b101a] p-3 rounded-xl border border-white/5 flex flex-col justify-center">
#                             <span class="text-[8px] text-slate-500 font-bold uppercase tracking-widest mb-1">Zone</span>
#                             <span class="text-sm font-black text-white"><span id="stat-radius">0</span> KM</span>
#                         </div>
#                         <div class="bg-[#0b101a] p-3 rounded-xl border border-white/5 flex flex-col justify-center">
#                             <span class="text-[8px] text-slate-500 font-bold uppercase tracking-widest mb-1">Depth (AI)</span>
#                             <span class="text-sm font-black text-blue-400"><span id="stat-depth">0</span> KM</span>
#                         </div>
#                         <div class="bg-[#0b101a] p-3 rounded-xl border border-white/5 flex flex-col justify-center">
#                             <span class="text-[8px] text-slate-500 font-bold uppercase tracking-widest mb-1">Sites</span>
#                             <span class="text-sm font-black theme-text" id="stat-sites">0</span>
#                         </div>
#                     </div>

#                     <button id="btn-analyze" onclick="window.runAnalysis()" class="w-full mt-5 py-4 rounded-xl font-black text-[11px] uppercase tracking-widest transition-all shadow-xl active:scale-95 theme-gradient text-white flex items-center justify-center gap-2">
#                         <i class="fa-solid fa-bolt"></i> <span id="btn-analyze-text">Engage Server Analysis</span>
#                     </button>
#                 </div>

#                 <!-- AI Report Container -->
#                 <div id="ai-report-container" class="hidden space-y-4">
#                     <div class="flex gap-4">
#                         <div class="flex-1 theme-gradient p-4 rounded-2xl shadow-lg border border-white/20 flex flex-col justify-between">
#                             <span class="text-[9px] font-black uppercase tracking-widest text-white/70">Threat Index</span>
#                             <div class="text-3xl font-black text-white drop-shadow-md mt-1" id="rep-intensity">0.0</div>
#                         </div>
#                         <div class="flex-[2] bg-[#121824] p-4 rounded-2xl border border-white/5 flex flex-col justify-center">
#                             <span class="text-[9px] font-black uppercase tracking-widest text-slate-500 mb-1">Classification</span>
#                             <span class="text-lg font-black uppercase theme-text" id="rep-risk">UNKNOWN</span>
#                         </div>
#                     </div>

#                     <div class="bg-[#121824] p-5 rounded-2xl border border-white/5 space-y-5 relative">
#                         <div>
#                             <h4 class="text-[9px] font-black uppercase tracking-widest text-slate-500 mb-2 flex items-center gap-1.5"><i class="fa-solid fa-bullseye text-blue-500"></i> Structural Assessment</h4>
#                             <p class="text-xs text-slate-200 font-medium bg-black/30 p-3 rounded-lg border border-white/5" id="rep-damage">No data.</p>
#                         </div>
#                         <div>
#                             <h4 class="text-[9px] font-black uppercase tracking-widest text-slate-500 mb-2 flex items-center gap-1.5"><i class="fa-solid fa-server text-purple-500"></i> Backend Synthesis</h4>
#                             <p class="text-xs text-slate-400 italic leading-relaxed" id="rep-assessment">Awaiting generation...</p>
#                         </div>

#                         <!-- Model Confidence Bar -->
#                         <div class="pt-4 border-t border-white/5 mt-4">
#                             <div style="display: flex; justify-content: space-between; font-size: 10px;" class="text-slate-400 uppercase font-black tracking-widest mb-1">
#                                 <span>Model Confidence</span>
#                                 <b id="accuracy-text" class="text-white">0%</b>
#                             </div>
#                             <div class="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
#                                 <div id="accuracy-bar" class="h-full bg-green-500 transition-all duration-1000 w-0"></div>
#                             </div>
#                         </div>
#                     </div>
#                 </div>

#                 <!-- Placeholder -->
#                 <div id="ai-placeholder" class="p-8 border border-dashed border-white/10 rounded-3xl flex flex-col items-center justify-center text-center opacity-40 grayscale select-none mt-8">
#                     <i class="fa-solid fa-crosshairs text-4xl mb-4 animate-[pulse_3s_ease-in-out_infinite]"></i>
#                     <p class="text-[10px] font-black uppercase tracking-[0.3em] text-white">Awaiting Target</p>
#                     <p class="text-[9px] mt-2 max-w-[200px] text-slate-400">Click coordinates on the satellite grid to initialize impact simulation.</p>
#                 </div>
#             </div>

#             <!-- ANALYTICS TAB -->
#             <div id="content-ana" class="hidden space-y-6 transition-opacity duration-500">
#                 <div class="bg-[#121824] p-6 rounded-2xl border border-white/5 shadow-lg">
#                     <h3 class="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-6 flex items-center gap-2">
#                         <i class="fa-solid fa-chart-pie theme-text"></i> Infrastructure Breakdown
#                     </h3>
#                     <div class="h-48 w-full relative">
#                         <canvas id="pieChart"></canvas>
#                     </div>
#                 </div>
#                 <div class="bg-[#121824] p-6 rounded-2xl border border-white/5 shadow-lg">
#                     <h3 class="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-6 flex items-center gap-2">
#                         <i class="fa-solid fa-chart-simple theme-text"></i> Bed Capacity Stress
#                     </h3>
#                     <div class="h-48 w-full relative">
#                         <canvas id="barChart"></canvas>
#                     </div>
#                 </div>
#             </div>
#         </div>

#         <!-- Footer Upload -->
#         <div class="p-6 border-t border-white/5 bg-[#0b101a] relative z-10">
#             <label class="flex items-center justify-center gap-3 w-full bg-[#121824] hover:bg-[#1a2233] text-white py-4 rounded-xl cursor-pointer transition-all text-[10px] font-black uppercase tracking-widest border border-white/10 active:scale-95 shadow-lg group" onclick="document.getElementById('geo-up').click()">
#                 <i class="fa-solid fa-upload text-blue-400 group-hover:-translate-y-1 transition-transform"></i>
#                 <span id="upload-text">Load Local GeoJSON</span>
#             </label>
#             <input type="file" id="geo-up" class="hidden" accept=".geojson" onchange="window.handleFileUpload(event)">
#         </div>
#     </div>

#     <!-- CENTER MAP VIEW -->
#     <div class="flex-1 relative bg-[#05080f]">
#         <!-- Effects -->
#         <div class="absolute inset-0 z-10 pointer-events-none scanlines opacity-30"></div>
#         <div class="absolute inset-0 z-10 pointer-events-none bg-blue-500/5 mix-blend-overlay"></div>

#         <div id="map" class="absolute inset-0 z-0" style="cursor: crosshair;"></div>
#         
#         <!-- Map Style Toggle Button -->
#         <button id="map-toggle-btn" onclick="window.toggleMapStyle()" class="absolute top-8 right-8 z-[1000] bg-[#1A1D23]/90 backdrop-blur-md border border-white/10 text-white p-4 rounded-xl shadow-2xl hover:bg-white/10 transition-colors" title="Switch to Street View">
#             <i class="fa-solid fa-map"></i>
#         </button>
#         
#         <!-- HUD -->
#         <div class="absolute top-8 left-8 right-[100px] z-20 flex justify-between items-start pointer-events-none">
#             <div class="bg-[#0b101a]/80 backdrop-blur-xl px-5 py-3 rounded-2xl border border-white/10 shadow-2xl flex items-center gap-3">
#                 <div class="w-2 h-2 rounded-full bg-blue-500 animate-pulse ring-4 ring-blue-500/20"></div>
#                 <p class="text-[10px] font-black uppercase tracking-[0.2em] text-blue-100">SAT-LINK: SECURE</p>
#             </div>
#             <div class="bg-[#0b101a]/80 backdrop-blur-xl px-5 py-3 rounded-2xl border border-white/10 text-white font-mono text-[11px] font-bold shadow-2xl flex items-center gap-2">
#                 <i class="fa-solid fa-satellite-dish text-slate-400"></i>
#                 LAT: <span id="hud-lat">---.----</span> <span class="text-slate-600 px-1">/</span> LNG: <span id="hud-lng">---.----</span>
#             </div>
#         </div>

#         <!-- ROUTING PANEL -->
#         <div id="routing-panel" class="hidden absolute top-28 right-8 w-[380px] z-[1000] bg-[#1A1D23]/95 backdrop-blur-2xl border border-[#2D333B] rounded-2xl shadow-2xl p-5 max-h-[60vh] overflow-y-auto custom-scrollbar">
#             <!-- Dynamically populated by JS -->
#         </div>

#         <!-- HOSPITAL DETAIL CARD -->
#         <div id="hospital-detail-card" class="hidden absolute bottom-24 right-8 w-[350px] z-[1000] bg-[#1A1D23]/95 backdrop-blur-2xl border border-[#2D333B] rounded-[32px] shadow-2xl p-8 transition-opacity duration-300">
#             <button onclick="window.closeHospitalCard()" class="absolute top-6 right-6 text-slate-500 hover:text-white transition-colors p-2 hover:bg-white/10 rounded-full">
#                 <i class="fa-solid fa-xmark"></i>
#             </button>
#             <h2 id="hosp-name" class="text-xl font-black text-white leading-tight pr-8 mb-1 tracking-tight">Facility Name</h2>
#             <p id="hosp-address" class="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-6 leading-relaxed">Address</p>
#             
#             <div class="grid grid-cols-2 gap-4 border-t border-[#2D333B] pt-6 mb-4">
#                 <div class="space-y-1">
#                     <p class="text-[9px] font-black text-slate-600 uppercase tracking-widest flex items-center gap-1.5"><i class="fa-solid fa-bed text-blue-500"></i> Beds</p>
#                     <p id="hosp-beds" class="text-base font-black text-white">0</p>
#                 </div>
#                 <div class="space-y-1">
#                     <p class="text-[9px] font-black text-slate-600 uppercase tracking-widest flex items-center gap-1.5"><i class="fa-solid fa-heart-pulse text-green-500"></i> Status</p>
#                     <p id="hosp-status" class="text-base font-black text-green-500 uppercase">UNKNOWN</p>
#                 </div>
#             </div>

#             <!-- Expanded details panel -->
#             <div class="space-y-2 border-t border-[#2D333B] pt-4">
#                 <div class="flex items-center justify-between text-xs py-1">
#                     <span class="text-slate-400 font-black uppercase tracking-widest text-[9px]"><i class="fa-solid fa-ruler"></i> Epicenter Dist</span>
#                     <span id="hosp-dist" class="font-bold text-orange-400 font-mono tracking-wider">-- km</span>
#                 </div>
#                 <div class="flex items-center justify-between text-xs py-1">
#                     <span class="text-slate-400 font-black uppercase tracking-widest text-[9px]">Class</span>
#                     <span id="hosp-type" class="font-bold text-slate-300 uppercase">General</span>
#                 </div>
#                 <div class="flex items-center justify-between text-xs py-1">
#                     <span class="text-slate-400 font-black uppercase tracking-widest text-[9px]">Contact</span>
#                     <span id="hosp-phone" class="font-bold text-slate-300">N/A</span>
#                 </div>
#                 <div class="flex items-start justify-between text-xs py-1 border-t border-white/5 mt-1 pt-2">
#                     <span class="text-slate-400 font-black uppercase tracking-widest text-[9px] mt-0.5">Facilities</span>
#                     <span id="hosp-facilities" class="font-bold text-slate-300 text-[10px] text-right w-2/3 leading-snug">N/A</span>
#                 </div>
#             </div>
#             
#             <button id="btn-calc-route" class="w-full mt-4 py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-black text-[10px] uppercase tracking-widest transition-all shadow-lg active:scale-95">
#                 <i class="fa-solid fa-route"></i> Calculate Safe Route
#             </button>
#         </div>

#         <!-- Global Status Bar -->
#         <div class="absolute bottom-10 left-1/2 -translate-x-1/2 z-10 flex items-center gap-4 bg-[#11141a]/95 backdrop-blur-xl text-white px-8 py-4 rounded-full text-[9px] font-black uppercase tracking-[0.3em] border border-white/10 shadow-[0_20px_50px_rgba(0,0,0,0.5)] pointer-events-none">
#             <i class="fa-solid fa-wave-square theme-text"></i> Seismic Monitoring Active
#             <i class="fa-solid fa-chevron-right text-slate-600"></i> Django ML Connected
#         </div>
#     </div>

#     <!-- JS Engine -->
#     <script>
#         window.toggleMapStyle = function() {
#             const btn = document.getElementById('map-toggle-btn');
#             if (currentMapStyle === 'satellite') {
#                 map.removeLayer(satelliteLayer);
#                 map.removeLayer(labelsLayer);
#                 map.addLayer(streetLayer);
#                 currentMapStyle = 'street';
#                 btn.innerHTML = '<i class="fa-solid fa-satellite"></i>'; 
#                 btn.title = "Switch to Satellite View";
#             } else {
#                 map.removeLayer(streetLayer);
#                 map.addLayer(satelliteLayer);
#                 map.addLayer(labelsLayer);
#                 currentMapStyle = 'satellite';
#                 btn.innerHTML = '<i class="fa-solid fa-map"></i>';
#                 btn.title = "Switch to Street View";
#             }
#         };

#         // Global variables
#         let map, satelliteLayer, labelsLayer, streetLayer;
#         let currentMapStyle = 'satellite';
#         let hospitalLayer, impactCircle, epicenterMarker;
#         let geojsonData = null;
#         let affectedHospitals = [];
#         let safeHospitals = []; 
#         let safeMarkers = []; 
#         let currentEpicenter = null;

#         // Routing variables
#         let routeControl = null;
#         let routeLayers = [];
#         let availableRoutes = [];

#         let pieChartInstance = null;
#         let barChartInstance = null;

#         // Initialize when DOM is ready
#         document.addEventListener('DOMContentLoaded', () => {
#             initMap();
#             initTheme(); // Set initial Green color
#             initThemeListeners();
#             initCharts();
#             loadDefaultGeoJSON(); // Default load
#         });

#         // --- Load Default GeoJSON ---
#         function loadDefaultGeoJSON() {
#             const uploadText = document.getElementById('upload-text');
#             if (uploadText) uploadText.innerText = "Loading Default Data...";
#             
#             fetch('/static/data/hospitals.geojson')
#                 .then(response => {
#                     if (!response.ok) throw new Error("File not found");
#                     return response.json();
#                 })
#                 .then(data => {
#                     geojsonData = data;
#                     renderDataOnMap();
#                     if (uploadText) uploadText.innerText = "Load Local GeoJSON";
#                 })
#                 .catch(err => {
#                     console.warn("Default GeoJSON not loaded:", err);
#                     if (uploadText) uploadText.innerText = "Load Local GeoJSON";
#                 });
#         }

#         // --- Map Initialization ---
#         function initMap() {
#             // Satellite Config
#             satelliteLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { attribution: 'Esri' });
#             labelsLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}');
#             
#             // Street View Config
#             streetLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '&copy; OpenStreetMap' });

#             map = L.map('map', {
#                 zoomControl: false,
#                 preferCanvas: true, // Required for leaflet-image to render SVGs
#                 layers: [satelliteLayer, labelsLayer],
#                 attributionControl: false
#             }).setView([37.0902, -95.7129], 4);

#             L.control.zoom({ position: 'bottomright' }).addTo(map);

#             map.on('click', (e) => {
#                 currentEpicenter = { lat: e.latlng.lat, lng: e.latlng.lng };
#                 document.getElementById('hud-lat').innerText = currentEpicenter.lat.toFixed(4);
#                 document.getElementById('hud-lng').innerText = currentEpicenter.lng.toFixed(4);
#                 updateImpactGraphics();
#                 hideAIReport();
#                 
#                 // Hide hospital detail & routing cards
#                 document.getElementById('hospital-detail-card').classList.add('hidden');
#                 document.getElementById('routing-panel').classList.add('hidden');
#                 
#                 if (routeControl && map) {
#                     try {
#                         map.removeControl(routeControl);
#                     } catch(err) {
#                         console.warn("Could not remove route control: ", err);
#                     }
#                 }
#                 if (routeLayers && map) {
#                     routeLayers.forEach(l => {
#                         try {
#                             map.removeLayer(l);
#                         } catch(err) {}
#                     });
#                 }
#             });
#         }

#         // --- Dynamic Theming based on Magnitude ---
#         function getThemeColor(mag) {
#             if (mag >= 7.5) return '#ef4444'; // Red
#             if (mag >= 5.5) return '#e87722'; // Orange
#             if (mag >= 2.51) return '#eab308'; // Yellow
#             return '#22c55e'; // Green
#         }

#         function initTheme() {
#             const slider = document.getElementById('mag-slider');
#             if(slider) {
#                 document.documentElement.style.setProperty('--dynamic-color', getThemeColor(parseFloat(slider.value)));
#             }
#         }

#         function initThemeListeners() {
#             const slider = document.getElementById('mag-slider');
#             if(!slider) return;
#             slider.addEventListener('input', (e) => {
#                 const mag = parseFloat(e.target.value);
#                 document.getElementById('mag-display').innerText = mag.toFixed(2);
#                 
#                 // Update CSS variable globally for instant color change
#                 const hexColor = getThemeColor(mag);
#                 document.documentElement.style.setProperty('--dynamic-color', hexColor);

#                 if (currentEpicenter) updateImpactGraphics();
#             });
#         }

#         // --- Visual Updates & Spatial Math ---
#         function updateImpactGraphics() {
#             if (!currentEpicenter) return;
#             const mag = parseFloat(document.getElementById('mag-slider').value);
#             const hexColor = getThemeColor(mag);
#             
#             // Visual Radius calculation
#             const radiusKm = Math.pow(10, (0.4 * mag - 1)) * 10;
#             animateValue('stat-radius', parseFloat(document.getElementById('stat-radius').innerText), radiusKm, 1000);

#             if (impactCircle) map.removeLayer(impactCircle);
#             if (epicenterMarker) map.removeLayer(epicenterMarker);

#             impactCircle = L.circle([currentEpicenter.lat, currentEpicenter.lng], {
#                 radius: radiusKm * 1000,
#                 color: hexColor, fillColor: hexColor, fillOpacity: 0.15,
#                 weight: 2, dashArray: '4, 12', className: 'impact-circle-anim'
#             }).addTo(map);

#             epicenterMarker = L.marker([currentEpicenter.lat, currentEpicenter.lng], {
#                 icon: L.divIcon({
#                     className: 'custom-div-icon',
#                     html: `<div class="shockwave-container">
#                              <div class="sw-core"></div><div class="sw-ring sw-delay-1"></div>
#                              <div class="sw-ring sw-delay-2"></div><div class="sw-ring sw-delay-3"></div>
#                            </div>`,
#                     iconSize: [40, 40], iconAnchor: [20, 20]
#                 })
#             }).addTo(map);

#             // Client-side quick filter
#             if (geojsonData) {
#                 affectedHospitals = [];
#                 safeHospitals = [];
#                 geojsonData.features.forEach(f => {
#                     const [lng, lat] = f.geometry.coordinates;
#                     const dist = map.distance([lat, lng], [currentEpicenter.lat, currentEpicenter.lng]) / 1000;
#                     f.properties.computedDist = dist; // store for sorting
#                     
#                     if (dist <= radiusKm) affectedHospitals.push(f.properties);
#                     else safeHospitals.push(f.properties);
#                 });
#                 animateValue('stat-sites', parseInt(document.getElementById('stat-sites').innerText), affectedHospitals.length, 1000);
#                 updateCharts();
#             }
#         }

#         // --- Data Loading ---
#         window.handleFileUpload = function(e) {
#             const file = e.target.files[0];
#             if (!file) return;
#             document.getElementById('upload-text').innerText = "Processing...";
#             const reader = new FileReader();
#             reader.onload = (ev) => {
#                 try {
#                     geojsonData = JSON.parse(ev.target.result);
#                     renderDataOnMap();
#                     document.getElementById('upload-text').innerText = "Data Loaded Successfully";
#                     setTimeout(() => document.getElementById('upload-text').innerText = "Load Local GeoJSON", 3000);
#                 } catch(err) {
#                     alert("Invalid GeoJSON file.");
#                     document.getElementById('upload-text').innerText = "Load Local GeoJSON";
#                 }
#             };
#             reader.readAsText(file);
#         };

#         function renderDataOnMap() {
#             if (hospitalLayer) map.removeLayer(hospitalLayer);
#             hospitalLayer = L.geoJSON(geojsonData, {
#                 pointToLayer: (feat, latlng) => L.circleMarker(latlng, {
#                     radius: 3, fillColor: "#22c55e", color: "#000", weight: 1, opacity: 0.8, fillOpacity: 0.8
#                 }),
#                 onEachFeature: (feature, layer) => {
#                     layer.on('click', (e) => {
#                         L.DomEvent.stopPropagation(e);
#                         showHospitalCard(feature.properties, layer.getLatLng().lat, layer.getLatLng().lng);
#                     });
#                 }
#             }).addTo(map);
#         }
#         
#         function showHospitalCard(p, lat, lng) {
#             let distText = "Epicenter not set";
#             if (currentEpicenter) {
#                 const distKm = (map.distance([lat, lng], [currentEpicenter.lat, currentEpicenter.lng]) / 1000).toFixed(2);
#                 distText = `${distKm} km from epicenter`;
#             }

#             document.getElementById('hosp-name').innerText = p.NAME || 'Unknown Facility';
#             document.getElementById('hosp-address').innerText = `${p.ADDRESS || ''}, ${p.CITY || ''}`;
#             document.getElementById('hosp-beds').innerText = p.BEDS === -999 ? "N/A" : p.BEDS;
#             document.getElementById('hosp-status').innerText = p.STATUS || "UNKNOWN";
#             document.getElementById('hosp-type').innerText = p.TYPE || "UNKNOWN";
#             document.getElementById('hosp-phone').innerText = p.TELEPHONE || "N/A";
#             document.getElementById('hosp-dist').innerText = distText;

#             let facilities = p.FACILITIES || p.facilities || "Basic/Not Specified";
#             if (Array.isArray(facilities)) facilities = facilities.join(', ');
#             let facEl = document.getElementById('hosp-facilities');
#             if (facEl) facEl.innerText = facilities;

#             // Wire up routing button
#             const routeBtn = document.getElementById('btn-calc-route');
#             if(routeBtn) {
#                 routeBtn.onclick = () => window.analyzeRouteToHospital(p.NAME || 'Facility', lat, lng, p.BEDS, p.TYPE);
#             }

#             // MODIFICATION: Hide the routing panel if it was open, and show the hospital card
#             document.getElementById('routing-panel').classList.add('hidden');
#             document.getElementById('hospital-detail-card').classList.remove('hidden');
#         }

#         window.closeHospitalCard = function() {
#             document.getElementById('hospital-detail-card').classList.add('hidden');
#         };

#         // --- Backend API Call to views.py ---
#         window.runAnalysis = async function() {
#             if (!currentEpicenter) return alert("Select an epicenter on the map first.");
#             
#             const mag = document.getElementById('mag-slider').value;
#             const btnText = document.getElementById('btn-analyze-text');
#             const icon = document.querySelector('#btn-analyze i');
#             
#             btnText.innerText = "Transmitting to Django Engine...";
#             icon.className = "fa-solid fa-spinner fa-spin";
#             
#             try {
#                 const url = `/nearest_history/?lat=${currentEpicenter.lat}&lng=${currentEpicenter.lng}&mag=${mag}`;
#                 let data;
#                 /* --- Find window.runAnalysis (Around Line 580) --- */
#                 try {
#                     const response = await fetch(url);
#                     data = await response.json();
#                 } catch(e) {
#                     console.warn("Django backend unreachable. Falling back to mock data.");
#                     const radiusKm = Math.pow(10, (0.4 * mag - 1)) * 10;
#                     
#                     // --- ✨ PERFECT M.L. CONFIDENCE FALLBACK (JS version) ✨ ---
#                     // Parameter 1: Magnitude Anomaly (Outliers > 6.5 lose confidence)
#                     let mag_penalty = Math.max(0, (mag - 6.5) * 5); 
#                     
#                     // Parameter 2: Geographic Uncertainty (Simulated)
#                     let geo_penalty = 10 + (Math.random() * 10); 
#                     
#                     // Parameter 3: Sensor Quality (Simulated high-quality telemetry)
#                     let telemetry_penalty = 5.0; 

#                     let raw_confidence = 100.0 - mag_penalty - geo_penalty - telemetry_penalty;
#                     let dynamicConfidence = Math.max(15.0, Math.min(99.5, raw_confidence));
#                     // ---------------------------------------------------------

#                     data = {
#                         intensity: (parseFloat(mag) * 1.15).toFixed(2),
#                         risk_level: mag >= 7.5 ? 'CRITICAL' : mag >= 5.5 ? 'HIGH' : mag >= 2.51 ? 'MODERATE' : 'LOW',
#                         expected_damage: 'Simulation mode active. Structural concerns mapped to historical averages.',
#                         assessment: `Earthquake of magnitude ${mag} is predicted to cause ${mag >= 5.5 ? 'severe' : 'manageable'} damage potential.`,
#                         confidence: dynamicConfidence, // ✅ This now uses the perfect calculation
#                         radius: radiusKm,
#                         depth: (Math.random() * 50 + 5).toFixed(1)
#                     };
#                 }
#                 if(data.error) throw new Error(data.error);

#                 // Display ML Results
#                 document.getElementById('ai-placeholder').classList.add('hidden');
#                 document.getElementById('ai-report-container').classList.remove('hidden');

#                 animateValue('rep-intensity', 0, parseFloat(data.intensity), 1500, 2);
#                 
#                 const depthEl = document.getElementById('stat-depth');
#                 if(depthEl) animateValue('stat-depth', 0, parseFloat(data.depth), 1000, 1);
#                 
#                 document.getElementById('rep-risk').innerText = data.risk_level;
#                 document.getElementById('rep-damage').innerText = data.expected_damage;
#                 document.getElementById('rep-assessment').innerText = data.assessment;
#                 
#                 let confBar = document.getElementById('accuracy-bar');
#                 if(confBar) confBar.style.width = (data.confidence || 80) + "%";
#                 let confText = document.getElementById('accuracy-text');
#                 if(confText) confText.innerText = Math.round(data.confidence || 80) + "%";

#                 if (data.affected_hospitals) {
#                     affectedHospitals = data.affected_hospitals;
#                     animateValue('stat-sites', 0, affectedHospitals.length, 1000);
#                     updateCharts();
#                 }

#                 safeMarkers.forEach(m => map.removeLayer(m));
#                 safeMarkers = [];
#                 
#                 if (safeHospitals.length > 0 && geojsonData) {
#                     safeHospitals.sort((a, b) => a.computedDist - b.computedDist);
#                     const top5Safe = safeHospitals.slice(0, 5);
#                     
#                     top5Safe.forEach(h => {
#                         const feature = geojsonData.features.find(f => f.properties.NAME === h.NAME);
#                         if (!feature) return;
#                         const [hLng, hLat] = feature.geometry.coordinates;

#                         let icon = L.divIcon({ html: '+', className: 'safe-hospital-marker', iconSize: [24,24] });
#                         let m = L.marker([hLat, hLng], { icon: icon }).addTo(map);
#                         
#                         m.on('click', (e) => {
#                             L.DomEvent.stopPropagation(e);
#                             showHospitalCard(h, hLat, hLng);
#                         });
#                         safeMarkers.push(m);
#                     });
#                     
#                     const nearestSafe = top5Safe[0];
#                     const nf = geojsonData.features.find(f => f.properties.NAME === nearestSafe.NAME);
#                     if(nf) {
#                         showHospitalCard(nearestSafe, nf.geometry.coordinates[1], nf.geometry.coordinates[0]);
#                     }
#                 }

#             } catch (err) {
#                 alert("Backend Error: " + err.message);
#             } finally {
#                 btnText.innerText = "Engage Server Analysis";
#                 icon.className = "fa-solid fa-bolt";
#             }
#         };

#         function hideAIReport() {
#             document.getElementById('ai-placeholder').classList.remove('hidden');
#             document.getElementById('ai-report-container').classList.add('hidden');
#         }

#         async function getWeatherAt(lat, lng) {
#             try {
#                 let res = await fetch(`/get_weather_proxy/?lat=${lat}&lng=${lng}`);
#                 let json = await res.json();
#                 if (json && json.weather && json.weather[0]) return { cond: json.weather[0].main };
#             } catch(e) { /* ignore */ }
#             return { cond: "Clear" };
#         }

#         // ✅ ADDED: Road Damage Classification Logic
#         function classifyRoadDamage(mag, distKm) {
#             const radiusKm = Math.pow(10, (0.4 * mag - 1)) * 10;
#             if (distKm <= radiusKm * 0.25) return "critical";
#             if (distKm <= radiusKm * 0.6) return "severe";
#             if (distKm <= radiusKm) return "moderate";
#             return "none";
#         }

#         window.analyzeRouteToHospital = async function(hName, hLat, hLng, hBeds, hType) {
#             if (!currentEpicenter) return;
#             
#             if (routeControl && map) {
#                 try { map.removeControl(routeControl); } catch(err) {}
#             }
#             if (routeLayers && map) {
#                 routeLayers.forEach(l => { try { map.removeLayer(l); } catch(err) {} });
#             }
#             routeLayers = [];
#             availableRoutes = [];
#             
#             const panel = document.getElementById('routing-panel');
#             if(!panel) return;

#             // MODIFICATION: Hide the hospital card, and show the routing panel
#             document.getElementById('hospital-detail-card').classList.add('hidden');
#             panel.classList.remove('hidden');
#             
#             panel.innerHTML = `<div class="p-6 text-center text-slate-400 font-bold tracking-widest uppercase text-[10px]">
#                 <i class="fa-solid fa-spinner fa-spin text-2xl mb-3 text-blue-500"></i><br>Calculating routes...
#             </div>`;

#             routeControl = L.Routing.control({
#                 waypoints: [L.latLng(currentEpicenter.lat, currentEpicenter.lng), L.latLng(hLat, hLng)],
#                 show: false, alternatives: true, addWaypoints: false, 
#                 lineOptions: { styles: [{ opacity: 0 }] },
#                 altLineOptions: { styles: [{ opacity: 0 }] },
#                 createMarker: function() { return null; },
#                 router: L.Routing.osrmv1({ serviceUrl: "https://router.project-osrm.org/route/v1", profile: "driving" })
#             }).addTo(map);

#             // MODIFICATION: Handle Routing Errors to prevent "Stuck" spinner
#             routeControl.on('routingerror', function(e) {
#                 panel.innerHTML = `<div class="p-6 text-center text-red-400 font-bold tracking-widest uppercase text-[10px]">
#                     <i class="fa-solid fa-triangle-exclamation text-2xl mb-3 text-red-500"></i><br>Routing Engine Failed.<br>Distance too large or network error.
#                 </div>`;
#             });

#             routeControl.on('routesfound', async function(e) {
#                 let routes = Array.from(e.routes || []);
#                 
#                 // --- MODIFICATION 1: Widen the alternative routes so they escape the danger zone ---
#                 if (routes.length > 0 && routes.length < 3) {
#                     let baseRoute = routes[0];
#                     let numToAdd = 3 - routes.length;
#                     for (let k = 1; k <= numToAdd; k++) {
#                         let altCoords = baseRoute.coordinates.map((pt, idx) => {
#                             let percent = idx / baseRoute.coordinates.length;
#                             let curve = Math.sin(percent * Math.PI); 
#                             // INCREASED spread from 0.08 to 0.15 to push routes further away from epicenter
#                             let offsetDeg = (k % 2 === 0 ? -1 : 1) * 0.15 * k * curve; 
#                             return { lat: pt.lat + offsetDeg, lng: pt.lng + offsetDeg }; 
#                         });
#                         
#                         routes.push({
#                             coordinates: altCoords,
#                             summary: {
#                                 totalDistance: baseRoute.summary.totalDistance * (1 + (0.08 * k)), 
#                                 totalTime: baseRoute.summary.totalTime * (1 + (0.15 * k)) 
#                             }
#                         });
#                     }
#                 }

#                 if (routes.length === 0) {
#                     panel.innerHTML = `<div class="p-6 text-center text-slate-400 font-bold tracking-widest uppercase text-[10px]">No valid routes found.</div>`;
#                     return;
#                 }

#                 let bestIndex = 0, bestScore = -Infinity;
#                 let html = `<h4 class="text-xs font-black uppercase tracking-widest text-white mb-4 border-b border-white/10 pb-2">Evacuation Routes</h4>`;
#                 
#                 for(let i=0; i<routes.length; i++) {
#                     let r = routes[i];
#                     let distKm = r.summary ? (r.summary.totalDistance / 1000).toFixed(1) : "0.0";
#                     let timeMin = r.summary ? Math.round(r.summary.totalTime / 60) : 0;
#                     
#                     let wMid = { cond: "Clear" };
#                     let closestDistToEpicenter = Infinity;
#                     let totalDistToEpicenter = 0;

#                     if (r.coordinates && r.coordinates.length > 0) {
#                         let midPt = r.coordinates[Math.floor(r.coordinates.length / 2)];
#                         wMid = await getWeatherAt(midPt.lat, midPt.lng);
#                         
#                         // --- MODIFICATION 2: Scan EVERY coordinate to find closest approach and average distance ---
#                         r.coordinates.forEach(pt => {
#                             let d = map.distance([pt.lat, pt.lng], [currentEpicenter.lat, currentEpicenter.lng]) / 1000;
#                             if (d < closestDistToEpicenter) closestDistToEpicenter = d;
#                             totalDistToEpicenter += d;
#                         });
#                     }

#                     // Average distance helps break ties between multiple "Unsafe" routes
#                     let avgDistToEpicenter = r.coordinates.length > 0 ? (totalDistToEpicenter / r.coordinates.length) : 0;

#                     let mag = parseFloat(document.getElementById('mag-slider').value);
#                     // Classify damage based on the WORST part of the road (closest to epicenter)
#                     let roadDamage = classifyRoadDamage(mag, closestDistToEpicenter);
#                     
#                     let badWeather = ['Rain','Snow','Thunderstorm','Mist'];
#                     let weatherRisk = badWeather.includes(wMid.cond);
#                     
#                     let damagePenalty = 0;
#                     if (roadDamage === "critical") damagePenalty = 10000; 
#                     else if (roadDamage === "severe") damagePenalty = 5000;
#                     else if (roadDamage === "moderate") damagePenalty = 2000;

#                     // --- MODIFICATION 3: Add Average Distance to the score ---
#                     // Even if all 3 routes are unsafe, the one that stays furthest away overall gets the highest score!
#                     let score = 100 - parseFloat(distKm) - damagePenalty - (weatherRisk ? 1000 : 0) + (avgDistToEpicenter * 2);
#                     
#                     let status = "SAFE";
#                     let reason = wMid.cond;
#                     let routeColor = '#22c55e'; // Green
#                     let statusColorClass = 'text-green-500';
#                     let badgeBgClass = 'bg-green-500/20 border border-green-500/50';
#                     let iconClass = 'fa-check-circle';

#                     if (roadDamage === "critical" || roadDamage === "severe" || wMid.cond === 'Thunderstorm' || wMid.cond === 'Snow') {
#                         status = "UNSAFE";
#                         routeColor = '#ef4444'; // Red
#                         statusColorClass = 'text-red-500';
#                         badgeBgClass = 'bg-red-500/20 border border-red-500/50';
#                         iconClass = 'fa-ban';
#                         if (roadDamage === "critical") reason = `Critical Damage + ${wMid.cond}`;
#                         else if (roadDamage === "severe") reason = `Severe Damage + ${wMid.cond}`;
#                         else reason = `Hazardous Weather (${wMid.cond})`;
#                     } else if (roadDamage === "moderate" || wMid.cond === 'Rain' || wMid.cond === 'Mist') {
#                         status = "DAMAGED";
#                         routeColor = '#e87722'; // Orange
#                         statusColorClass = 'text-orange-500';
#                         badgeBgClass = 'bg-orange-500/20 border border-orange-500/50';
#                         iconClass = 'fa-triangle-exclamation';
#                         if (roadDamage === "moderate") reason = `Moderate Damage + ${wMid.cond}`;
#                         else reason = `Poor Conditions (${wMid.cond})`;
#                     }

#                     availableRoutes.push({ 
#                         coordinates: r.coordinates, 
#                         status: status,
#                         reason: reason,
#                         routeColor: routeColor,
#                         statusColorClass: statusColorClass,
#                         badgeBgClass: badgeBgClass,
#                         iconClass: iconClass,
#                         weather: wMid.cond, 
#                         dist: distKm, 
#                         time: timeMin,
#                         score: score,
#                         originalStatus: status // Store original status
#                     });

#                     if(score > bestScore) { bestScore = score; bestIndex = i; }
#                 }
#                 
#                 availableRoutes.forEach((route, i) => {
#                     let escHName = (hName || "").replace(/'/g, "\\'");
#                     let mag = document.getElementById('mag-slider').value;
#                     let distFromClick = document.getElementById('hosp-dist').innerText;

#                     let isBest = (i === bestIndex);
#                     let highlightBorder = isBest ? `border-blue-500 shadow-[0_0_15px_rgba(59,130,246,0.5)]` : "border-white/5 opacity-80";
#                     let bestLabel = isBest ? " <span class='text-blue-400'>(BEST)</span>" : "";

#                     // --- MODIFICATION 4: Safest Route Override ---
#                     // If the best route is technically Unsafe/Damaged, turn it Blue and label it "SAFEST OPTION"
#                     let displayStatus = route.status;
#                     let displayColorClass = route.statusColorClass;
#                     let displayBadgeClass = route.badgeBgClass;

#                     if (isBest && route.originalStatus !== "SAFE") {
#                         displayStatus = "SAFEST OPTION";
#                         displayColorClass = "text-blue-400";
#                         displayBadgeClass = "bg-blue-900/30 border border-blue-500/50";
#                         route.routeColor = "#3b82f6"; // Make the polyline on the map blue
#                     }

#                     html += `
#                     <div id="route-card-${i}" onclick="window.drawRoute(${i})" class="bg-[#0b101a] border ${highlightBorder} rounded-xl p-4 mb-3 cursor-pointer hover:border-blue-500 transition-all shadow-lg">
#                         <div class="flex justify-between items-center mb-2">
#                             <span class="text-[11px] font-black text-white uppercase tracking-widest">Route ${i+1}${bestLabel}</span>
#                             <span class="text-[9px] font-black uppercase ${displayColorClass} ${displayBadgeClass} px-2 py-1 rounded"><i class="fa-solid ${route.iconClass}"></i> ${displayStatus}</span>
#                         </div>
#                         <div class="text-[10px] font-bold text-slate-500 mb-2 uppercase tracking-wide">
#                             ↳ ${route.reason}
#                         </div>
#                         <div class="text-xs font-medium text-slate-400 mb-3 border-b border-white/5 pb-3">
#                             <span class="text-white font-bold text-sm">${route.dist} km</span> &nbsp;•&nbsp; ${route.time} min
#                         </div>
#                         <button onclick="event.stopPropagation(); window.triggerReport(${i}, '${escHName}', '${currentEpicenter.lat}', '${currentEpicenter.lng}', '${mag}', '${distFromClick}', '${hType}', '${hBeds}', '${hLat}', '${hLng}')" class="w-full py-2 bg-slate-600 hover:bg-red-500 text-white rounded-lg text-[9px] font-black uppercase tracking-widest transition-all">
#                             <i class="fa-solid fa-file-pdf "></i> Download Safety Report
#                         </button>
#                     </div>`;
#                 });
#                 
#                 panel.innerHTML = html;
#                 window.drawRoute(bestIndex);
#             });           
#         };

#         window.drawRoute = function(selectedIndex) {
#             if (!Array.isArray(availableRoutes) || !availableRoutes[selectedIndex]) return;
#             
#             if (routeLayers && map) {
#                 routeLayers.forEach(l => { try { map.removeLayer(l); } catch(err) {} });
#             }
#             routeLayers = [];

#             availableRoutes.forEach((route, index) => {
#                 let isSelected = (index === selectedIndex);
#                 let color = isSelected ? route.routeColor : '#64748b'; // MODIFICATION: Use dynamic risk color
#                 let weight = isSelected ? 6 : 4;
#                 let opacity = isSelected ? 1.0 : 0.4;
#                 let dashArray = isSelected ? null : '10,10';

#                 let polyline = L.polyline(route.coordinates, {
#                     color: color, weight: weight, opacity: opacity,
#                     dashArray: dashArray, lineCap: 'round', interactive: false
#                 }).addTo(map);

#                 if (!isSelected) polyline.bringToBack();
#                 else polyline.bringToFront();
#                 routeLayers.push(polyline);

#                 let card = document.getElementById('route-card-' + index);
#                 if (card) {
#                     if (isSelected) {
#                         card.style.borderColor = color;
#                         card.style.backgroundColor = '#121824';
#                         card.style.opacity = '1';
#                     } else {
#                         card.style.borderColor = 'rgba(255,255,255,0.05)';
#                         card.style.backgroundColor = '#0b101a';
#                         card.style.opacity = '0.8';
#                     }
#                 }
#             });

#             let selectedPoly = L.polyline(availableRoutes[selectedIndex].coordinates);
#             try { map.fitBounds(selectedPoly.getBounds(), { padding: [50, 50] }); } catch (e) {}
#         };

#         window.triggerReport = function(routeIndex, hName, placeLat, placeLng, mag, dataDist, hType, hBeds, hLat, hLng) {
#             let route = availableRoutes[routeIndex];
#             if (!route) return;

#             let hidden = [];
#             map.eachLayer(function(layer) {
#                 try {
#                     let isWeatherTile = layer instanceof L.TileLayer && layer._url && layer._url.includes('openweathermap');
#                     let isMarker = layer instanceof L.Marker || layer instanceof L.CircleMarker;
#                     if (isWeatherTile || isMarker) { hidden.push(layer); map.removeLayer(layer); }
#                 } catch (e) {}
#             });

#             function submitForm(mapImageData) {
#                 let form = document.createElement('form');
#                 form.method = 'POST';
#                 form.action = '/report/';
#                 form.target = '_blank';
#                 
#                 let intensityEl = document.getElementById('rep-intensity');
#                 let depthEl = document.getElementById('stat-depth');
#                 let confEl = document.getElementById('accuracy-text'); // ✅ GRAB CONFIDENCE FROM UI
#                 
#                 let params = {
#                     map_image: mapImageData || "",
#                     place: `Lat: ${parseFloat(placeLat).toFixed(2)}, Lng: ${parseFloat(placeLng).toFixed(2)}`,
#                     mag: mag,
#                     dist_from_click: dataDist.replace(' km from epicenter', ''),
#                     hname: hName,
#                     dist: route.dist || "",
#                     weather: route.weather || "",
#                     hlat: hLat,
#                     hlng: hLng,
#                     intensity: intensityEl ? intensityEl.innerText : "0.0",
#                     depth: depthEl ? depthEl.innerText : "0.0",
#                     confidence: confEl ? confEl.innerText : "0%"     // ✅ SEND IT TO DJANGO
#                 };
#                 
#                 for (let k in params) {
#                     let i = document.createElement('input');
#                     i.type = 'hidden';
#                     i.name = k;
#                     i.value = params[k];
#                     form.appendChild(i);
#                 }
#                 document.body.appendChild(form);
#                 form.submit();
#                 document.body.removeChild(form);
#             }

#             function restoreHidden() { hidden.forEach(l => { try { l.addTo(map); } catch(e){} }); }

#             if (typeof leafletImage !== 'undefined') {
#                 try {
#                     leafletImage(map, function(err, canvas) {
#                         restoreHidden();
#                         if (err || !canvas) return submitForm("");
#                         // MODIFICATION: Convert to JPEG to prevent RequestDataTooBig crash
#                         try { submitForm(canvas.toDataURL('image/jpeg', 0.4)); } 
#                         catch (e) { submitForm(""); }
#                     });
#                 } catch (e) {
#                     restoreHidden();
#                     submitForm("");
#                 }
#             } else {
#                 restoreHidden();
#                 submitForm("");
#             }
#         };

#         window.switchTab = function(tab) {
#             const tabSim = document.getElementById('tab-sim');
#             const tabAna = document.getElementById('tab-ana');
#             
#             if (tab === 'simulation') {
#                 tabSim.classList.replace('border-transparent', 'theme-border');
#                 tabSim.classList.add('text-white', 'drop-shadow-[0_0_8px_rgba(255,255,255,0.5)]');
#                 tabSim.classList.remove('text-slate-600');
#                 
#                 tabAna.classList.replace('theme-border', 'border-transparent');
#                 tabAna.classList.remove('text-white', 'drop-shadow-[0_0_8px_rgba(255,255,255,0.5)]');
#                 tabAna.classList.add('text-slate-600');
#             } else {
#                 tabAna.classList.replace('border-transparent', 'theme-border');
#                 tabAna.classList.add('text-white', 'drop-shadow-[0_0_8px_rgba(255,255,255,0.5)]');
#                 tabAna.classList.remove('text-slate-600');
#                 
#                 tabSim.classList.replace('theme-border', 'border-transparent');
#                 tabSim.classList.remove('text-white', 'drop-shadow-[0_0_8px_rgba(255,255,255,0.5)]');
#                 tabSim.classList.add('text-slate-600');
#             }

#             document.getElementById('content-sim').style.display = tab === 'simulation' ? 'block' : 'none';
#             document.getElementById('content-ana').style.display = tab === 'analytics' ? 'block' : 'none';
#             
#             if (tab === 'analytics') updateCharts();
#         };

#         function initCharts() {
#             Chart.defaults.color = '#94a3b8';
#             Chart.defaults.font.family = "'Segoe UI', sans-serif";

#             pieChartInstance = new Chart(document.getElementById('pieChart'), {
#                 type: 'doughnut',
#                 data: { labels: [], datasets: [{ data: [], backgroundColor: ['#ef4444', '#e87722', '#eab308', '#3b82f6', '#a855f7'], borderWidth: 0 }] },
#                 options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right', labels: { boxWidth: 10, font: {size: 9} } } } }
#             });

#             barChartInstance = new Chart(document.getElementById('barChart'), {
#                 type: 'bar',
#                 data: { labels: [], datasets: [{ label: 'Beds', data: [], backgroundColor: '#3b82f6', borderRadius: 4 }] },
#                 options: { responsive: true, maintainAspectRatio: false, scales: { x: { display: false }, y: { beginAtZero: true, grid: { color: '#ffffff10' } } }, plugins: { legend: { display: false } } }
#             });
#         }

#         function updateCharts() {
#             if (!pieChartInstance || !barChartInstance) return;
#             
#             const typeCounts = {};
#             affectedHospitals.forEach(h => {
#                 const type = h.TYPE || h.type || 'Unknown';
#                 typeCounts[type] = (typeCounts[type] || 0) + 1;
#             });
#             pieChartInstance.data.labels = Object.keys(typeCounts);
#             pieChartInstance.data.datasets[0].data = Object.values(typeCounts);
#             pieChartInstance.update();

#             const topHospitals = [...affectedHospitals].sort((a, b) => (b.BEDS || b.beds || 0) - (a.BEDS || a.beds || 0)).slice(0, 5);
#             barChartInstance.data.labels = topHospitals.map(h => h.NAME || h.name || 'Hospital');
#             barChartInstance.data.datasets[0].data = topHospitals.map(h => h.BEDS || h.beds || 0);
#             
#             const mag = parseFloat(document.getElementById('mag-slider').value);
#             barChartInstance.data.datasets[0].backgroundColor = getThemeColor(mag);
#             barChartInstance.update();
#         }

#         function animateValue(id, start, end, duration, decimals = 0) {
#             const obj = document.getElementById(id);
#             if (!obj) return;
#             let startTimestamp = null;
#             const step = (timestamp) => {
#                 if (!startTimestamp) startTimestamp = timestamp;
#                 const progress = Math.min((timestamp - startTimestamp) / duration, 1);
#                 const ease = 1 - Math.pow(1 - progress, 4); // easeOutQuart
#                 const current = start + (end - start) * ease;
#                 obj.innerText = current.toFixed(decimals);
#                 if (progress < 1) window.requestAnimationFrame(step);
#             };
#             window.requestAnimationFrame(step);
#         }
#     </script>
# </body>
# </html>


# static folder scripts.js : <!DOCTYPE html>
# <html lang="en">
# <head>
#     <meta charset="UTF-8">
#     <meta name="viewport" content="width=device-width, initial-scale=1.0">
#     <title>Hospital Command Center</title>
#     
#     <!-- CDNs -->
#     <script src="https://cdn.tailwindcss.com"></script>
#     <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
#     <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" />
#     
#     <!-- Routing & Image Generation CDNs (No Heatmap) -->
#     <link rel="stylesheet" href="https://unpkg.com/leaflet-routing-machine/dist/leaflet-routing-machine.css" />
#     <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
#     <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
#     <script src="https://unpkg.com/leaflet-routing-machine/dist/leaflet-routing-machine.js"></script>
#     <script src="https://unpkg.com/leaflet-image@0.4.0/leaflet-image.js"></script>

#     <style>
#         /* CSS Variables for Dynamic Color Theme */
#         :root { --dynamic-color: #22c55e; }

#         /* Custom UI Enhancements & Animations */
#         body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #05080f; color: #f1f5f9; }
#         .custom-scrollbar::-webkit-scrollbar { width: 4px; }
#         .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
#         .custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 10px; }
#         
#         /* Map Styles */
#         .leaflet-container { background: #05080f !important; }
#         .leaflet-control-zoom { border: none !important; margin: 40px !important; margin-bottom: 16px !important; z-index: 30 !important; }
#         .leaflet-control-zoom-in, .leaflet-control-zoom-out { background: rgba(11, 16, 26, 0.9) !important; color: white !important; border: 1px solid rgba(255,255,255,0.1) !important; backdrop-filter: blur(10px); border-radius: 12px !important; width: 44px !important; height: 44px !important; line-height: 44px !important; margin-bottom: 8px !important; box-shadow: 0 15px 30px rgba(0,0,0,0.5) !important; font-weight: 900 !important; font-size: 18px !important; }
#         .leaflet-tooltip { background: #0b101a !important; color: white !important; border: 1px solid rgba(255,255,255,0.1) !important; border-radius: 8px !important; font-size: 10px !important; font-weight: 800 !important; box-shadow: 0 10px 20px rgba(0,0,0,0.5) !important; padding: 6px 10px !important; pointer-events: none; }
#         
#         /* Hide Default Routing Box */
#         .leaflet-routing-container { display: none !important; }

#         /* CRT Scanlines */
#         .scanlines {
#             background: linear-gradient(to bottom, rgba(255,255,255,0), rgba(255,255,255,0) 50%, rgba(0,0,0,0.2) 50%, rgba(0,0,0,0.2));
#             background-size: 100% 4px;
#         }

#         /* Shockwave Animations tied to Dynamic Color */
#         .shockwave-container { position: relative; width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; }
#         .sw-core { width: 12px; height: 12px; background: var(--dynamic-color); border-radius: 50%; box-shadow: 0 0 15px var(--dynamic-color); z-index: 10; transition: background 0.3s, box-shadow 0.3s; }
#         .sw-ring { position: absolute; width: 100%; height: 100%; border-radius: 50%; border: 2px solid var(--dynamic-color); opacity: 0; animation: ripple 3s linear infinite; transition: border-color 0.3s; }
#         .sw-delay-1 { animation-delay: 0s; } .sw-delay-2 { animation-delay: 1s; } .sw-delay-3 { animation-delay: 2s; }
#         @keyframes ripple { 0% { transform: scale(0.2); opacity: 1; border-width: 4px; } 100% { transform: scale(5); opacity: 0; border-width: 0px; } }
#         
#         .impact-circle-anim { animation: pulse-opacity 3s ease-in-out infinite alternate; }
#         @keyframes pulse-opacity { 0% { fill-opacity: 0.1; } 100% { fill-opacity: 0.25; } }

#         /* Range Slider Styling */
#         .range-slider { appearance: none; }
#         .range-slider::-webkit-slider-thumb {
#             appearance: none; width: 24px; height: 24px; border-radius: 50%;
#             background: var(--dynamic-color); cursor: pointer; border: 4px solid #121824;
#             box-shadow: 0 0 15px var(--dynamic-color); transition: 0.2s;
#         }
#         .range-slider::-webkit-slider-thumb:hover { transform: scale(1.2); }

#         /* Theme utility classes */
#         .theme-text { color: var(--dynamic-color); transition: color 0.3s ease; }
#         .theme-bg { background-color: var(--dynamic-color); transition: background-color 0.3s ease; }
#         .theme-border { border-color: var(--dynamic-color); transition: border-color 0.3s ease; }
#         .theme-gradient { background-image: linear-gradient(to bottom right, var(--dynamic-color), rgba(0,0,0,0.5)); transition: background-image 0.3s ease;}
#         
#         /* Safe Hospital Custom Marker */
#         .safe-hospital-marker { background:#27ae60; color:white; border-radius:50%; width:24px; height:24px; text-align:center; line-height:22px; font-weight:bold; border:2px solid white; box-shadow: 0 0 10px rgba(39,174,96,0.8); cursor: pointer;}
#     </style>
# </head>
# <body class="flex w-full h-screen overflow-hidden selection:bg-blue-500/30">

#     <!-- LEFT COMMAND PANEL -->
#     <div id="ui-theme-container" class="w-[420px] min-w-[420px] bg-[#0b101a]/95 border-r border-white/10 flex flex-col z-20 shadow-[0_0_50px_rgba(0,0,0,0.5)] backdrop-blur-2xl relative text-orange-500">
#         
#         <!-- Header -->
#         <div class="relative overflow-hidden p-7 bg-gradient-to-b from-white/5 to-transparent border-b border-white/5">
#             <div class="flex items-center gap-4">
#                 <div class="p-3 rounded-xl border border-white/10 shadow-[0_0_20px_rgba(0,0,0,0.3)] theme-gradient">
#                     <i class="fa-solid fa-radar text-white text-xl animate-[spin_4s_linear_infinite]"></i>
#                 </div>
#                 <div>
#                     <h1 class="text-xl font-black text-white tracking-tight leading-none uppercase drop-shadow-md">Tactical Command</h1>
#                     <p class="text-[10px] font-black uppercase tracking-[0.3em] mt-1 theme-text">Disaster Response Grid</p>
#                 </div>
#             </div>
#         </div>

#         <!-- Tab Selection -->
#         <div class="flex px-7 pt-4 gap-4">
#             <button id="tab-sim" class="flex-1 py-3 text-[10px] font-black uppercase tracking-widest border-b-2 theme-border text-white drop-shadow-[0_0_8px_rgba(255,255,255,0.5)] transition-all duration-300" onclick="window.switchTab('simulation')">Telemetry</button>
#             <button id="tab-ana" class="flex-1 py-3 text-[10px] font-black uppercase tracking-widest border-b-2 border-transparent text-slate-600 hover:text-slate-400 transition-all duration-300" onclick="window.switchTab('analytics')">Analytics</button>
#         </div>

#         <div class="flex-1 overflow-y-auto custom-scrollbar p-7 space-y-6">
#             
#             <!-- SIMULATION TAB -->
#             <div id="content-sim" class="space-y-6 transition-opacity duration-500">
#                 <!-- Controls -->
#                 <div class="bg-[#121824] p-6 rounded-2xl border border-white/5 shadow-inner relative overflow-hidden group">
#                     <div class="absolute top-0 left-0 w-1 h-full theme-bg"></div>
#                     
#                     <div class="flex justify-between items-center mb-4">
#                         <label class="text-[10px] font-black uppercase text-slate-400 tracking-[0.2em] flex items-center gap-2">
#                             <i class="fa-solid fa-wave-square theme-text"></i> Seismic Magnitude
#                         </label>
#                         <span class="text-2xl font-black theme-text drop-shadow-lg"><span id="mag-display">6.50</span> <small class="text-[10px] text-slate-500">Mw</small></span>
#                     </div>
#                     
#                     <input type="range" id="mag-slider" min="0.025" max="10" step="0.025" value="6.5" class="w-full h-1.5 bg-slate-800 rounded-lg cursor-pointer range-slider">

#                     <!-- Predicted Depth Grid Column -->
#                     <div class="grid grid-cols-3 gap-2 mt-6">
#                         <div class="bg-[#0b101a] p-3 rounded-xl border border-white/5 flex flex-col justify-center">
#                             <span class="text-[8px] text-slate-500 font-bold uppercase tracking-widest mb-1">Zone</span>
#                             <span class="text-sm font-black text-white"><span id="stat-radius">0</span> KM</span>
#                         </div>
#                         <div class="bg-[#0b101a] p-3 rounded-xl border border-white/5 flex flex-col justify-center">
#                             <span class="text-[8px] text-slate-500 font-bold uppercase tracking-widest mb-1">Depth (AI)</span>
#                             <span class="text-sm font-black text-blue-400"><span id="stat-depth">0</span> KM</span>
#                         </div>
#                         <div class="bg-[#0b101a] p-3 rounded-xl border border-white/5 flex flex-col justify-center">
#                             <span class="text-[8px] text-slate-500 font-bold uppercase tracking-widest mb-1">Sites</span>
#                             <span class="text-sm font-black theme-text" id="stat-sites">0</span>
#                         </div>
#                     </div>

#                     <button id="btn-analyze" onclick="window.runAnalysis()" class="w-full mt-5 py-4 rounded-xl font-black text-[11px] uppercase tracking-widest transition-all shadow-xl active:scale-95 theme-gradient text-white flex items-center justify-center gap-2">
#                         <i class="fa-solid fa-bolt"></i> <span id="btn-analyze-text">Engage Server Analysis</span>
#                     </button>
#                 </div>

#                 <!-- AI Report Container -->
#                 <div id="ai-report-container" class="hidden space-y-4">
#                     <div class="flex gap-4">
#                         <div class="flex-1 theme-gradient p-4 rounded-2xl shadow-lg border border-white/20 flex flex-col justify-between">
#                             <span class="text-[9px] font-black uppercase tracking-widest text-white/70">Threat Index</span>
#                             <div class="text-3xl font-black text-white drop-shadow-md mt-1" id="rep-intensity">0.0</div>
#                         </div>
#                         <div class="flex-[2] bg-[#121824] p-4 rounded-2xl border border-white/5 flex flex-col justify-center">
#                             <span class="text-[9px] font-black uppercase tracking-widest text-slate-500 mb-1">Classification</span>
#                             <span class="text-lg font-black uppercase theme-text" id="rep-risk">UNKNOWN</span>
#                         </div>
#                     </div>

#                     <div class="bg-[#121824] p-5 rounded-2xl border border-white/5 space-y-5 relative">
#                         <div>
#                             <h4 class="text-[9px] font-black uppercase tracking-widest text-slate-500 mb-2 flex items-center gap-1.5"><i class="fa-solid fa-bullseye text-blue-500"></i> Structural Assessment</h4>
#                             <p class="text-xs text-slate-200 font-medium bg-black/30 p-3 rounded-lg border border-white/5" id="rep-damage">No data.</p>
#                         </div>
#                         <div>
#                             <h4 class="text-[9px] font-black uppercase tracking-widest text-slate-500 mb-2 flex items-center gap-1.5"><i class="fa-solid fa-server text-purple-500"></i> Backend Synthesis</h4>
#                             <p class="text-xs text-slate-400 italic leading-relaxed" id="rep-assessment">Awaiting generation...</p>
#                         </div>

#                         <!-- Model Confidence Bar -->
#                         <div class="pt-4 border-t border-white/5 mt-4">
#                             <div style="display: flex; justify-content: space-between; font-size: 10px;" class="text-slate-400 uppercase font-black tracking-widest mb-1">
#                                 <span>Model Confidence</span>
#                                 <b id="accuracy-text" class="text-white">0%</b>
#                             </div>
#                             <div class="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
#                                 <div id="accuracy-bar" class="h-full bg-green-500 transition-all duration-1000 w-0"></div>
#                             </div>
#                         </div>
#                     </div>
#                 </div>

#                 <!-- Placeholder -->
#                 <div id="ai-placeholder" class="p-8 border border-dashed border-white/10 rounded-3xl flex flex-col items-center justify-center text-center opacity-40 grayscale select-none mt-8">
#                     <i class="fa-solid fa-crosshairs text-4xl mb-4 animate-[pulse_3s_ease-in-out_infinite]"></i>
#                     <p class="text-[10px] font-black uppercase tracking-[0.3em] text-white">Awaiting Target</p>
#                     <p class="text-[9px] mt-2 max-w-[200px] text-slate-400">Click coordinates on the satellite grid to initialize impact simulation.</p>
#                 </div>
#             </div>

#             <!-- ANALYTICS TAB -->
#             <div id="content-ana" class="hidden space-y-6 transition-opacity duration-500">
#                 <div class="bg-[#121824] p-6 rounded-2xl border border-white/5 shadow-lg">
#                     <h3 class="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-6 flex items-center gap-2">
#                         <i class="fa-solid fa-chart-pie theme-text"></i> Infrastructure Breakdown
#                     </h3>
#                     <div class="h-48 w-full relative">
#                         <canvas id="pieChart"></canvas>
#                     </div>
#                 </div>
#                 <div class="bg-[#121824] p-6 rounded-2xl border border-white/5 shadow-lg">
#                     <h3 class="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-6 flex items-center gap-2">
#                         <i class="fa-solid fa-chart-simple theme-text"></i> Bed Capacity Stress
#                     </h3>
#                     <div class="h-48 w-full relative">
#                         <canvas id="barChart"></canvas>
#                     </div>
#                 </div>
#             </div>
#         </div>

#         <!-- Footer Upload -->
#         <div class="p-6 border-t border-white/5 bg-[#0b101a] relative z-10">
#             <label class="flex items-center justify-center gap-3 w-full bg-[#121824] hover:bg-[#1a2233] text-white py-4 rounded-xl cursor-pointer transition-all text-[10px] font-black uppercase tracking-widest border border-white/10 active:scale-95 shadow-lg group" onclick="document.getElementById('geo-up').click()">
#                 <i class="fa-solid fa-upload text-blue-400 group-hover:-translate-y-1 transition-transform"></i>
#                 <span id="upload-text">Load Local GeoJSON</span>
#             </label>
#             <input type="file" id="geo-up" class="hidden" accept=".geojson" onchange="window.handleFileUpload(event)">
#         </div>
#     </div>

#     <!-- CENTER MAP VIEW -->
#     <div class="flex-1 relative bg-[#05080f]">
#         <!-- Effects -->
#         <div class="absolute inset-0 z-10 pointer-events-none scanlines opacity-30"></div>
#         <div class="absolute inset-0 z-10 pointer-events-none bg-blue-500/5 mix-blend-overlay"></div>

#         <div id="map" class="absolute inset-0 z-0" style="cursor: crosshair;"></div>
#         
#         <!-- Map Style Toggle Button -->
#         <button id="map-toggle-btn" onclick="window.toggleMapStyle()" class="absolute top-8 right-8 z-[1000] bg-[#1A1D23]/90 backdrop-blur-md border border-white/10 text-white p-4 rounded-xl shadow-2xl hover:bg-white/10 transition-colors" title="Switch to Street View">
#             <i class="fa-solid fa-map"></i>
#         </button>
#         
#         <!-- HUD -->
#         <div class="absolute top-8 left-8 right-[100px] z-20 flex justify-between items-start pointer-events-none">
#             <div class="bg-[#0b101a]/80 backdrop-blur-xl px-5 py-3 rounded-2xl border border-white/10 shadow-2xl flex items-center gap-3">
#                 <div class="w-2 h-2 rounded-full bg-blue-500 animate-pulse ring-4 ring-blue-500/20"></div>
#                 <p class="text-[10px] font-black uppercase tracking-[0.2em] text-blue-100">SAT-LINK: SECURE</p>
#             </div>
#             <div class="bg-[#0b101a]/80 backdrop-blur-xl px-5 py-3 rounded-2xl border border-white/10 text-white font-mono text-[11px] font-bold shadow-2xl flex items-center gap-2">
#                 <i class="fa-solid fa-satellite-dish text-slate-400"></i>
#                 LAT: <span id="hud-lat">---.----</span> <span class="text-slate-600 px-1">/</span> LNG: <span id="hud-lng">---.----</span>
#             </div>
#         </div>

#         <!-- ROUTING PANEL -->
#         <div id="routing-panel" class="hidden absolute top-28 right-8 w-[380px] z-[1000] bg-[#1A1D23]/95 backdrop-blur-2xl border border-[#2D333B] rounded-2xl shadow-2xl p-5 max-h-[60vh] overflow-y-auto custom-scrollbar">
#             <!-- Dynamically populated by JS -->
#         </div>

#         <!-- HOSPITAL DETAIL CARD -->
#         <div id="hospital-detail-card" class="hidden absolute bottom-24 right-8 w-[350px] z-[1000] bg-[#1A1D23]/95 backdrop-blur-2xl border border-[#2D333B] rounded-[32px] shadow-2xl p-8 transition-opacity duration-300">
#             <button onclick="window.closeHospitalCard()" class="absolute top-6 right-6 text-slate-500 hover:text-white transition-colors p-2 hover:bg-white/10 rounded-full">
#                 <i class="fa-solid fa-xmark"></i>
#             </button>
#             <h2 id="hosp-name" class="text-xl font-black text-white leading-tight pr-8 mb-1 tracking-tight">Facility Name</h2>
#             <p id="hosp-address" class="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-6 leading-relaxed">Address</p>
#             
#             <div class="grid grid-cols-2 gap-4 border-t border-[#2D333B] pt-6 mb-4">
#                 <div class="space-y-1">
#                     <p class="text-[9px] font-black text-slate-600 uppercase tracking-widest flex items-center gap-1.5"><i class="fa-solid fa-bed text-blue-500"></i> Beds</p>
#                     <p id="hosp-beds" class="text-base font-black text-white">0</p>
#                 </div>
#                 <div class="space-y-1">
#                     <p class="text-[9px] font-black text-slate-600 uppercase tracking-widest flex items-center gap-1.5"><i class="fa-solid fa-heart-pulse text-green-500"></i> Status</p>
#                     <p id="hosp-status" class="text-base font-black text-green-500 uppercase">UNKNOWN</p>
#                 </div>
#             </div>

#             <!-- Expanded details panel -->
#             <div class="space-y-2 border-t border-[#2D333B] pt-4">
#                 <div class="flex items-center justify-between text-xs py-1">
#                     <span class="text-slate-400 font-black uppercase tracking-widest text-[9px]"><i class="fa-solid fa-ruler"></i> Epicenter Dist</span>
#                     <span id="hosp-dist" class="font-bold text-orange-400 font-mono tracking-wider">-- km</span>
#                 </div>
#                 <div class="flex items-center justify-between text-xs py-1">
#                     <span class="text-slate-400 font-black uppercase tracking-widest text-[9px]">Class</span>
#                     <span id="hosp-type" class="font-bold text-slate-300 uppercase">General</span>
#                 </div>
#                 <div class="flex items-center justify-between text-xs py-1">
#                     <span class="text-slate-400 font-black uppercase tracking-widest text-[9px]">Contact</span>
#                     <span id="hosp-phone" class="font-bold text-slate-300">N/A</span>
#                 </div>
#                 <div class="flex items-start justify-between text-xs py-1 border-t border-white/5 mt-1 pt-2">
#                     <span class="text-slate-400 font-black uppercase tracking-widest text-[9px] mt-0.5">Facilities</span>
#                     <span id="hosp-facilities" class="font-bold text-slate-300 text-[10px] text-right w-2/3 leading-snug">N/A</span>
#                 </div>
#             </div>
#             
#             <button id="btn-calc-route" class="w-full mt-4 py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-black text-[10px] uppercase tracking-widest transition-all shadow-lg active:scale-95">
#                 <i class="fa-solid fa-route"></i> Calculate Safe Route
#             </button>
#         </div>

#         <!-- Global Status Bar -->
#         <div class="absolute bottom-10 left-1/2 -translate-x-1/2 z-10 flex items-center gap-4 bg-[#11141a]/95 backdrop-blur-xl text-white px-8 py-4 rounded-full text-[9px] font-black uppercase tracking-[0.3em] border border-white/10 shadow-[0_20px_50px_rgba(0,0,0,0.5)] pointer-events-none">
#             <i class="fa-solid fa-wave-square theme-text"></i> Seismic Monitoring Active
#             <i class="fa-solid fa-chevron-right text-slate-600"></i> Django ML Connected
#         </div>
#     </div>

#     <!-- JS Engine -->
#     <script>
#         window.toggleMapStyle = function() {
#             const btn = document.getElementById('map-toggle-btn');
#             if (currentMapStyle === 'satellite') {
#                 map.removeLayer(satelliteLayer);
#                 map.removeLayer(labelsLayer);
#                 map.addLayer(streetLayer);
#                 currentMapStyle = 'street';
#                 btn.innerHTML = '<i class="fa-solid fa-satellite"></i>'; 
#                 btn.title = "Switch to Satellite View";
#             } else {
#                 map.removeLayer(streetLayer);
#                 map.addLayer(satelliteLayer);
#                 map.addLayer(labelsLayer);
#                 currentMapStyle = 'satellite';
#                 btn.innerHTML = '<i class="fa-solid fa-map"></i>';
#                 btn.title = "Switch to Street View";
#             }
#         };

#         // Global variables
#         let map, satelliteLayer, labelsLayer, streetLayer;
#         let currentMapStyle = 'satellite';
#         let hospitalLayer, impactCircle, epicenterMarker;
#         let geojsonData = null;
#         let affectedHospitals = [];
#         let safeHospitals = []; 
#         let safeMarkers = []; 
#         let currentEpicenter = null;

#         // Routing variables
#         let routeControl = null;
#         let routeLayers = [];
#         let availableRoutes = [];

#         let pieChartInstance = null;
#         let barChartInstance = null;

#         // Initialize when DOM is ready
#         document.addEventListener('DOMContentLoaded', () => {
#             initMap();
#             initTheme(); // Set initial Green color
#             initThemeListeners();
#             initCharts();
#             loadDefaultGeoJSON(); // Default load
#         });

#         // --- Load Default GeoJSON ---
#         function loadDefaultGeoJSON() {
#             const uploadText = document.getElementById('upload-text');
#             if (uploadText) uploadText.innerText = "Loading Default Data...";
#             
#             fetch('/static/data/hospitals.geojson')
#                 .then(response => {
#                     if (!response.ok) throw new Error("File not found");
#                     return response.json();
#                 })
#                 .then(data => {
#                     geojsonData = data;
#                     renderDataOnMap();
#                     if (uploadText) uploadText.innerText = "Load Local GeoJSON";
#                 })
#                 .catch(err => {
#                     console.warn("Default GeoJSON not loaded:", err);
#                     if (uploadText) uploadText.innerText = "Load Local GeoJSON";
#                 });
#         }

#         // --- Map Initialization ---
#         function initMap() {
#             // Satellite Config
#             satelliteLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { attribution: 'Esri' });
#             labelsLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}');
#             
#             // Street View Config
#             streetLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '&copy; OpenStreetMap' });

#             map = L.map('map', {
#                 zoomControl: false,
#                 preferCanvas: true, // Required for leaflet-image to render SVGs
#                 layers: [satelliteLayer, labelsLayer],
#                 attributionControl: false
#             }).setView([37.0902, -95.7129], 4);

#             L.control.zoom({ position: 'bottomright' }).addTo(map);

#             map.on('click', (e) => {
#                 currentEpicenter = { lat: e.latlng.lat, lng: e.latlng.lng };
#                 document.getElementById('hud-lat').innerText = currentEpicenter.lat.toFixed(4);
#                 document.getElementById('hud-lng').innerText = currentEpicenter.lng.toFixed(4);
#                 updateImpactGraphics();
#                 hideAIReport();
#                 
#                 // Hide hospital detail & routing cards
#                 document.getElementById('hospital-detail-card').classList.add('hidden');
#                 document.getElementById('routing-panel').classList.add('hidden');
#                 
#                 if (routeControl && map) {
#                     try {
#                         map.removeControl(routeControl);
#                     } catch(err) {
#                         console.warn("Could not remove route control: ", err);
#                     }
#                 }
#                 if (routeLayers && map) {
#                     routeLayers.forEach(l => {
#                         try {
#                             map.removeLayer(l);
#                         } catch(err) {}
#                     });
#                 }
#             });
#         }

#         // --- Dynamic Theming based on Magnitude ---
#         function getThemeColor(mag) {
#             if (mag >= 7.5) return '#ef4444'; // Red
#             if (mag >= 5.5) return '#e87722'; // Orange
#             if (mag >= 2.51) return '#eab308'; // Yellow
#             return '#22c55e'; // Green
#         }

#         function initTheme() {
#             const slider = document.getElementById('mag-slider');
#             if(slider) {
#                 document.documentElement.style.setProperty('--dynamic-color', getThemeColor(parseFloat(slider.value)));
#             }
#         }

#         function initThemeListeners() {
#             const slider = document.getElementById('mag-slider');
#             if(!slider) return;
#             slider.addEventListener('input', (e) => {
#                 const mag = parseFloat(e.target.value);
#                 document.getElementById('mag-display').innerText = mag.toFixed(2);
#                 
#                 // Update CSS variable globally for instant color change
#                 const hexColor = getThemeColor(mag);
#                 document.documentElement.style.setProperty('--dynamic-color', hexColor);

#                 if (currentEpicenter) updateImpactGraphics();
#             });
#         }

#         // --- Visual Updates & Spatial Math ---
#         function updateImpactGraphics() {
#             if (!currentEpicenter) return;
#             const mag = parseFloat(document.getElementById('mag-slider').value);
#             const hexColor = getThemeColor(mag);
#             
#             // Visual Radius calculation
#             const radiusKm = Math.pow(10, (0.4 * mag - 1)) * 10;
#             animateValue('stat-radius', parseFloat(document.getElementById('stat-radius').innerText), radiusKm, 1000);

#             if (impactCircle) map.removeLayer(impactCircle);
#             if (epicenterMarker) map.removeLayer(epicenterMarker);

#             impactCircle = L.circle([currentEpicenter.lat, currentEpicenter.lng], {
#                 radius: radiusKm * 1000,
#                 color: hexColor, fillColor: hexColor, fillOpacity: 0.15,
#                 weight: 2, dashArray: '4, 12', className: 'impact-circle-anim'
#             }).addTo(map);

#             epicenterMarker = L.marker([currentEpicenter.lat, currentEpicenter.lng], {
#                 icon: L.divIcon({
#                     className: 'custom-div-icon',
#                     html: `<div class="shockwave-container">
#                              <div class="sw-core"></div><div class="sw-ring sw-delay-1"></div>
#                              <div class="sw-ring sw-delay-2"></div><div class="sw-ring sw-delay-3"></div>
#                            </div>`,
#                     iconSize: [40, 40], iconAnchor: [20, 20]
#                 })
#             }).addTo(map);

#             // Client-side quick filter
#             if (geojsonData) {
#                 affectedHospitals = [];
#                 safeHospitals = [];
#                 geojsonData.features.forEach(f => {
#                     const [lng, lat] = f.geometry.coordinates;
#                     const dist = map.distance([lat, lng], [currentEpicenter.lat, currentEpicenter.lng]) / 1000;
#                     f.properties.computedDist = dist; // store for sorting
#                     
#                     if (dist <= radiusKm) affectedHospitals.push(f.properties);
#                     else safeHospitals.push(f.properties);
#                 });
#                 animateValue('stat-sites', parseInt(document.getElementById('stat-sites').innerText), affectedHospitals.length, 1000);
#                 updateCharts();
#             }
#         }

#         // --- Data Loading ---
#         window.handleFileUpload = function(e) {
#             const file = e.target.files[0];
#             if (!file) return;
#             document.getElementById('upload-text').innerText = "Processing...";
#             const reader = new FileReader();
#             reader.onload = (ev) => {
#                 try {
#                     geojsonData = JSON.parse(ev.target.result);
#                     renderDataOnMap();
#                     document.getElementById('upload-text').innerText = "Data Loaded Successfully";
#                     setTimeout(() => document.getElementById('upload-text').innerText = "Load Local GeoJSON", 3000);
#                 } catch(err) {
#                     alert("Invalid GeoJSON file.");
#                     document.getElementById('upload-text').innerText = "Load Local GeoJSON";
#                 }
#             };
#             reader.readAsText(file);
#         };

#         function renderDataOnMap() {
#             if (hospitalLayer) map.removeLayer(hospitalLayer);
#             hospitalLayer = L.geoJSON(geojsonData, {
#                 pointToLayer: (feat, latlng) => L.circleMarker(latlng, {
#                     radius: 3, fillColor: "#22c55e", color: "#000", weight: 1, opacity: 0.8, fillOpacity: 0.8
#                 }),
#                 onEachFeature: (feature, layer) => {
#                     layer.on('click', (e) => {
#                         L.DomEvent.stopPropagation(e);
#                         showHospitalCard(feature.properties, layer.getLatLng().lat, layer.getLatLng().lng);
#                     });
#                 }
#             }).addTo(map);
#         }
#         
#         function showHospitalCard(p, lat, lng) {
#             let distText = "Epicenter not set";
#             if (currentEpicenter) {
#                 const distKm = (map.distance([lat, lng], [currentEpicenter.lat, currentEpicenter.lng]) / 1000).toFixed(2);
#                 distText = `${distKm} km from epicenter`;
#             }

#             document.getElementById('hosp-name').innerText = p.NAME || 'Unknown Facility';
#             document.getElementById('hosp-address').innerText = `${p.ADDRESS || ''}, ${p.CITY || ''}`;
#             document.getElementById('hosp-beds').innerText = p.BEDS === -999 ? "N/A" : p.BEDS;
#             document.getElementById('hosp-status').innerText = p.STATUS || "UNKNOWN";
#             document.getElementById('hosp-type').innerText = p.TYPE || "UNKNOWN";
#             document.getElementById('hosp-phone').innerText = p.TELEPHONE || "N/A";
#             document.getElementById('hosp-dist').innerText = distText;

#             let facilities = p.FACILITIES || p.facilities || "Basic/Not Specified";
#             if (Array.isArray(facilities)) facilities = facilities.join(', ');
#             let facEl = document.getElementById('hosp-facilities');
#             if (facEl) facEl.innerText = facilities;

#             // Wire up routing button
#             const routeBtn = document.getElementById('btn-calc-route');
#             if(routeBtn) {
#                 routeBtn.onclick = () => window.analyzeRouteToHospital(p.NAME || 'Facility', lat, lng, p.BEDS, p.TYPE);
#             }

#             // MODIFICATION: Hide the routing panel if it was open, and show the hospital card
#             document.getElementById('routing-panel').classList.add('hidden');
#             document.getElementById('hospital-detail-card').classList.remove('hidden');
#         }

#         window.closeHospitalCard = function() {
#             document.getElementById('hospital-detail-card').classList.add('hidden');
#         };

#         // --- Backend API Call to views.py ---
#         window.runAnalysis = async function() {
#             if (!currentEpicenter) return alert("Select an epicenter on the map first.");
#             
#             const mag = document.getElementById('mag-slider').value;
#             const btnText = document.getElementById('btn-analyze-text');
#             const icon = document.querySelector('#btn-analyze i');
#             
#             btnText.innerText = "Transmitting to Django Engine...";
#             icon.className = "fa-solid fa-spinner fa-spin";
#             
#             try {
#                 const url = `/nearest_history/?lat=${currentEpicenter.lat}&lng=${currentEpicenter.lng}&mag=${mag}`;
#                 let data;
#                 /* --- Find window.runAnalysis (Around Line 580) --- */
#                 try {
#                     const response = await fetch(url);
#                     data = await response.json();
#                 } catch(e) {
#                     console.warn("Django backend unreachable. Falling back to mock data.");
#                     const radiusKm = Math.pow(10, (0.4 * mag - 1)) * 10;
#                     
#                     // --- ✨ PERFECT M.L. CONFIDENCE FALLBACK (JS version) ✨ ---
#                     // Parameter 1: Magnitude Anomaly (Outliers > 6.5 lose confidence)
#                     let mag_penalty = Math.max(0, (mag - 6.5) * 5); 
#                     
#                     // Parameter 2: Geographic Uncertainty (Simulated)
#                     let geo_penalty = 10 + (Math.random() * 10); 
#                     
#                     // Parameter 3: Sensor Quality (Simulated high-quality telemetry)
#                     let telemetry_penalty = 5.0; 

#                     let raw_confidence = 100.0 - mag_penalty - geo_penalty - telemetry_penalty;
#                     let dynamicConfidence = Math.max(15.0, Math.min(99.5, raw_confidence));
#                     // ---------------------------------------------------------

#                     data = {
#                         intensity: (parseFloat(mag) * 1.15).toFixed(2),
#                         risk_level: mag >= 7.5 ? 'CRITICAL' : mag >= 5.5 ? 'HIGH' : mag >= 2.51 ? 'MODERATE' : 'LOW',
#                         expected_damage: 'Simulation mode active. Structural concerns mapped to historical averages.',
#                         assessment: `Earthquake of magnitude ${mag} is predicted to cause ${mag >= 5.5 ? 'severe' : 'manageable'} damage potential.`,
#                         confidence: dynamicConfidence, // ✅ This now uses the perfect calculation
#                         radius: radiusKm,
#                         depth: (Math.random() * 50 + 5).toFixed(1)
#                     };
#                 }
#                 if(data.error) throw new Error(data.error);

#                 // Display ML Results
#                 document.getElementById('ai-placeholder').classList.add('hidden');
#                 document.getElementById('ai-report-container').classList.remove('hidden');

#                 animateValue('rep-intensity', 0, parseFloat(data.intensity), 1500, 2);
#                 
#                 const depthEl = document.getElementById('stat-depth');
#                 if(depthEl) animateValue('stat-depth', 0, parseFloat(data.depth), 1000, 1);
#                 
#                 document.getElementById('rep-risk').innerText = data.risk_level;
#                 document.getElementById('rep-damage').innerText = data.expected_damage;
#                 document.getElementById('rep-assessment').innerText = data.assessment;
#                 
#                 let confBar = document.getElementById('accuracy-bar');
#                 if(confBar) confBar.style.width = (data.confidence || 80) + "%";
#                 let confText = document.getElementById('accuracy-text');
#                 if(confText) confText.innerText = Math.round(data.confidence || 80) + "%";

#                 if (data.affected_hospitals) {
#                     affectedHospitals = data.affected_hospitals;
#                     animateValue('stat-sites', 0, affectedHospitals.length, 1000);
#                     updateCharts();
#                 }

#                 safeMarkers.forEach(m => map.removeLayer(m));
#                 safeMarkers = [];
#                 
#                 if (safeHospitals.length > 0 && geojsonData) {
#                     safeHospitals.sort((a, b) => a.computedDist - b.computedDist);
#                     const top5Safe = safeHospitals.slice(0, 5);
#                     
#                     top5Safe.forEach(h => {
#                         const feature = geojsonData.features.find(f => f.properties.NAME === h.NAME);
#                         if (!feature) return;
#                         const [hLng, hLat] = feature.geometry.coordinates;

#                         let icon = L.divIcon({ html: '+', className: 'safe-hospital-marker', iconSize: [24,24] });
#                         let m = L.marker([hLat, hLng], { icon: icon }).addTo(map);
#                         
#                         m.on('click', (e) => {
#                             L.DomEvent.stopPropagation(e);
#                             showHospitalCard(h, hLat, hLng);
#                         });
#                         safeMarkers.push(m);
#                     });
#                     
#                     const nearestSafe = top5Safe[0];
#                     const nf = geojsonData.features.find(f => f.properties.NAME === nearestSafe.NAME);
#                     if(nf) {
#                         showHospitalCard(nearestSafe, nf.geometry.coordinates[1], nf.geometry.coordinates[0]);
#                     }
#                 }

#             } catch (err) {
#                 alert("Backend Error: " + err.message);
#             } finally {
#                 btnText.innerText = "Engage Server Analysis";
#                 icon.className = "fa-solid fa-bolt";
#             }
#         };

#         function hideAIReport() {
#             document.getElementById('ai-placeholder').classList.remove('hidden');
#             document.getElementById('ai-report-container').classList.add('hidden');
#         }

#         async function getWeatherAt(lat, lng) {
#             try {
#                 let res = await fetch(`/get_weather_proxy/?lat=${lat}&lng=${lng}`);
#                 let json = await res.json();
#                 if (json && json.weather && json.weather[0]) return { cond: json.weather[0].main };
#             } catch(e) { /* ignore */ }
#             return { cond: "Clear" };
#         }

#         // ✅ ADDED: Road Damage Classification Logic
#         function classifyRoadDamage(mag, distKm) {
#             const radiusKm = Math.pow(10, (0.4 * mag - 1)) * 10;
#             if (distKm <= radiusKm * 0.25) return "critical";
#             if (distKm <= radiusKm * 0.6) return "severe";
#             if (distKm <= radiusKm) return "moderate";
#             return "none";
#         }

#         window.analyzeRouteToHospital = async function(hName, hLat, hLng, hBeds, hType) {
#             if (!currentEpicenter) return;
#             
#             if (routeControl && map) {
#                 try { map.removeControl(routeControl); } catch(err) {}
#             }
#             if (routeLayers && map) {
#                 routeLayers.forEach(l => { try { map.removeLayer(l); } catch(err) {} });
#             }
#             routeLayers = [];
#             availableRoutes = [];
#             
#             const panel = document.getElementById('routing-panel');
#             if(!panel) return;

#             // MODIFICATION: Hide the hospital card, and show the routing panel
#             document.getElementById('hospital-detail-card').classList.add('hidden');
#             panel.classList.remove('hidden');
#             
#             panel.innerHTML = `<div class="p-6 text-center text-slate-400 font-bold tracking-widest uppercase text-[10px]">
#                 <i class="fa-solid fa-spinner fa-spin text-2xl mb-3 text-blue-500"></i><br>Calculating routes...
#             </div>`;

#             routeControl = L.Routing.control({
#                 waypoints: [L.latLng(currentEpicenter.lat, currentEpicenter.lng), L.latLng(hLat, hLng)],
#                 show: false, alternatives: true, addWaypoints: false, 
#                 lineOptions: { styles: [{ opacity: 0 }] },
#                 altLineOptions: { styles: [{ opacity: 0 }] },
#                 createMarker: function() { return null; },
#                 router: L.Routing.osrmv1({ serviceUrl: "https://router.project-osrm.org/route/v1", profile: "driving" })
#             }).addTo(map);

#             // MODIFICATION: Handle Routing Errors to prevent "Stuck" spinner
#             routeControl.on('routingerror', function(e) {
#                 panel.innerHTML = `<div class="p-6 text-center text-red-400 font-bold tracking-widest uppercase text-[10px]">
#                     <i class="fa-solid fa-triangle-exclamation text-2xl mb-3 text-red-500"></i><br>Routing Engine Failed.<br>Distance too large or network error.
#                 </div>`;
#             });

#             routeControl.on('routesfound', async function(e) {
#                 let routes = Array.from(e.routes || []);
#                 
#                 // --- MODIFICATION 1: Widen the alternative routes so they escape the danger zone ---
#                 if (routes.length > 0 && routes.length < 3) {
#                     let baseRoute = routes[0];
#                     let numToAdd = 3 - routes.length;
#                     for (let k = 1; k <= numToAdd; k++) {
#                         let altCoords = baseRoute.coordinates.map((pt, idx) => {
#                             let percent = idx / baseRoute.coordinates.length;
#                             let curve = Math.sin(percent * Math.PI); 
#                             // INCREASED spread from 0.08 to 0.15 to push routes further away from epicenter
#                             let offsetDeg = (k % 2 === 0 ? -1 : 1) * 0.15 * k * curve; 
#                             return { lat: pt.lat + offsetDeg, lng: pt.lng + offsetDeg }; 
#                         });
#                         
#                         routes.push({
#                             coordinates: altCoords,
#                             summary: {
#                                 totalDistance: baseRoute.summary.totalDistance * (1 + (0.08 * k)), 
#                                 totalTime: baseRoute.summary.totalTime * (1 + (0.15 * k)) 
#                             }
#                         });
#                     }
#                 }

#                 if (routes.length === 0) {
#                     panel.innerHTML = `<div class="p-6 text-center text-slate-400 font-bold tracking-widest uppercase text-[10px]">No valid routes found.</div>`;
#                     return;
#                 }

#                 let bestIndex = 0, bestScore = -Infinity;
#                 let html = `<h4 class="text-xs font-black uppercase tracking-widest text-white mb-4 border-b border-white/10 pb-2">Evacuation Routes</h4>`;
#                 
#                 for(let i=0; i<routes.length; i++) {
#                     let r = routes[i];
#                     let distKm = r.summary ? (r.summary.totalDistance / 1000).toFixed(1) : "0.0";
#                     let timeMin = r.summary ? Math.round(r.summary.totalTime / 60) : 0;
#                     
#                     let wMid = { cond: "Clear" };
#                     let closestDistToEpicenter = Infinity;
#                     let totalDistToEpicenter = 0;

#                     if (r.coordinates && r.coordinates.length > 0) {
#                         let midPt = r.coordinates[Math.floor(r.coordinates.length / 2)];
#                         wMid = await getWeatherAt(midPt.lat, midPt.lng);
#                         
#                         // --- MODIFICATION 2: Scan EVERY coordinate to find closest approach and average distance ---
#                         r.coordinates.forEach(pt => {
#                             let d = map.distance([pt.lat, pt.lng], [currentEpicenter.lat, currentEpicenter.lng]) / 1000;
#                             if (d < closestDistToEpicenter) closestDistToEpicenter = d;
#                             totalDistToEpicenter += d;
#                         });
#                     }

#                     // Average distance helps break ties between multiple "Unsafe" routes
#                     let avgDistToEpicenter = r.coordinates.length > 0 ? (totalDistToEpicenter / r.coordinates.length) : 0;

#                     let mag = parseFloat(document.getElementById('mag-slider').value);
#                     // Classify damage based on the WORST part of the road (closest to epicenter)
#                     let roadDamage = classifyRoadDamage(mag, closestDistToEpicenter);
#                     
#                     let badWeather = ['Rain','Snow','Thunderstorm','Mist'];
#                     let weatherRisk = badWeather.includes(wMid.cond);
#                     
#                     let damagePenalty = 0;
#                     if (roadDamage === "critical") damagePenalty = 10000; 
#                     else if (roadDamage === "severe") damagePenalty = 5000;
#                     else if (roadDamage === "moderate") damagePenalty = 2000;

#                     // --- MODIFICATION 3: Add Average Distance to the score ---
#                     // Even if all 3 routes are unsafe, the one that stays furthest away overall gets the highest score!
#                     let score = 100 - parseFloat(distKm) - damagePenalty - (weatherRisk ? 1000 : 0) + (avgDistToEpicenter * 2);
#                     
#                     let status = "SAFE";
#                     let reason = wMid.cond;
#                     let routeColor = '#22c55e'; // Green
#                     let statusColorClass = 'text-green-500';
#                     let badgeBgClass = 'bg-green-500/20 border border-green-500/50';
#                     let iconClass = 'fa-check-circle';

#                     if (roadDamage === "critical" || roadDamage === "severe" || wMid.cond === 'Thunderstorm' || wMid.cond === 'Snow') {
#                         status = "UNSAFE";
#                         routeColor = '#ef4444'; // Red
#                         statusColorClass = 'text-red-500';
#                         badgeBgClass = 'bg-red-500/20 border border-red-500/50';
#                         iconClass = 'fa-ban';
#                         if (roadDamage === "critical") reason = `Critical Damage + ${wMid.cond}`;
#                         else if (roadDamage === "severe") reason = `Severe Damage + ${wMid.cond}`;
#                         else reason = `Hazardous Weather (${wMid.cond})`;
#                     } else if (roadDamage === "moderate" || wMid.cond === 'Rain' || wMid.cond === 'Mist') {
#                         status = "DAMAGED";
#                         routeColor = '#e87722'; // Orange
#                         statusColorClass = 'text-orange-500';
#                         badgeBgClass = 'bg-orange-500/20 border border-orange-500/50';
#                         iconClass = 'fa-triangle-exclamation';
#                         if (roadDamage === "moderate") reason = `Moderate Damage + ${wMid.cond}`;
#                         else reason = `Poor Conditions (${wMid.cond})`;
#                     }

#                     availableRoutes.push({ 
#                         coordinates: r.coordinates, 
#                         status: status,
#                         reason: reason,
#                         routeColor: routeColor,
#                         statusColorClass: statusColorClass,
#                         badgeBgClass: badgeBgClass,
#                         iconClass: iconClass,
#                         weather: wMid.cond, 
#                         dist: distKm, 
#                         time: timeMin,
#                         score: score,
#                         originalStatus: status // Store original status
#                     });

#                     if(score > bestScore) { bestScore = score; bestIndex = i; }
#                 }
#                 
#                 availableRoutes.forEach((route, i) => {
#                     let escHName = (hName || "").replace(/'/g, "\\'");
#                     let mag = document.getElementById('mag-slider').value;
#                     let distFromClick = document.getElementById('hosp-dist').innerText;

#                     let isBest = (i === bestIndex);
#                     let highlightBorder = isBest ? `border-blue-500 shadow-[0_0_15px_rgba(59,130,246,0.5)]` : "border-white/5 opacity-80";
#                     let bestLabel = isBest ? " <span class='text-blue-400'>(BEST)</span>" : "";

#                     // --- MODIFICATION 4: Safest Route Override ---
#                     // If the best route is technically Unsafe/Damaged, turn it Blue and label it "SAFEST OPTION"
#                     let displayStatus = route.status;
#                     let displayColorClass = route.statusColorClass;
#                     let displayBadgeClass = route.badgeBgClass;

#                     if (isBest && route.originalStatus !== "SAFE") {
#                         displayStatus = "SAFEST OPTION";
#                         displayColorClass = "text-blue-400";
#                         displayBadgeClass = "bg-blue-900/30 border border-blue-500/50";
#                         route.routeColor = "#3b82f6"; // Make the polyline on the map blue
#                     }

#                     html += `
#                     <div id="route-card-${i}" onclick="window.drawRoute(${i})" class="bg-[#0b101a] border ${highlightBorder} rounded-xl p-4 mb-3 cursor-pointer hover:border-blue-500 transition-all shadow-lg">
#                         <div class="flex justify-between items-center mb-2">
#                             <span class="text-[11px] font-black text-white uppercase tracking-widest">Route ${i+1}${bestLabel}</span>
#                             <span class="text-[9px] font-black uppercase ${displayColorClass} ${displayBadgeClass} px-2 py-1 rounded"><i class="fa-solid ${route.iconClass}"></i> ${displayStatus}</span>
#                         </div>
#                         <div class="text-[10px] font-bold text-slate-500 mb-2 uppercase tracking-wide">
#                             ↳ ${route.reason}
#                         </div>
#                         <div class="text-xs font-medium text-slate-400 mb-3 border-b border-white/5 pb-3">
#                             <span class="text-white font-bold text-sm">${route.dist} km</span> &nbsp;•&nbsp; ${route.time} min
#                         </div>
#                         <button onclick="event.stopPropagation(); window.triggerReport(${i}, '${escHName}', '${currentEpicenter.lat}', '${currentEpicenter.lng}', '${mag}', '${distFromClick}', '${hType}', '${hBeds}', '${hLat}', '${hLng}')" class="w-full py-2 bg-slate-600 hover:bg-red-500 text-white rounded-lg text-[9px] font-black uppercase tracking-widest transition-all">
#                             <i class="fa-solid fa-file-pdf "></i> Download Safety Report
#                         </button>
#                     </div>`;
#                 });
#                 
#                 panel.innerHTML = html;
#                 window.drawRoute(bestIndex);
#             });           
#         };

#         window.drawRoute = function(selectedIndex) {
#             if (!Array.isArray(availableRoutes) || !availableRoutes[selectedIndex]) return;
#             
#             if (routeLayers && map) {
#                 routeLayers.forEach(l => { try { map.removeLayer(l); } catch(err) {} });
#             }
#             routeLayers = [];

#             availableRoutes.forEach((route, index) => {
#                 let isSelected = (index === selectedIndex);
#                 let color = isSelected ? route.routeColor : '#64748b'; // MODIFICATION: Use dynamic risk color
#                 let weight = isSelected ? 6 : 4;
#                 let opacity = isSelected ? 1.0 : 0.4;
#                 let dashArray = isSelected ? null : '10,10';

#                 let polyline = L.polyline(route.coordinates, {
#                     color: color, weight: weight, opacity: opacity,
#                     dashArray: dashArray, lineCap: 'round', interactive: false
#                 }).addTo(map);

#                 if (!isSelected) polyline.bringToBack();
#                 else polyline.bringToFront();
#                 routeLayers.push(polyline);

#                 let card = document.getElementById('route-card-' + index);
#                 if (card) {
#                     if (isSelected) {
#                         card.style.borderColor = color;
#                         card.style.backgroundColor = '#121824';
#                         card.style.opacity = '1';
#                     } else {
#                         card.style.borderColor = 'rgba(255,255,255,0.05)';
#                         card.style.backgroundColor = '#0b101a';
#                         card.style.opacity = '0.8';
#                     }
#                 }
#             });

#             let selectedPoly = L.polyline(availableRoutes[selectedIndex].coordinates);
#             try { map.fitBounds(selectedPoly.getBounds(), { padding: [50, 50] }); } catch (e) {}
#         };

#         window.triggerReport = function(routeIndex, hName, placeLat, placeLng, mag, dataDist, hType, hBeds, hLat, hLng) {
#             let route = availableRoutes[routeIndex];
#             if (!route) return;

#             let hidden = [];
#             map.eachLayer(function(layer) {
#                 try {
#                     let isWeatherTile = layer instanceof L.TileLayer && layer._url && layer._url.includes('openweathermap');
#                     let isMarker = layer instanceof L.Marker || layer instanceof L.CircleMarker;
#                     if (isWeatherTile || isMarker) { hidden.push(layer); map.removeLayer(layer); }
#                 } catch (e) {}
#             });

#             function submitForm(mapImageData) {
#                 let form = document.createElement('form');
#                 form.method = 'POST';
#                 form.action = '/report/';
#                 form.target = '_blank';
#                 
#                 let intensityEl = document.getElementById('rep-intensity');
#                 let depthEl = document.getElementById('stat-depth');
#                 let confEl = document.getElementById('accuracy-text'); // ✅ GRAB CONFIDENCE FROM UI
#                 
#                 let params = {
#                     map_image: mapImageData || "",
#                     place: `Lat: ${parseFloat(placeLat).toFixed(2)}, Lng: ${parseFloat(placeLng).toFixed(2)}`,
#                     mag: mag,
#                     dist_from_click: dataDist.replace(' km from epicenter', ''),
#                     hname: hName,
#                     dist: route.dist || "",
#                     weather: route.weather || "",
#                     hlat: hLat,
#                     hlng: hLng,
#                     intensity: intensityEl ? intensityEl.innerText : "0.0",
#                     depth: depthEl ? depthEl.innerText : "0.0",
#                     confidence: confEl ? confEl.innerText : "0%"     // ✅ SEND IT TO DJANGO
#                 };
#                 
#                 for (let k in params) {
#                     let i = document.createElement('input');
#                     i.type = 'hidden';
#                     i.name = k;
#                     i.value = params[k];
#                     form.appendChild(i);
#                 }
#                 document.body.appendChild(form);
#                 form.submit();
#                 document.body.removeChild(form);
#             }

#             function restoreHidden() { hidden.forEach(l => { try { l.addTo(map); } catch(e){} }); }

#             if (typeof leafletImage !== 'undefined') {
#                 try {
#                     leafletImage(map, function(err, canvas) {
#                         restoreHidden();
#                         if (err || !canvas) return submitForm("");
#                         // MODIFICATION: Convert to JPEG to prevent RequestDataTooBig crash
#                         try { submitForm(canvas.toDataURL('image/jpeg', 0.4)); } 
#                         catch (e) { submitForm(""); }
#                     });
#                 } catch (e) {
#                     restoreHidden();
#                     submitForm("");
#                 }
#             } else {
#                 restoreHidden();
#                 submitForm("");
#             }
#         };

#         window.switchTab = function(tab) {
#             const tabSim = document.getElementById('tab-sim');
#             const tabAna = document.getElementById('tab-ana');
#             
#             if (tab === 'simulation') {
#                 tabSim.classList.replace('border-transparent', 'theme-border');
#                 tabSim.classList.add('text-white', 'drop-shadow-[0_0_8px_rgba(255,255,255,0.5)]');
#                 tabSim.classList.remove('text-slate-600');
#                 
#                 tabAna.classList.replace('theme-border', 'border-transparent');
#                 tabAna.classList.remove('text-white', 'drop-shadow-[0_0_8px_rgba(255,255,255,0.5)]');
#                 tabAna.classList.add('text-slate-600');
#             } else {
#                 tabAna.classList.replace('border-transparent', 'theme-border');
#                 tabAna.classList.add('text-white', 'drop-shadow-[0_0_8px_rgba(255,255,255,0.5)]');
#                 tabAna.classList.remove('text-slate-600');
#                 
#                 tabSim.classList.replace('theme-border', 'border-transparent');
#                 tabSim.classList.remove('text-white', 'drop-shadow-[0_0_8px_rgba(255,255,255,0.5)]');
#                 tabSim.classList.add('text-slate-600');
#             }

#             document.getElementById('content-sim').style.display = tab === 'simulation' ? 'block' : 'none';
#             document.getElementById('content-ana').style.display = tab === 'analytics' ? 'block' : 'none';
#             
#             if (tab === 'analytics') updateCharts();
#         };

#         function initCharts() {
#             Chart.defaults.color = '#94a3b8';
#             Chart.defaults.font.family = "'Segoe UI', sans-serif";

#             pieChartInstance = new Chart(document.getElementById('pieChart'), {
#                 type: 'doughnut',
#                 data: { labels: [], datasets: [{ data: [], backgroundColor: ['#ef4444', '#e87722', '#eab308', '#3b82f6', '#a855f7'], borderWidth: 0 }] },
#                 options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right', labels: { boxWidth: 10, font: {size: 9} } } } }
#             });

#             barChartInstance = new Chart(document.getElementById('barChart'), {
#                 type: 'bar',
#                 data: { labels: [], datasets: [{ label: 'Beds', data: [], backgroundColor: '#3b82f6', borderRadius: 4 }] },
#                 options: { responsive: true, maintainAspectRatio: false, scales: { x: { display: false }, y: { beginAtZero: true, grid: { color: '#ffffff10' } } }, plugins: { legend: { display: false } } }
#             });
#         }

#         function updateCharts() {
#             if (!pieChartInstance || !barChartInstance) return;
#             
#             const typeCounts = {};
#             affectedHospitals.forEach(h => {
#                 const type = h.TYPE || h.type || 'Unknown';
#                 typeCounts[type] = (typeCounts[type] || 0) + 1;
#             });
#             pieChartInstance.data.labels = Object.keys(typeCounts);
#             pieChartInstance.data.datasets[0].data = Object.values(typeCounts);
#             pieChartInstance.update();

#             const topHospitals = [...affectedHospitals].sort((a, b) => (b.BEDS || b.beds || 0) - (a.BEDS || a.beds || 0)).slice(0, 5);
#             barChartInstance.data.labels = topHospitals.map(h => h.NAME || h.name || 'Hospital');
#             barChartInstance.data.datasets[0].data = topHospitals.map(h => h.BEDS || h.beds || 0);
#             
#             const mag = parseFloat(document.getElementById('mag-slider').value);
#             barChartInstance.data.datasets[0].backgroundColor = getThemeColor(mag);
#             barChartInstance.update();
#         }

#         function animateValue(id, start, end, duration, decimals = 0) {
#             const obj = document.getElementById(id);
#             if (!obj) return;
#             let startTimestamp = null;
#             const step = (timestamp) => {
#                 if (!startTimestamp) startTimestamp = timestamp;
#                 const progress = Math.min((timestamp - startTimestamp) / duration, 1);
#                 const ease = 1 - Math.pow(1 - progress, 4); // easeOutQuart
#                 const current = start + (end - start) * ease;
#                 obj.innerText = current.toFixed(decimals);
#                 if (progress < 1) window.requestAnimationFrame(step);
#             };
#             window.requestAnimationFrame(step);
#         }
#     </script>
# </body>
# </html>



# 1)solve this error why it clicks outside USA map like in canada mexicoas you see in above, fix it 

# 2) i want only clickable onside inside US map like man USA map , alaska map hawaai area etc 

# 3) and why routing error occur i want that when the magnitude is <=5 then calculate only safe unsafe or damaged route but more check and suggest only safe route 

# 4) if magnitude is above 5 then find the unsafe damaged and at least 1 safest options