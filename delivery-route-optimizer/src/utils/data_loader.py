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
    def __init__(self, filename: str):
        self.filepath = os.path.join(DATA_DIR, filename)
        
    def load_data(self) -> pd.DataFrame:
        try:
            df = pd.read_csv(self.filepath)
            required_columns = ['Customer_ID', 'Longitude', 'Latitude', 'Number_of_parcels']
            
            if not all(col in df.columns for col in required_columns):
                raise ValueError("Missing required columns in CSV file")
            
            # Clean and convert numeric columns
            df['Longitude'] = df['Longitude'].astype(str).str.strip().astype(float)
            df['Latitude'] = df['Latitude'].astype(str).str.strip().astype(float)
            df['Number_of_parcels'] = df['Number_of_parcels'].astype(int)
            
            # Swap coordinates if they're in wrong order
            if df['Longitude'].mean() < df['Latitude'].mean():
                df['Longitude'], df['Latitude'] = df['Latitude'], df['Longitude']
            
            # Debug coordinates
            logger.debug(f"Longitude range: {df['Longitude'].min()} to {df['Longitude'].max()}")
            logger.debug(f"Latitude range: {df['Latitude'].min()} to {df['Latitude'].max()}")
            
            # Validate coordinates (Davao City area)
            if not (df['Longitude'].between(125.0, 126.0).all() and 
                   df['Latitude'].between(6.5, 8.0).all()):
                raise ValueError("Coordinates outside Davao City range")
                
            # Validate parcel numbers
            if not (df['Number_of_parcels'] > 0).all():
                raise ValueError("Invalid parcel numbers")
                
            return df
            
        except FileNotFoundError:
            raise FileNotFoundError(f"Data file not found at {self.filepath}")
        except Exception as e:
            raise Exception(f"Error loading data: {str(e)}")
            
    def get_coordinates(self) -> List[Tuple[float, float]]:
        """Returns list of (longitude, latitude) tuples"""
        df = self.load_data()
        return list(zip(df['Longitude'], df['Latitude']))
    
    def get_customer_info(self) -> pd.DataFrame:
        """Returns customer information with coordinates"""
        return self.load_data()