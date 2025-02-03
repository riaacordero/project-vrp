import folium
from folium import plugins
from typing import List, Dict, Tuple
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from config import HUB_LOCATION, OUTPUT_MAP

class MapVisualizer:
    def __init__(self, route_info: List[Dict], ors_client):
        self.route_info = route_info
        self.ors_client = ors_client
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
        """Draw actual road routes between points"""
        # Draw route from hub to first stop
        first_stop = self.route_info[0]
        route = self.ors_client.get_route_details(
            HUB_LOCATION,
            first_stop['coordinates']
        )
        self._add_route_to_map(route)
        
        # Draw routes between stops
        for i in range(len(self.route_info) - 1):
            current = self.route_info[i]
            next_stop = self.route_info[i + 1]
            
            route = self.ors_client.get_route_details(
                current['coordinates'],
                next_stop['coordinates']
            )
            self._add_route_to_map(route)
            
        # Draw route from last stop back to hub
        last_stop = self.route_info[-1]
        route = self.ors_client.get_route_details(
            last_stop['coordinates'],
            HUB_LOCATION
        )
        self._add_route_to_map(route)
        
    def _add_route_to_map(self, route):
        """Add route GeoJSON to map"""
        folium.GeoJson(
            route,
            style_function=lambda x: {
                'color': '#3388ff',
                'weight': 3,
                'opacity': 0.8
            }
        ).add_to(self.map)
        
    def generate_map(self):
        """Generate complete route map"""
        self.add_markers()
        self.draw_routes()
        self.map.save(OUTPUT_MAP)