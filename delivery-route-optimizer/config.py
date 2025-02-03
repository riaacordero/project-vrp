import os

# Constants
HUB_LOCATION = (125.6117, 7.0854)
AVG_SPEED_KMH = 30
IDLE_TIME_PER_HOUSE = 6  # minutes

# ORS API Configuration
ORS_API_URL = "http://localhost:8080/ors"
ORS_PROFILE = "driving-car"

# Data paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "src", "data")
TEMPLATE_DIR = os.path.join(BASE_DIR, "src", "templates")

# Output paths
OUTPUT_MAP = os.path.join(TEMPLATE_DIR, "route_map.html")