import sys
import os
import argparse
import logging
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
    default_data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'delivery_data.csv')
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
        
        # Optimize route
        logger.info("Calculating optimal route...")
        optimizer = RouteOptimizer(data_loader, ors_client)
        route_sequence = optimizer.optimize_route()
        
        # Generate map
        logger.info("Generating route visualization...")
        visualizer = MapVisualizer(route_sequence, ors_client)
        visualizer.generate_map()
        
        logger.info("Route optimization completed successfully!")
        logger.info(f"Total stops: {len(route_sequence)}")
        logger.info("Map saved to route_map.html")
        
    except FileNotFoundError as e:
        logger.error(f"Data file not found: {e}")
        sys.exit(1)
    except ValueError as e:
        logger.error(f"Invalid data format: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()