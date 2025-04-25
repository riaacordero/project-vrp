import sys
import os
import argparse
import logging
import string
from datetime import datetime, timedelta
import pandas as pd
from utils.data_loader import DeliveryDataLoader
from utils.ors_client import ORSClient
from models.route_optimizer import RouteOptimizer
from utils.map_visualizer import MapVisualizer
from utils.route_validator import RouteValidator
from config import HUB_LOCATION  # Add this import

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def parse_args():
    parser = argparse.ArgumentParser(description='Vehicle Route Optimizer')
    default_data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'all_delivery_data.csv')
    parser.add_argument('--data', default=default_data_path,
                      help='Path to delivery data CSV file')
    parser.add_argument('--debug', action='store_true',
                      help='Enable debug logging')
    return parser.parse_args()

def list_data_files():
    """List and enumerate data files with letters"""
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    data_files = [f for f in os.listdir(data_dir) if f.endswith('.csv')]
    data_files.sort()
    
    file_map = {letter: filename for letter, filename in zip(string.ascii_uppercase, data_files)}
    
    print("\nAvailable datasets:")
    for letter, filename in file_map.items():
        print(f"{letter}: {filename}")
    print("\nEnter '0' to process all files")
    
    return file_map

def get_user_selection(file_map):
    """Get user input for file selection"""
    while True:
        selection = input("\nEnter letters for datasets to process (comma-separated, e.g. A,B,C) or '0' for all: ").strip()
        
        # Handle "process all" option
        if selection == '0':
            return list(file_map.keys())
        
        # Handle specific file selection
        letters = [l.strip().upper() for l in selection.split(',')]
        invalid_letters = [l for l in letters if l not in file_map]
        
        if invalid_letters:
            print(f"Invalid selection: {','.join(invalid_letters)}")
            continue
            
        return letters

def process_dataset(filepath):
    """Process a single dataset"""
    filename = os.path.basename(filepath)
    
    # Create test log directory and configure logging
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'output')
    test_log_dir = os.path.join(output_dir, 'test_log')
    os.makedirs(test_log_dir, exist_ok=True)
    
    # Set up file handler with custom formatter
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(test_log_dir, f'validation_log_{os.path.splitext(filename)[0]}_{timestamp}.txt')
    
    # Create file handler with formatting
    file_handler = logging.FileHandler(log_file)
    formatter = logging.Formatter('%(message)s')  # Just the message without timestamp
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    
    # Add handler to logger
    logger = logging.getLogger(__name__)
    logger.addHandler(file_handler)
    
    try:
        data_loader = DeliveryDataLoader(filepath)
        ors_client = ORSClient()
        optimizer = RouteOptimizer(data_loader, ors_client)
        route_sequence = optimizer.optimize_route()
        
        # Log dataset information
        logger.info(f"Dataset: {filename}")
        logger.info("=" * 50)
        logger.info(f"Total Stops: {len(route_sequence)}")
        logger.info(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("-" * 50)
        
        # Add validation with logging
        validator = RouteValidator(route_sequence, HUB_LOCATION, ors_client, logger)
        validation_results = validator.compare_methods()
        
        if not validation_results:  # Check for empty list
            logger.warning("Validation produced no results")
            validation_results = []  # Ensure we have an empty list
        
        # Group by zone
        zones = {}
        for stop in route_sequence:
            zone = stop['zone']
            if zone not in zones:
                zones[zone] = []
            zones[zone].append(stop)
        
        # Process each zone
        start_time = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
        
        # Process zones and calculate times
        for zone, stops in zones.items():
            total_zone_distance = 0
            current_time = start_time
            
            for i, stop in enumerate(stops, 1):
                stop['stop_number'] = i
                total_zone_distance += stop['distance']
                stop['total_distance'] = total_zone_distance
                
                travel_time = (stop['distance'] / 1000) * (60 / 30)  # minutes
                service_time = 4  # Changed from 6 to 4 minutes per stop
                
                current_time += timedelta(minutes=travel_time + service_time)
                stop['arrival_time'] = current_time.strftime('%H:%M')
                
                # For last stop, calculate return but don't add to total_distance
                if i == len(stops):  # Last stop
                    return_route = ors_client.get_route_details(
                        stop['coordinates'],
                        HUB_LOCATION
                    )
                    return_distance = return_route['features'][0]['properties']['segments'][0]['distance']
                    stop['return_distance'] = return_distance
                    
                    # Update final time with return journey
                    return_time = (return_distance / 1000) * (60 / 30)
                    current_time += timedelta(minutes=return_time)
                    stop['return_time'] = current_time.strftime('%H:%M')
                
                stop['remaining_stops'] = len(stops) - i
        
        # Generate maps using original filename in maps directory
        maps_dir = os.path.join(output_dir, 'maps')
        os.makedirs(maps_dir, exist_ok=True)
        output_file = os.path.join(maps_dir, os.path.splitext(filename)[0] + '.html')
        visualizer = MapVisualizer(zones, ors_client)
        visualizer.generate_map(output_file)
        
        return zones, validation_results
        
    except Exception as e:
        logger.error(f"Error processing dataset: {e}")
        return None, []  # Return empty list for validation_results
        
    finally:
        logger.removeHandler(file_handler)
        file_handler.close()

def create_route_summary(zones: dict, filename: str, validation_results: list) -> pd.DataFrame:
    """Create route summary dataframe including hub start/end points and validation results"""
    rows = []
    
    # Add starting point (hub)
    rows.append({
        'Stop Number': 'Starting Point',
        'Zone': '-',
        'Address': 'SMC Complex Hub',
        'Longitude': HUB_LOCATION[0],
        'Latitude': HUB_LOCATION[1],
        'Arrival Time': '08:00',
        'Distance from Hub': 0,
        'Total km Traveled': 0
    })
    
    # Add all stops in order
    for zone, stops in zones.items():
        for stop in stops:
            rows.append({
                'Stop Number': f"Stop {stop['stop_number']}",
                'Zone': stop['zone'],
                'Address': stop['address'],
                'Longitude': stop['coordinates'][0],
                'Latitude': stop['coordinates'][1],
                'Arrival Time': stop['arrival_time'],
                'Distance from Hub': stop['distance_from_hub']/1000,
                'Total km Traveled': stop['total_distance']/1000
            })
    
    # Add ending point (return to hub)
    last_stop = next(iter(zones.values()))[-1]  # Get last stop
    rows.append({
        'Stop Number': 'Ending Point',
        'Zone': '-',
        'Address': 'SMC Complex Hub',
        'Longitude': HUB_LOCATION[0],
        'Latitude': HUB_LOCATION[1],
        'Arrival Time': last_stop['return_time'],
        'Distance from Hub': 0,
        'Total km Traveled': (last_stop['total_distance'] + last_stop['return_distance'])/1000
    })
    
    # Add spacing rows
    rows.append({key: '' for key in rows[0].keys()})
    rows.append({key: '' for key in rows[0].keys()})
    
    # Add validation results header
    rows.append({
        'Stop Number': '=== ROUTE OPTIMIZATION TEST RESULTS ===',
        'Zone': '',
        'Address': '',
        'Longitude': '',
        'Latitude': '',
        'Arrival Time': '',
        'Distance from Hub': '',
        'Total km Traveled': ''
    })
    
    # Add column headers for test results
    rows.append({
        'Stop Number': 'Method',
        'Zone': 'Distance (km)',
        'Address': 'Time (min)',
        'Longitude': 'Stops',
        'Latitude': 'Avg Time/Stop',
        'Arrival Time': 'Redundancy',
        'Distance from Hub': '% from Optimal',
        'Total km Traveled': ''
    })
    
    # Add test results
    for result in validation_results:
        rows.append({
            'Stop Number': result[0],  # Method
            'Zone': result[1],         # Distance
            'Address': result[2],      # Time
            'Longitude': result[3],    # Stops
            'Latitude': result[4],     # Avg Time/Stop
            'Arrival Time': result[5], # Redundancy
            'Distance from Hub': result[6],  # % from Optimal
            'Total km Traveled': ''
        })
    
    return pd.DataFrame(rows)

def main():
    args = parse_args()
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    try:
        file_map = list_data_files()
        if not file_map:
            logger.error("No CSV files found in data directory")
            sys.exit(1)
        
        selected_letters = get_user_selection(file_map)
        if not selected_letters:
            logger.error("No datasets selected")
            sys.exit(1)
        
        # Process each selected dataset
        for letter in selected_letters:
            filename = file_map[letter]
            filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', filename)
            
            logger.info(f"\nProcessing {filename}...")
            zones, validation_results = process_dataset(filepath)
            
            if not zones or not validation_results:
                logger.error(f"Error processing {filename}")
                continue
            
            # Generate map
            output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'output')
            maps_dir = os.path.join(output_dir, 'maps')
            os.makedirs(maps_dir, exist_ok=True)
            
            output_file = os.path.join(maps_dir, os.path.splitext(filename)[0] + '.html')
            visualizer = MapVisualizer(zones, ORSClient())
            visualizer.generate_map(output_file)
            
        logger.info("\nAll datasets processed successfully!")
        
    except KeyboardInterrupt:
        logger.info("\nProcessing interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()