import sys
import os
import argparse
import logging
import string
from datetime import datetime, timedelta
from utils.data_loader import DeliveryDataLoader
from utils.ors_client import ORSClient
from models.route_optimizer import RouteOptimizer
from utils.map_visualizer import MapVisualizer

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
    
    return file_map

def get_user_selection(file_map):
    """Get user input for file selection"""
    while True:
        selection = input("\nEnter letters for datasets to process (comma-separated, e.g. A,B,C): ").strip()
        letters = [l.strip().upper() for l in selection.split(',')]
        
        invalid_letters = [l for l in letters if l not in file_map]
        if invalid_letters:
            print(f"Invalid selection: {','.join(invalid_letters)}")
            continue
            
        return letters

def process_dataset(filepath):
    """Process a single dataset"""
    filename = os.path.basename(filepath)
    logger.info(f"\nProcessing dataset: {filename}")
    
    # Create output directory if it doesn't exist
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'output')
    os.makedirs(output_dir, exist_ok=True)
    
    data_loader = DeliveryDataLoader(filepath)
    ors_client = ORSClient()
    optimizer = RouteOptimizer(data_loader, ors_client)
    route_sequence = optimizer.optimize_route()
    
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
            prev_stops_distance = sum(s['distance'] for s in stops[:i-1])
            stop['total_distance'] = stop['distance_from_hub'] + prev_stops_distance
            
            travel_time = (stop['distance'] / 1000) * (60 / 30)
            service_time = 6
            
            current_time += timedelta(minutes=travel_time + service_time)
            stop['arrival_time'] = current_time.strftime('%H:%M')
            
            total_zone_distance += stop['distance']
            stop['remaining_stops'] = len(stops) - i
    
    # Generate maps using original filename in output directory
    output_file = os.path.join(output_dir, os.path.splitext(filename)[0] + '.html')
    visualizer = MapVisualizer(zones, ors_client)
    visualizer.generate_map(output_file)
    
    return len(zones)

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
        
        for letter in selected_letters:
            filename = file_map[letter]
            filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', filename)
            zones_count = process_dataset(filepath)
            logger.info(f"Completed processing {filename}: {zones_count} zones")
        
        logger.info("\nAll datasets processed successfully!")
        
    except KeyboardInterrupt:
        logger.info("\nProcessing interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()