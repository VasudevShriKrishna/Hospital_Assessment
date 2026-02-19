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

# MAIN MAP RENDER FUNCTION
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

    # HOSPITAL LAYER
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

    

    folium.LayerControl().add_to(m)

    return m._repr_html_()

# MAIN VIEW   IMP

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
