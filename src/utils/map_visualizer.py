import folium
from folium import plugins
from typing import List, Dict, Tuple
import logging
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from config import HUB_LOCATION, OUTPUT_MAP

logger = logging.getLogger(__name__)

class MapVisualizer:
    def __init__(self, zone_routes: Dict[str, List[Dict]], ors_client):
        """Initialize with dictionary of zone-based routes"""
        self.zone_routes = zone_routes
        self.ors_client = ors_client

    def create_base_map(self, stops: List[Dict]) -> folium.Map:
        """Create base map centered on zone's delivery points"""
        if not stops:
            return folium.Map(location=[HUB_LOCATION[1], HUB_LOCATION[0]], zoom_start=14)
            
        center_lat = sum(stop['coordinates'][1] for stop in stops) / len(stops)
        center_lon = sum(stop['coordinates'][0] for stop in stops) / len(stops)
        return folium.Map(location=[center_lat, center_lon], zoom_start=14)

    def generate_tooltip(self, stop: Dict) -> str:
        """Generate tooltip content for map markers"""
        return f"""
            <b>Stop {stop['stop_number']}</b><br>
            {stop['tracking_num']}<br>
            Zone: {stop['zone']}<br>
            Address: {stop['address']}<br>
            Coordinates: {stop['coordinates']}<br>
            <br>
            Distance from Hub: {stop['distance_from_hub']/1000:.2f} km<br>
            Total Distance: {stop['total_distance']/1000:.2f} km<br>
            Arrival Time: {stop['arrival_time']}<br>
            <br>
            Remaining Stops: {stop['remaining_stops']}
        """

    def draw_hub_route(self, map_obj: folium.Map, first_stop: Dict):
        """Draw route from hub to zone's first stop"""
        try:
            route = self.ors_client.get_route_details(HUB_LOCATION, first_stop['coordinates'])
            folium.GeoJson(
                route,
                style_function=lambda x: {
                    'color': 'red',
                    'weight': 3,
                    'opacity': 0.8
                }
            ).add_to(map_obj)
        except Exception as e:
            logger.error(f"Failed to draw hub route: {e}")

    def draw_routes(self, map_obj: folium.Map, stops: List[Dict]):
        """Draw routes between consecutive stops and from hub to first stop"""
        try:
            # Draw route from hub to first stop
            if stops:
                first_route = self.ors_client.get_route_details(HUB_LOCATION, stops[0]['coordinates'])
                folium.GeoJson(
                    first_route,
                    style_function=lambda x: {
                        'color': 'red',
                        'weight': 3,
                        'opacity': 0.8
                    }
                ).add_to(map_obj)

            # Draw routes between consecutive stops
            for i in range(len(stops) - 1):
                current_stop = stops[i]
                next_stop = stops[i + 1]
                
                route = self.ors_client.get_route_details(
                    current_stop['coordinates'],
                    next_stop['coordinates']
                )
                
                folium.GeoJson(
                    route,
                    style_function=lambda x: {
                        'color': 'blue',
                        'weight': 2,
                        'opacity': 0.6
                    }
                ).add_to(map_obj)
                
        except Exception as e:
            logger.error(f"Failed to draw routes: {e}")

    def generate_maps(self):
        """Generate separate maps for each zone"""
        for zone, stops in self.zone_routes.items():
            try:
                # Create new map for this zone
                zone_map = self.create_base_map(stops)
                
                # Add hub marker
                folium.Marker(
                    location=[HUB_LOCATION[1], HUB_LOCATION[0]],
                    icon=folium.Icon(color='red', icon='info-sign'),
                    tooltip=f"<b>Delivery Hub</b><br>Coordinates: {HUB_LOCATION}"
                ).add_to(zone_map)
                
                # Draw all routes
                self.draw_routes(zone_map, stops)
                
                # Add delivery point markers
                for stop in stops:
                    folium.Marker(
                        location=[stop['coordinates'][1], stop['coordinates'][0]],
                        icon=folium.Icon(color='green'),
                        tooltip=self.generate_tooltip(stop)
                    ).add_to(zone_map)
                
                # Save map
                output_file = f"Zone_{zone}.html"
                zone_map.save(output_file)
                logger.info(f"Generated map for Zone {zone} with {len(stops)} stops")
                
            except Exception as e:
                logger.error(f"Failed to generate map for Zone {zone}: {e}")