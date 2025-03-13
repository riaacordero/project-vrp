import folium
from typing import Dict, List
import logging
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from config import HUB_LOCATION, OUTPUT_MAP

logger = logging.getLogger(__name__)

class MapVisualizer:
    def __init__(self, zones: Dict[str, List[Dict]], ors_client):
        self.zones = zones
        self.ors_client = ors_client

    def create_base_map(self, stops: List[Dict]) -> folium.Map:
        """Create base map centered on delivery points"""
        center_lat = sum(stop['coordinates'][1] for stop in stops) / len(stops)
        center_lon = sum(stop['coordinates'][0] for stop in stops) / len(stops)
        return folium.Map(location=[center_lat, center_lon], zoom_start=14)

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

    def generate_hub_tooltip(self, zones: Dict) -> str:
        """Generate enhanced tooltip for hub with complete journey info"""
        total_journey_distance = 0
        last_stop = None
        return_distance = 0

        # Calculate total journey distance including return
        for zone_stops in zones.values():
            if zone_stops:
                # Add all stop-to-stop distances
                total_journey_distance += sum(stop['distance'] for stop in zone_stops)
                
                # Track last stop and return distance
                if 'return_distance' in zone_stops[-1]:
                    if not last_stop or zone_stops[-1]['arrival_time'] > last_stop['arrival_time']:
                        last_stop = zone_stops[-1]
                        return_distance = last_stop['return_distance']
                        total_journey_distance += return_distance  # Add return distance to total

        if last_stop:
            return f"""
                <b>SMC Complex Hub</b><br>
                Coordinates: {HUB_LOCATION}<br>
                <br>
                Last stop visited: Stop #{last_stop['stop_number']} - {last_stop['address']}<br>
                Total distance travelled: {total_journey_distance/1000:.2f} km<br>
                Return to hub distance: {return_distance/1000:.2f} km<br>
                Final return time: {last_stop['return_time']}
            """
        
        return f"<b>SMC Complex Hub</b><br>Coordinates: {HUB_LOCATION}"

    def draw_return_route(self, map_obj: folium.Map, last_stop: Dict):
        """Draw return route from last stop to hub"""
        try:
            return_route = self.ors_client.get_route_details(
                last_stop['coordinates'],
                HUB_LOCATION
            )
            folium.GeoJson(
                return_route,
                style_function=lambda x: {
                    'color': 'red',
                    'weight': 3,
                    'opacity': 0.8,
                    'dashArray': '10,10'  # Creates dashed line
                }
            ).add_to(map_obj)
        except Exception as e:
            logger.error(f"Failed to draw return route: {e}")

    def generate_map(self, output_file: str):
        """Generate and save the route map"""
        try:
            # Create map with all stops from all zones
            all_stops = [stop for stops in self.zones.values() for stop in stops]
            zone_map = self.create_base_map(all_stops)
            
            # Add hub marker with enhanced tooltip
            folium.Marker(
                location=[HUB_LOCATION[1], HUB_LOCATION[0]],
                icon=folium.Icon(color='red', icon='info-sign'),
                tooltip=self.generate_hub_tooltip(self.zones)
            ).add_to(zone_map)
            
            # Process each zone
            for zone, stops in self.zones.items():
                # Draw routes for this zone
                self.draw_routes(zone_map, stops)
                
                # Add markers for each stop
                for stop in stops:
                    folium.Marker(
                        location=[stop['coordinates'][1], stop['coordinates'][0]],
                        icon=folium.Icon(color='green'),
                        tooltip=self.generate_tooltip(stop)
                    ).add_to(zone_map)
                
                # Draw return route for last stop in zone
                if stops:
                    self.draw_return_route(zone_map, stops[-1])
            
            # Save the map
            zone_map.save(output_file)
            logger.info(f"Generated map: {output_file}")
            
        except Exception as e:
            logger.error(f"Failed to generate map: {e}")
            raise