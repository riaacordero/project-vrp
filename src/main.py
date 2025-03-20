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
    
    # Create output directories if they don't exist
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'output')
    maps_dir = os.path.join(output_dir, 'maps')
    os.makedirs(maps_dir, exist_ok=True)
    
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
    output_file = os.path.join(maps_dir, os.path.splitext(filename)[0] + '.html')
    visualizer = MapVisualizer(zones, ors_client)
    visualizer.generate_map(output_file)
    
    return zones

def create_route_summary(zones: dict, filename: str) -> pd.DataFrame:
    """Create route summary dataframe including hub start/end points"""
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
        
        # Create Excel writer with timestamp in lists directory
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        lists_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'output',
            'lists'
        )
        os.makedirs(lists_dir, exist_ok=True)
        
        excel_path = os.path.join(lists_dir, f'route_summary_{timestamp}.xlsx')
        
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            for letter in selected_letters:
                filename = file_map[letter]
                filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', filename)
                
                # Process dataset and get zones
                zones = process_dataset(filepath)
                
                # Create summary sheet
                sheet_name = os.path.splitext(filename)[0][:31]  # Excel limits sheet names to 31 chars
                summary_df = create_route_summary(zones, filename)
                summary_df.to_excel(writer, sheet_name=sheet_name, index=False)
                
                # Auto-adjust column widths
                worksheet = writer.sheets[sheet_name]
                for idx, col in enumerate(summary_df.columns):
                    max_length = max(
                        summary_df[col].astype(str).apply(len).max(),
                        len(col)
                    )
                    worksheet.column_dimensions[chr(65 + idx)].width = max_length + 2
        
        logger.info(f"\nGenerated route summary: {excel_path}")
        logger.info("\nAll datasets processed successfully!")
        
    except KeyboardInterrupt:
        logger.info("\nProcessing interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()