import openrouteservice as ors
from typing import List, Tuple, Dict
import numpy as np
import logging
import sys
import os
from time import sleep

# Configure logger
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from config import ORS_API_URL, ORS_PROFILE

class ORSClient:
    def __init__(self):
        self.client = ors.Client(base_url="http://localhost:8080/ors")
        self.profile = "driving-car"
        self.max_batch = 45  # Square root of 2500 minus safety margin
        
    def _format_coordinates(self, coordinates: List[Tuple[float, float]]) -> List[List[float]]:
        """Format coordinates as [longitude, latitude] for ORS API"""
        return [[lon, lat] for lon, lat in coordinates]
    
    def _validate_coordinates(self, coordinates: List[Tuple[float, float]]) -> bool:
        """Validate coordinates are within Davao City bounds"""
        for coord in coordinates:
            lon, lat = coord
            logger.debug(f"Validating coordinate: lon={lon}, lat={lat}")
            # Expanded bounds slightly for safety
            if not (124.5 <= lon <= 126.5 and 6.0 <= lat <= 8.5):
                logger.error(f"Invalid coordinate: {coord}")
                return False
        return True
    
    def _normalize_coordinates(self, coordinates: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """Ensure all coordinates are in (lon, lat) format"""
        normalized = []
        for lon, lat in coordinates:
            # If coordinates appear swapped (lat > lon), swap them
            if lat > lon:
                lon, lat = lat, lon
            normalized.append((lon, lat))
        return normalized
    
    def get_distance_matrix(self, coordinates: List[Tuple[float, float]]) -> List[List[float]]:
        """Calculate distance matrix between all points"""
        try:
            logger.debug(f"Input coordinates: {coordinates}")
            
            if not self._validate_coordinates(coordinates):
                raise ValueError(f"Coordinates outside Davao City bounds: {coordinates}")
                
            if len(coordinates) <= self.max_batch:
                return self._request_matrix(coordinates)
                
            return self._process_large_matrix(coordinates)
            
        except Exception as e:
            logger.error(f"Matrix calculation failed: {str(e)}")
            raise Exception(f"Error calculating distance matrix: {str(e)}")
            
    def _request_matrix(self, coords: List[Tuple[float, float]]) -> List[List[float]]:
        matrix = self.client.distance_matrix(
            locations=coords,
            profile=self.profile,
            metrics=['duration'],
            validate=False
        )
        return matrix.get('durations', [])
        
    def _process_large_matrix(self, coordinates: List[Tuple[float, float]]) -> List[List[float]]:
        n = len(coordinates)
        result = np.zeros((n, n))
        
        for i in range(0, n, self.max_batch):
            batch = coordinates[i:min(i + self.max_batch, n)]
            sub_matrix = self._request_matrix(batch)
            result[i:i + len(batch), i:i + len(batch)] = sub_matrix
            
        return result.tolist()
            
    def get_route(self, start: Tuple[float, float], end: Tuple[float, float]) -> Dict:
        """Get detailed route between two points"""
        try:
            route = self.client.directions(
                coordinates=[start, end],
                profile=self.profile,
                format='geojson'
            )
            return route
        except Exception as e:
            raise Exception(f"Error getting route: {str(e)}")
            
    def calculate_eta(self, distance: float, parcels: int) -> float:
        """Calculate estimated time of arrival in minutes"""
        try:
            return (distance / 1000.0) * 60 + parcels * 6  # Convert to minutes
        except Exception as e:
            raise Exception(f"Error calculating ETA: {str(e)}")