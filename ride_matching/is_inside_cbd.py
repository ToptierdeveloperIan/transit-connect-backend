from math import radians, cos, sin, asin, sqrt

def haversine(lat1, lng1, lat2, lng2):
    # Haversine formula to calculate distance between two lat/lng points in meters
    R = 6371000  # Radius of Earth in meters
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng/2)**2
    c = 2 * asin(sqrt(a))
    return R * c

def is_inside_cbd(user_lat, user_lng):
    distance = haversine(user_lat, user_lng, CBD_CENTER["lat"], CBD_CENTER["lng"])
    return distance <= CBD_RADIUS_METERS
