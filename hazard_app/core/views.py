import folium
from folium.plugins import MarkerCluster
from django.shortcuts import render
from django.http import JsonResponse
from typing import Dict

from .services import (
    load_hospitals,
    load_earthquakes,
    predict_hospital_load,
    ai_risk_classification,
    
)
from .utils import haversine

# impact_radius,
#     magnitude_color,
# -------------------------------------------------------
# MAIN MAP RENDER FUNCTION
# -------------------------------------------------------

def render_map(params: Dict):

    # Default center: USA centroid
    center_lat = float(params.get("lat", 39.8283))
    center_lon = float(params.get("lon", -98.5795))

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=5,
        control_scale=True
    )

    hospitals = load_hospitals()
    earthquakes = load_earthquakes()

    cluster = MarkerCluster(name="Hospitals").add_to(m)

    # -------------------------------------------------------
    # HOSPITAL LAYER
    # -------------------------------------------------------

    for hospital in hospitals:

        hospital_color = "green"
        predicted_load = 0
        risk_level = "LOW"

        # Determine if hospital lies within any  impact zone
        for eq in earthquakes:
            dist = haversine(
                hospital["lat"],    
                hospital["lon"],
                eq["lat"],
                eq["lon"],
            )

        # Custom hospital icon
        icon_url = "https://cdn-icons-png.flaticon.com/512/2967/2967350.png"

        facilities_html = "".join(
            f"<li>{facility}</li>"
            for facility in hospital["facilities"]
        )

        popup_html = f"""
        <div style="width:320px;font-family:Arial;">
            <h3 style="color:{hospital_color};">
                {'🚨 At Risk Hospital' if hospital_color=='red' else '✅ Safe Hospital'}
            </h3>

            <b>Name:</b> {hospital['name']}<br>
            <b>City:</b> {hospital['city']}, {hospital['state']}<br>
            <b>Beds:</b> {hospital['beds']}<br>
            <b>Predicted Load:</b> {predicted_load}%<br>
            <b>AI Risk Level:</b>
            <span style="font-weight:bold;color:red;">
                {risk_level}
            </span>

            <hr>

            <b>Facilities:</b>
            <ul style="max-height:140px;overflow:auto;">
                {facilities_html}
            </ul>
        </div>
        """

        folium.Marker(
            location=[hospital["lat"], hospital["lon"]],
            popup=folium.Popup(popup_html, max_width=350),
            icon=folium.CustomIcon(icon_url, icon_size=(30, 30))
        ).add_to(cluster)

    # # -------------------------------------------------------
    # # LEGEND BOX
    # # -------------------------------------------------------

    # legend_html = """
    # <div style="
    #     position: absolute;
    #     top: 140px;
    #     left: 40px;
    #     width: 260px;
    #     background-color: white;
    #     border: 2px solid grey;
    #     z-index: 9999;
    #     font-size: 14px;
    #     padding: 12px;
    #     box-shadow: 2px 2px 6px rgba(0,0,0,0.3);
    # ">
    # <b>Hazard Legend</b><br><br>

    # 🔴 Red Hospital → Inside Impact Zone<br>
    # 🟢 Green Hospital → Safe<br><br>

    # 🟡 Yellow Circle → Minor(Mag < 4)<br>
    # 🟠 Orange Circle → Moderate(Mag 4–5)<br>
    # 🔴 Red Circle → Strong(Mag 5–6)<br>
    # 🔥 Dark Red Circle → Severe(Mag ≥ 6)<br><br>
    # </div>
    # """

    # m.get_root().html.add_child(folium.Element(legend_html))

    folium.LayerControl().add_to(m)

    return m._repr_html_()


    # 🚨 Predicted Load → Surge estimation<br>
    # 🤖 AI Risk → LOW / MODERATE / HIGH / CRITICAL
# -------------------------------------------------------
# MAIN VIEW
# -------------------------------------------------------IMP

def map_view(request):
    map_html = render_map(request.GET)
    return render(request, "core/map.html", {"map": map_html})


# -------------------------------------------------------
# OPTIONAL API ENDPOINT
# -------------------------------------------------------

def health_status_api(request):
    """
    Optional API endpoint if frontend wants JSON data.
    """

    hospitals = load_hospitals()
    earthquakes = load_earthquakes()

    return JsonResponse({
        "total_hospitals": len(hospitals),
        "total_earthquakes": len(earthquakes),
    })




# import folium
# from folium.plugins import MarkerCluster
# from .services import (
#     load_hospitals,
#     load_earthquakes,
#     predict_hospital_load,
#     ai_risk_classification,
#     impact_radius,
#     magnitude_color
# )
# from .utils import haversine


# def render_map(params):

#     m = folium.Map(location=[39.8, -98.5], zoom_start=5)

#     hospitals = load_hospitals()
#     earthquakes = load_earthquakes()

#     cluster = MarkerCluster().add_to(m)

#     # -------------------------------------------------
#     # PROCESS EARTHQUAKES FIRST
#     # -------------------------------------------------

#     for eq in earthquakes:

#         radius = impact_radius(eq["mag"])
#         color = magnitude_color(eq["mag"])

#         # Animated Ripple
#         folium.Circle(
#             location=[eq["lat"], eq["lon"]],
#             radius=radius * 1000,
#             color=color,
#             fill=True,
#             fill_opacity=0.2
#         ).add_to(m)

#         folium.CircleMarker(
#             [eq["lat"], eq["lon"]],
#             radius=8,
#             color=color,
#             fill=True,
#             popup=f"<b>Magnitude:</b> {eq['mag']}<br><b>Location:</b> {eq['place']}"
#         ).add_to(m)

#     # -------------------------------------------------
#     # HOSPITAL PROCESSING
#     # -------------------------------------------------

#     for h in hospitals:

#         hospital_color = "green"
#         load_percent = 0
#         risk_label = "LOW"

#         for eq in earthquakes:
#             dist = haversine(h["lat"], h["lon"], eq["lat"], eq["lon"])
#             radius = impact_radius(eq["mag"])

#             if dist <= radius:
#                 hospital_color = "red"

#                 hazard_score = eq["mag"] * 20
#                 load_percent = predict_hospital_load(h["beds"], hazard_score)
#                 risk_label = ai_risk_classification(
#                     eq["mag"], dist, load_percent
#                 )
#                 break

#         icon_url = "https://cdn-icons-png.flaticon.com/512/2967/2967350.png"

#         popup_html = f"""
#         <div style="width:300px;font-family:Arial;">
#             <h3 style="color:{hospital_color};">
#                 {'🚨 At Risk' if hospital_color=='red' else '✅ Safe Hospital'}
#             </h3>

#             <b>Name:</b> {h['name']}<br>
#             <b>City:</b> {h['city']}, {h['state']}<br>
#             <b>Beds:</b> {h['beds']}<br>
#             <b>Predicted Load:</b> {load_percent}%<br>
#             <b>AI Risk Level:</b> 
#             <span style="color:red;font-weight:bold;">
#                 {risk_label}
#             </span>

#             <hr>

#             <b>Facilities:</b>
#             <ul style="max-height:120px;overflow:auto;">
#                 {''.join(f"<li>{f}</li>" for f in h['facilities'])}
#             </ul>
#         </div>
#         """

#         folium.Marker(
#             [h["lat"], h["lon"]],
#             popup=folium.Popup(popup_html, max_width=350),
#             icon=folium.CustomIcon(icon_url, icon_size=(28, 28))
#         ).add_to(cluster)

#     # -------------------------------------------------
#     # LEGEND BOX
#     # -------------------------------------------------

#     legend_html = """
#     <div style="
#         position: fixed;
#         bottom: 50px;
#         left: 50px;
#         width: 250px;
#         background-color: white;
#         border:2px solid grey;
#         z-index:9999;
#         font-size:14px;
#         padding:10px;
#     ">
#     <b>Hazard Legend</b><br>
#     🔴 Red Hospital = Inside Impact Zone<br>
#     🟢 Green Hospital = Safe<br>
#     🟠 Orange Circle = Moderate EQ<br>
#     🔴 Red Circle = Strong EQ<br>
#     🚨 Load % = Predicted surge<br>
#     </div>
#     """

#     m.get_root().html.add_child(folium.Element(legend_html))

#     return m._repr_html_()




# import folium
# from folium.plugins import MarkerCluster, HeatMap
# from django.shortcuts import render
# from django.http import JsonResponse
# from .services import (
#     load_hospitals,
#     load_earthquakes,
#     nearest_hospital,
#     hazard_index,
#     affected_hospitals,
#     nearest_safe_hospitals
# )


# def render_map(params):

#     m = folium.Map(location=[39.8283, -98.5795], zoom_start=5)

#     hospitals = load_hospitals()
#     cluster = MarkerCluster().add_to(m)

#     # -------------------------
#     # SAFE HOSPITAL POPUPS
#     # -------------------------

#     for h in hospitals:

#         facilities_html = "".join(
#             f"<li>{f}</li>" for f in h["facilities"]
#         )

#         popup_html = f"""
#         <div style="width:300px;font-family:Arial;">
#             <h3 style="color:green;">✅ Safe Hospital</h3>
#             <b>Name:</b> {h['name']}<br>
#             <b>City:</b> {h['city']}, {h['state']}<br>
#             <b>Beds:</b> {h['beds']}<br><br>
#             <b>Facilities:</b>
#             <ul style="max-height:150px;overflow:auto;">
#                 {facilities_html}
#             </ul>
#         </div>
#         """

#         folium.Marker(
#             [h["lat"], h["lon"]],
#             popup=folium.Popup(popup_html, max_width=350),
#             icon=folium.Icon(color="green", icon="plus-sign")
#         ).add_to(cluster)

#     # -------------------------
#     # EARTHQUAKE REPORT POPUPS
#     # -------------------------

#     earthquakes = load_earthquakes()

#     for eq in earthquakes:

#         affected = affected_hospitals(eq["lat"], eq["lon"])
#         safe = nearest_safe_hospitals(eq["lat"], eq["lon"])

#         affected_list = "".join(
#             f"<li style='color:red;'>❌ {h['name']}</li>"
#             for h in affected
#         )

#         safe_list = "".join(
#             f"<li style='color:green;'>🚑 {h['name']}</li>"
#             for h in safe
#         )

#         popup_html = f"""
#         <div style="width:350px;font-family:Arial;">
#             <h3 style="color:#d4a017;">⚠️ Earthquake Impact Report</h3>
#             <b>Magnitude:</b> {eq['mag']}<br><br>

#             <b style="color:red;">Affected Hospitals</b>
#             <ul style="max-height:120px;overflow:auto;">
#                 {affected_list if affected_list else "<li>None</li>"}
#             </ul>

#             <hr>

#             <b style="color:green;">Nearest Safe Hospitals</b>
#             <ul style="max-height:120px;overflow:auto;">
#                 {safe_list}
#             </ul>
#         </div>
#         """

#         folium.CircleMarker(
#             [eq["lat"], eq["lon"]],
#             radius=8,
#             color="red",
#             fill=True,
#             fill_color="red",
#             popup=folium.Popup(popup_html, max_width=400)
#         ).add_to(m)

#     return m._repr_html_()


# def map_view(request):
#     map_html = render_map(request.GET)
#     return render(request, "core/map.html", {"map": map_html})


# def nearest_view(request):
#     lat = float(request.GET.get("lat"))
#     lon = float(request.GET.get("lon"))

#     hospital = nearest_hospital(lat, lon)
#     hazard_score, weather_data = hazard_index(
#         lat, lon, hospital["distance_km"]
#     )

#     color = "green"
#     if hazard_score > 70:
#         color = "red"
#     elif hazard_score > 40:
#         color = "orange"

#     return JsonResponse({
#         "hospital": hospital["name"],
#         "distance": hospital["distance_km"],
#         "hazard_score": hazard_score,
#         "weather": weather_data,
#         "color": color
#     })




# import folium
# from django.http import JsonResponse
# from django.shortcuts import render
# from typing import Dict

# from .services import (
#     nearest_hospital,
#     earthquake_risk,
#     weather_data
# )


# def render_map(params: Dict):
#     lat = float(params.get("lat", 39.8283))
#     lon = float(params.get("lon", -98.5795))

#     m = folium.Map(location=[lat, lon], zoom_start=5)

#     folium.Marker(
#         [lat, lon],
#         tooltip="Selected Location",
#         icon=folium.Icon(color="red")
#     ).add_to(m)

#     return m._repr_html_()


# def map_view(request):
#     map_html = render_map(request.GET)
#     return render(request, "core/map.html", {"map": map_html})


# def nearest_view(request):
#     lat = float(request.GET.get("lat"))
#     lon = float(request.GET.get("lon"))

#     hospital = nearest_hospital(lat, lon)
#     eq_risk = earthquake_risk(lat, lon)
#     weather = weather_data(lat, lon)

#     return JsonResponse({
#         "name": hospital["name"],
#         "address": hospital["address"],
#         "city": hospital["city"],
#         "state": hospital["state"],
#         "beds": hospital["beds"],
#         "distance_km": hospital["distance_km"],
#         "earthquake_risk": eq_risk,
#         "temperature": weather["temperature"],
#         "windspeed": weather["windspeed"]
#     })


# import folium
# import requests
# from django.shortcuts import render
# from django.http import JsonResponse

# from .data_loader import load_hospitals, load_earthquakes
# from .utils import haversine, earthquake_risk

# def map_view(request):
#     # Create base US map
#     m = folium.Map(location=[39.5, -98.35], zoom_start=4)

#     hospitals = load_hospitals()

#     for hospital in hospitals:
#         coords = hospital["geometry"]["coordinates"]

#         longitude = coords[0]   # GeoJSON order
#         latitude = coords[1]

#         name = hospital["properties"].get("NAME", "Hospital")

#         folium.Marker(
#             [latitude, longitude],   # Folium expects lat, lon
#             popup=name
#         ).add_to(m)

#     return render(request, "core/map.html", {
#         "map": m._repr_html_()
#     })


# def nearest_hospital(request):
#     lat = float(request.GET.get("lat"))
#     lon = float(request.GET.get("lon"))

#     hospitals = load_hospitals()
#     earthquakes = load_earthquakes()

#     # Nearest hospital
#     nearest = None
#     min_dist = float("inf")

#     for h in hospitals:
#         d = haversine(lat, lon, h["latitude"], h["longitude"])
#         if d < min_dist:
#             min_dist = d
#             nearest = h

#     # Earthquake risk
#     max_risk = "NONE"

#     for q in earthquakes:
#         d_q = haversine(
#             nearest["latitude"],
#             nearest["longitude"],
#             q["latitude"],
#             q["longitude"]
#         )

#         risk = earthquake_risk(d_q, q["magnitude"])

#         if risk == "HIGH":
#             max_risk = "HIGH"
#             break
#         elif risk == "MEDIUM":
#             max_risk = "MEDIUM"
#         elif risk == "LOW" and max_risk == "NONE":
#             max_risk = "LOW"

#     # Weather API
#     weather_url = (
#         f"https://api.open-meteo.com/v1/forecast"
#         f"?latitude={nearest['latitude']}"
#         f"&longitude={nearest['longitude']}"
#         f"&current_weather=true"
#     )

#     weather_data = requests.get(weather_url, timeout=5).json()
#     current_weather = weather_data.get("current_weather", {})

#     return JsonResponse({
#         "hospital": nearest["name"],
#         "distance_km": round(min_dist, 2),
#         "earthquake_risk": max_risk,
#         "temperature": current_weather.get("temperature"),
#         "windspeed": current_weather.get("windspeed")
#     })


# import folium
# import requests
# from django.shortcuts import render
# from django.http import JsonResponse

# from .data_loader import load_hospitals, load_earthquakes
# from .utils import haversine, earthquake_risk


# def map_view(request):
#     """
#     Renders Folium map with hospital markers.
#     """

#     m = folium.Map(location=[39.5, -98.35], zoom_start=4)

#     hospitals = load_hospitals()

#     for hospital in hospitals:
#         folium.Marker(
#             location=[hospital["latitude"], hospital["longitude"]],
#             popup=f'{hospital["name"]} ({hospital["state"]})'
#         ).add_to(m)

#     map_html = m._repr_html_()

#     return render(request, "core/map.html", {"map": map_html})


# def nearest_hospital(request):
#     """
#     Returns nearest hospital + earthquake risk + live weather.
#     """

#     lat = float(request.GET.get("lat"))
#     lon = float(request.GET.get("lon"))

#     hospitals = load_hospitals()
#     earthquakes = load_earthquakes()

#     # ---- Find nearest hospital ----
#     nearest = None
#     min_distance = float("inf")

#     for hospital in hospitals:
#         distance = haversine(
#             lat, lon,
#             hospital["latitude"],
#             hospital["longitude"]
#         )

#         if distance < min_distance:
#             min_distance = distance
#             nearest = hospital

#     # ---- Earthquake risk calculation ----
#     max_risk = "NONE"

#     for quake in earthquakes:
#         quake_distance = haversine(
#             nearest["latitude"],
#             nearest["longitude"],
#             quake["latitude"],
#             quake["longitude"]
#         )

#         risk = earthquake_risk(quake_distance, quake["magnitude"])

#         if risk == "HIGH":
#             max_risk = "HIGH"
#             break
#         elif risk == "MEDIUM":
#             max_risk = "MEDIUM"
#         elif risk == "LOW" and max_risk == "NONE":
#             max_risk = "LOW"

#     # ---- Weather API ----
#     weather_url = (
#         f"https://api.open-meteo.com/v1/forecast"
#         f"?latitude={nearest['latitude']}"
#         f"&longitude={nearest['longitude']}"
#         f"&current_weather=true"
#     )

#     weather_data = requests.get(weather_url, timeout=5).json()
#     current_weather = weather_data.get("current_weather", {})

#     return JsonResponse({
#         "hospital": nearest["name"],
#         "distance_km": round(min_distance, 2),
#         "earthquake_risk": max_risk,
#         "temperature_c": current_weather.get("temperature"),
#         "windspeed_kmh": current_weather.get("windspeed")
#     })
