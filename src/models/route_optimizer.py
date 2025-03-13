import numpy as np
from typing import List, Tuple, Dict
import logging
import os, sys

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from config import (
    HUB_LOCATION, 
    AVG_SPEED_KMH, 
    IDLE_TIME_PER_HOUSE
)

# Hub location coordinates (longitude, latitude)
HUB_LOCATION = (125.61986151071888, 7.070884126747574)  # SMC Complex Hub

# Output map filename
OUTPUT_MAP = 'route_map.html'

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

    def meters_to_km(self, meters: float) -> float:
        """Convert meters to kilometers"""
        return meters / 1000.0

    def calculate_eta(self, distance_km: float) -> float:
        """
        Calculate ETA in minutes based on distance and configuration
        Args:
            distance_km: Distance in kilometers
        Returns:
            float: Estimated time in minutes
        """
        travel_time = (distance_km / AVG_SPEED_KMH) * 60  # Convert hours to minutes
        return travel_time + IDLE_TIME_PER_HOUSE

    def find_nearest_point(self) -> int:
        min_distance = float('inf')
        nearest_idx = -1

        current_coords = self.all_coordinates[self.current_location]
        
        for idx in range(len(self.all_coordinates)):
            if idx not in self.visited:
                # Get actual route distance
                distance = self.get_route_distance(self.current_location, idx)
                distance_km = self.meters_to_km(distance)
                
                logger.debug(f"Point {idx} - Distance: {distance_km:.2f}km")
                
                if distance < min_distance:
                    min_distance = distance
                    nearest_idx = idx
                    
        if nearest_idx == -1:
            raise ValueError("No unvisited points found")
            
        return nearest_idx

    def get_route_distance(self, start_idx: int, end_idx: int) -> float:
        """Get actual road distance between two points in meters"""
        try:
            route = self.ors_client.get_route_details(
                self.all_coordinates[start_idx],
                self.all_coordinates[end_idx]
            )
            return route['features'][0]['properties']['segments'][0]['distance']
        except Exception as e:
            logger.error(f"Failed to get route distance: {e}")
            return self.distance_matrix[start_idx][end_idx]

    def optimize_route(self) -> List[Dict]:
        try:
            logger.info("Getting distance matrix...")
            self.distance_matrix = self.ors_client.get_distance_matrix(self.all_coordinates)
            route_info = []
            total_distance = 0
            
            self.current_location = 0
            self.visited = {0}
            
            while len(self.visited) < len(self.all_coordinates):
                next_idx = self.find_nearest_point()
                self.visited.add(next_idx)
                
                # Calculate distances
                current_distance = self.get_route_distance(self.current_location, next_idx)
                hub_distance = self.get_route_distance(0, next_idx)
                total_distance += current_distance
                
                # Log only every 10th point or first/last point
                if len(self.visited) % 10 == 0 or len(self.visited) == len(self.all_coordinates):
                    logger.debug(f"Progress: {len(self.visited)}/{len(self.all_coordinates)} stops")
                    logger.debug(f"Total distance so far: {total_distance/1000:.2f}km")
                
                stop_info = {
                    'stop_number': len(self.visited) - 1,
                    'tracking_num': self.customer_data.iloc[next_idx - 1]['tracking_num'],
                    'zone': self.customer_data.iloc[next_idx - 1]['zone'],
                    'address': self.customer_data.iloc[next_idx - 1]['customer_address'],
                    'coordinates': self.all_coordinates[next_idx],
                    'last_location': self.all_coordinates[self.current_location],
                    'distance': current_distance,
                    'distance_from_hub': hub_distance,
                    'eta': self.calculate_eta(current_distance),
                    'remaining_stops': len(self.all_coordinates) - len(self.visited),
                    'remaining_parcels': len(self.all_coordinates) - len(self.visited)
                }
                
                route_info.append(stop_info)
                self.current_location = next_idx
                
            logger.info(f"Route optimization complete. Total distance: {total_distance/1000:.2f}km")
            return route_info
            
        except Exception as e:
            logger.error(f"Route optimization failed: {str(e)}")
            raise