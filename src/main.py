import sys
import os
import argparse
import logging
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

def main():
    args = parse_args()
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    try:
        # Initialize components
        logger.info("Loading delivery data...")
        data_loader = DeliveryDataLoader(args.data)
        
        logger.info("Initializing ORS client...")
        ors_client = ORSClient()
        
        # Initialize components and optimize route
        optimizer = RouteOptimizer(data_loader, ors_client)
        route_sequence = optimizer.optimize_route()
        
        # Group and process routes by zone
        zones = {}
        for stop in route_sequence:
            zone = stop['zone']
            if zone not in zones:
                zones[zone] = []
            zones[zone].append(stop)
        
        # Set delivery start time to 8:00 AM
        start_time = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
        
        # Renumber stops and recalculate per zone
        logger.info(f"Processing {len(zones)} zones...")
        for zone, stops in zones.items():
            total_zone_distance = 0
            current_time = start_time  # Reset time for each zone
            
            for i, stop in enumerate(stops, 1):
                # Reset stop number for this zone
                stop['stop_number'] = i
                
                # Calculate cumulative distance and time
                prev_stops_distance = sum(s['distance'] for s in stops[:i-1])
                stop['total_distance'] = stop['distance_from_hub'] + prev_stops_distance
                
                # Calculate arrival time (assuming 30km/h average speed + 6 min per stop)
                travel_time = (stop['distance'] / 1000) * (60 / 30)  # minutes
                service_time = 6  # minutes per stop
                
                current_time += timedelta(minutes=travel_time + service_time)
                stop['arrival_time'] = current_time.strftime('%H:%M')
                
                total_zone_distance += stop['distance']
            
            # Update remaining stops count for this zone
            total_stops = len(stops)
            for i, stop in enumerate(stops):
                stop['remaining_stops'] = total_stops - i
            
            logger.debug(f"Zone {zone}: {total_stops} stops, {total_zone_distance/1000:.2f}km total distance")
        
        # Generate maps for each zone
        logger.info(f"Generating {len(zones)} zone-based maps...")
        visualizer = MapVisualizer(zones, ors_client)
        visualizer.generate_maps()
        
        logger.info("Route optimization completed successfully!")
        logger.info(f"Total zones processed: {len(zones)}")
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()