import math

EARTH_R = 6371000.0


def haversine(lat1, lng1, lat2, lng2):
    """Great-circle distance in metres."""
    la1, lo1, la2, lo2 = map(math.radians, (lat1, lng1, lat2, lng2))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * EARTH_R * math.asin(math.sqrt(h))


def bearing(lat1, lng1, lat2, lng2):
    """Compass bearing in degrees (0 = north, 90 = east) from point 1 to point 2."""
    la1, la2 = math.radians(lat1), math.radians(lat2)
    dlo = math.radians(lng2 - lng1)
    y = math.sin(dlo) * math.cos(la2)
    x = math.cos(la1) * math.sin(la2) - math.sin(la1) * math.cos(la2) * math.cos(dlo)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def turn_angle(bearing_in, bearing_out):
    """Signed turn in degrees, -180..180. Positive = right, negative = left."""
    return (bearing_out - bearing_in + 540) % 360 - 180
