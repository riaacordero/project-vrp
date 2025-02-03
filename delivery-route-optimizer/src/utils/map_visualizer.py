import folium
from folium import plugins
from typing import List, Dict, Tuple
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from config import HUB_LOCATION, OUTPUT_MAP

class MapVisualizer:
    def __init__(self, route_info: List[Dict]):
        self.route_info = route_info
        self.map = self.create_base_map()
        
    def create_base_map(self) -> folium.Map:
        """Initialize map centered on hub"""
        return folium.Map(
            location=[HUB_LOCATION[1], HUB_LOCATION[0]],
            zoom_start=13,
            tiles='cartodbpositron'
        )
        
    def generate_tooltip(self, stop: Dict) -> str:
        """Create HTML tooltip for stop"""
        return f"""
            <b>Stop {stop['stop_number']}</b><br>
            Customer ID: {stop['customer_id']}<br>
            Coordinates: {stop['coordinates']}<br>
            Last Location: {stop['last_location']}<br>
            Distance from Hub: {stop['distance_from_hub']:.2f} km<br>
            ETA: {stop['eta']:.1f} min<br>
            Remaining Stops: {stop['remaining_stops']}/{len(self.route_info)}<br>
            Remaining Parcels: {stop['remaining_parcels']}
        """
        
    def add_markers(self):
        """Add hub and delivery point markers"""
        # Add hub marker
        folium.Marker(
            location=[HUB_LOCATION[1], HUB_LOCATION[0]],
            icon=folium.Icon(color='red', icon='info-sign'),
            popup=f"<b>Delivery Hub</b><br>Coordinates: {HUB_LOCATION}"
        ).add_to(self.map)
        
        # Add delivery point markers
        for stop in self.route_info:
            folium.Marker(
                location=[stop['coordinates'][1], stop['coordinates'][0]],
                icon=folium.Icon(color='green', icon='info-sign'),
                popup=folium.Popup(self.generate_tooltip(stop), max_width=300)
            ).add_to(self.map)
            
    def draw_routes(self):
        """Draw delivery sequence routes"""
        coordinates = [(HUB_LOCATION[1], HUB_LOCATION[0])]
        for stop in self.route_info:
            coordinates.append((stop['coordinates'][1], stop['coordinates'][0]))
        coordinates.append((HUB_LOCATION[1], HUB_LOCATION[0]))
        
        folium.PolyLine(
            coordinates,
            weight=2,
            color='blue',
            opacity=0.8
        ).add_to(self.map)
        
    def generate_map(self):
        """Generate complete route map"""
        self.add_markers()
        self.draw_routes()
        self.map.save(OUTPUT_MAP)