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
        self.route_groups = []  # Store route groups separately

    def create_base_map(self):
        center_lat = sum(stop['coordinates'][1] for stop in self.route_info) / len(self.route_info)
        center_lon = sum(stop['coordinates'][0] for stop in self.route_info) / len(self.route_info)
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
            Last Location: {stop['last_location']}<br>
            Distance from Hub: {stop['distance_from_hub']/1000:.2f} km<br>
            ETA: {stop['eta']:.0f} min<br>
            <br>
            Remaining Stops: {stop['remaining_stops']}<br>
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
        """Draw routes with minimal API calls"""
        route_group = folium.FeatureGroup(name='routes')
        
        for i in range(len(self.route_info) - 1):
            current = self.route_info[i]['coordinates']
            next_stop = self.route_info[i + 1]['coordinates']
            
            route = self.ors_client.get_route_details(current, next_stop)
            self._add_route_segment(route, route_group, i)
            
        route_group.add_to(self.map)
        
    def _add_route_segment(self, route, route_group, index):
        folium.GeoJson(
            route,
            style_function=lambda x: {
                'color': '#3388ff',
                'weight': 3,
                'dashArray': '10, 10'
            }
        ).add_to(route_group)
        
    def add_navigation_controls(self):
        navigation_js = """
            <script>
                var currentStep = -1;
                var totalSteps = %d;
                var routeGroups = {};
                
                function initRouteGroups() {
                    for (let i = 0; i <= totalSteps; i++) {
                        routeGroups[i] = document.querySelector(`[name="route_${i}"]`);
                    }
                }
                
                function showStep(step) {
                    if (step === -1) {
                        // Show all routes
                        Object.values(routeGroups).forEach(group => {
                            if (group) group.style.display = 'block';
                        });
                    } else {
                        // Show only current segment
                        Object.entries(routeGroups).forEach(([idx, group]) => {
                            if (group) group.style.display = idx == step ? 'block' : 'none';
                        });
                    }
                    
                    document.getElementById('stepCounter').textContent = 
                        step === -1 ? 'All Routes' : `Step ${step + 1} / ${totalSteps}`;
                }
                
                function nextStep() {
                    if (currentStep < totalSteps - 1) {
                        currentStep++;
                        showStep(currentStep);
                    }
                }
                
                function prevStep() {
                    if (currentStep > -1) {
                        currentStep--;
                        showStep(currentStep);
                    }
                }
                
                // Initialize after map loads
                window.addEventListener('load', function() {
                    initRouteGroups();
                    showStep(-1);
                });
            </script>
        """ % len(self.route_groups)
        
        navigation_html = """
            <div style='position: fixed; bottom: 50px; left: 50px; z-index: 999; 
                      background: white; padding: 10px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.2);'>
                <button onclick='prevStep()' style='margin-right: 10px;'>←</button>
                <span id='stepCounter'>All Routes</span>
                <button onclick='nextStep()' style='margin-left: 10px;'>→</button>
            </div>
        """
        
        self.map.get_root().html.add_child(folium.Element(navigation_js + navigation_html))
        
    def generate_map(self):
        self.add_markers()
        self.draw_routes()
        self.map.save(OUTPUT_MAP)