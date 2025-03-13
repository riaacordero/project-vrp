import pandas as pd
from typing import List, Tuple
import sys
import os
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from config import DATA_DIR
# Configure logger
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class DeliveryDataLoader:
    def __init__(self, filepath: str):
        try:
            self.data = pd.read_csv(filepath)
            self.preprocess_data()
            self.validate_data()
            logger.debug(f"Loaded {len(self.data)} delivery points")
        except Exception as e:
            logger.error(f"Failed to load data: {e}")
            raise

    def preprocess_data(self) -> None:
        """Clean and preprocess delivery data"""
        # Log initial count
        initial_count = len(self.data)
        
        # Drop rows with NaN coordinates
        self.data = self.data.dropna(subset=['longitude', 'latitude'])
        cleaned_count = len(self.data)
        
        if initial_count != cleaned_count:
            logger.warning(f"Removed {initial_count - cleaned_count} rows with invalid coordinates")
        
        # Drop only unnecessary columns
        columns_to_drop = ['date_of_delivery', 'barangay', 'reason']
        self.data = self.data.drop(columns=[col for col in columns_to_drop if col in self.data.columns])
        
        # Rename columns if needed
        if 'customer_id' in self.data.columns:
            self.data = self.data.rename(columns={'customer_id': 'tracking_num'})
        
        # Reset index after cleaning
        self.data = self.data.reset_index(drop=True)

    def validate_data(self) -> None:
        """Validate the loaded delivery data"""
        required_columns = ['longitude', 'latitude']
        
        # Check for required columns
        missing_cols = [col for col in required_columns if col not in self.data.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")
            
        # Validate coordinate ranges
        lon_range = self.data['longitude'].agg(['min', 'max'])
        lat_range = self.data['latitude'].agg(['min', 'max'])
        
        # Check if coordinates need to be swapped
        if lon_range['min'] < 100:  # Longitude in Philippines should be > 100
            logger.info("Swapping latitude and longitude columns")
            self.data['longitude'], self.data['latitude'] = self.data['latitude'], self.data['longitude']
            
            # Recalculate ranges after swap
            lon_range = self.data['longitude'].agg(['min', 'max'])
            lat_range = self.data['latitude'].agg(['min', 'max'])
            
        logger.debug(f"Longitude range: {lon_range['min']:.4f} to {lon_range['max']:.4f}")
        logger.debug(f"Latitude range: {lat_range['min']:.4f} to {lat_range['max']:.4f}")
        
        # Validate coordinate ranges for Davao City
        if not (125.0 <= lon_range['min'] <= lon_range['max'] <= 126.0):
            raise ValueError(f"Longitude values outside Davao City bounds: {lon_range['min']:.4f} to {lon_range['max']:.4f}")
        if not (6.5 <= lat_range['min'] <= lat_range['max'] <= 7.5):
            raise ValueError(f"Latitude values outside Davao City bounds: {lat_range['min']:.4f} to {lat_range['max']:.4f}")

    def get_coordinates(self) -> List[Tuple[float, float]]:
        """Extract delivery point coordinates as (longitude, latitude) tuples"""
        return list(zip(self.data['longitude'], self.data['latitude']))
    
    def get_customer_info(self) -> pd.DataFrame:
        """Get customer information including zone and address"""
        return self.data[['tracking_num', 'zone', 'customer_address']]