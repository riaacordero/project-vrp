import numpy as np
from typing import List, Tuple, Dict
import logging
from config import HUB_LOCATION

logger = logging.getLogger(__name__)

class RouteOptimizer:
    def __init__(self, data_loader, ors_client):
        self.data_loader = data_loader
        self.ors_client = ors_client
        self.delivery_points = self.data_loader.get_coordinates()
        self.all_coordinates = [HUB_LOCATION] + self.delivery_points
        self.customer_data = self.data_loader.get_customer_info()
        self.total_stops = len(self.delivery_points)
        self.visited = {0}  # Hub is already visited
        self.current_location = 0  # Start at hub
        self.distance_matrix = None
        
    def find_nearest_point(self) -> int:
        if not self.distance_matrix:
            raise ValueError("Distance matrix not initialized")
            
        min_distance = float('inf')
        nearest_idx = -1
        
        for idx in range(1, len(self.all_coordinates)):
            if idx not in self.visited:
                distance = self.distance_matrix[self.current_location][idx]
                if distance < min_distance:
                    min_distance = distance
                    nearest_idx = idx
                    
        if nearest_idx == -1:
            raise ValueError("No unvisited points found")
            
        return nearest_idx
        
    def optimize_route(self) -> List[Dict]:
        try:
            self.distance_matrix = self.ors_client.get_distance_matrix(self.all_coordinates)
            route_info = []
            total_parcels = self.customer_data['Number_of_parcels'].sum()
            remaining_parcels = total_parcels
            
            while len(self.visited) < len(self.all_coordinates):
                next_idx = self.find_nearest_point()
                self.visited.add(next_idx)
                
                # Calculate metrics
                distance_from_hub = self.distance_matrix[0][next_idx]
                current_distance = self.distance_matrix[self.current_location][next_idx]
                parcels = self.customer_data.iloc[next_idx - 1]['Number_of_parcels']
                remaining_parcels -= parcels
                
                # Calculate ETA (distance in meters, speed in km/h)
                eta = (current_distance / 1000.0) * (60 / 30) + 6  # 30 km/h speed, 6 min stop
                
                stop_info = {
                    'stop_number': len(self.visited) - 1,
                    'customer_id': self.customer_data.iloc[next_idx - 1]['Customer_ID'],
                    'coordinates': self.all_coordinates[next_idx],
                    'last_location': self.all_coordinates[self.current_location],
                    'distance': current_distance,
                    'distance_from_hub': distance_from_hub,
                    'eta': eta,
                    'remaining_stops': self.total_stops - (len(self.visited) - 1),
                    'remaining_parcels': remaining_parcels
                }
                
                route_info.append(stop_info)
                self.current_location = next_idx
                
            return route_info
            
        except Exception as e:
            logger.error(f"Route optimization failed: {str(e)}")
            raise