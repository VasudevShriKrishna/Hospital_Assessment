from .models import Hospital
from .utils import haversine

def get_affected_hospitals(epicenter_lat, epicenter_lon, ):
    hospitals=Hospital.objects.all()
    affected_hospitals = []
    for h in hospitals:
        distance = haversine(epicenter_lat, epicenter_lon, h.latitude, h.longitude)
        if distance <= 20:
            impact ="severe"
        elif distance <= 50:
            impact = "moderate"
        elif distance <= 100:
            impact = "high"
        else:impact = "low"

        affected_hospitals.append({
            "hospital": h.name,
            "distance_km":round(distance, 2),
            "impact": impact
        })
    affected_hospitals.sort(key=lambda x: x["distance_km"])
    return affected_hospitals