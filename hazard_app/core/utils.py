import math


def haversine(lat1, lon1, lat2, lon2):
    R = 6371

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) *
         math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def earthquake_risk(distance_km, magnitude):
    if distance_km <= 50 and magnitude >= 6:
        return "HIGH"
    elif distance_km <= 100 and magnitude >= 5:
        return "MEDIUM"
    elif distance_km <= 200:
        return "LOW"
    else:
        return "NONE"


# import math


# def haversine(lat1, lon1, lat2, lon2):
#     R = 6371  # Earth radius (km)

#     dlat = math.radians(lat2 - lat1)
#     dlon = math.radians(lon2 - lon1)

#     a = (math.sin(dlat / 2) ** 2 +
#          math.cos(math.radians(lat1)) *
#          math.cos(math.radians(lat2)) *
#          math.sin(dlon / 2) ** 2)

#     c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

#     return R * c


# def earthquake_risk(distance_km, magnitude):
#     """
#     Heuristic impact model (v1 MVP)
#     """

#     if distance_km <= 50 and magnitude >= 6.0:
#         return "HIGH"
#     elif distance_km <= 100 and magnitude >= 5.0:
#         return "MEDIUM"
#     elif distance_km <= 200:
#         return "LOW"
#     else:
#         return "NONE"
