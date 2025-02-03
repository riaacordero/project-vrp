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
        self.route_layers = []

    def create_base_map(self):
        center_lat = sum(stop['coordinates'][1] for stop in self.route_info) / len(self.route_info)
        center_lon = sum(stop['coordinates'][0] for stop in self.route_info) / len(self.route_info)
        return folium.Map(location=[center_lat, center_lon], zoom_start=14)

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
        # Hub marker
        folium.Marker(
            location=[HUB_LOCATION[1], HUB_LOCATION[0]],
            icon=folium.Icon(color='red', icon='info-sign'),
            tooltip=f"<b>Delivery Hub</b><br>Coordinates: {HUB_LOCATION}"
        ).add_to(self.map)
        
        # Stop markers
        for stop in self.route_info:
            folium.Marker(
                location=[stop['coordinates'][1], stop['coordinates'][0]],
                icon=folium.Icon(color='green', icon='info-sign'),
                tooltip=self.generate_tooltip(stop)
            ).add_to(self.map)

    def draw_routes(self):
        route_group = folium.FeatureGroup(name='routes')
        
        # Add hub to first stop
        first_route = self.ors_client.get_route_details(HUB_LOCATION, self.route_info[0]['coordinates'])
        self._add_route_segment(first_route, route_group, 0)
        
        # Add routes between stops
        for i in range(len(self.route_info) - 1):
            route = self.ors_client.get_route_details(
                self.route_info[i]['coordinates'],
                self.route_info[i + 1]['coordinates']
            )
            self._add_route_segment(route, route_group, i + 1)
        
        # Add last stop to hub
        last_route = self.ors_client.get_route_details(
            self.route_info[-1]['coordinates'],
            HUB_LOCATION
        )
        self._add_route_segment(last_route, route_group, len(self.route_info))
        
        route_group.add_to(self.map)
        self.add_navigation_controls()

    def _add_route_segment(self, route, group, index):
        layer = folium.GeoJson(
            route,
            style_function=lambda x: {
                'color': '#3388ff',
                'weight': 3,
                'opacity': 0.8,
                'dashArray': '10, 10'
            }
        )
        self.route_layers.append(layer)
        layer.add_to(group)

    def add_navigation_controls(self):
        """Add navigation buttons to control route display"""
        navigation_html = """
        <div style='position: fixed; bottom: 50px; left: 50px; z-index: 9999;'>
            <button onclick='prevStep()'>←</button>
            <button onclick='nextStep()'>→</button>
        </div>
        <script>
            var currentStep = 0;
            var routeLayers = {};
            function showStep(step) {
                Object.values(routeLayers).forEach(layer => layer.setStyle({opacity: 0}));
                if (step >= 0 && step < Object.keys(routeLayers).length) {
                    routeLayers[step].setStyle({opacity: 0.8});
                }
            }
            function nextStep() {
                currentStep = Math.min(currentStep + 1, Object.keys(routeLayers).length - 1);
                showStep(currentStep);
            }
            function prevStep() {
                currentStep = Math.max(currentStep - 1, 0);
                showStep(currentStep);
            }
        </script>
        """
        self.map.get_root().html.add_child(folium.Element(navigation_html))
        
    def generate_map(self):
        self.add_markers()
        self.draw_routes()
        self.map.save(OUTPUT_MAP)