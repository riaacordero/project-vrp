from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
import numpy as np
from datetime import datetime, timedelta
import random
import math
import logging
from tabulate import tabulate

logger = logging.getLogger(__name__)

class RouteValidator:
    def __init__(self, stops, hub_location, ors_client, logger):
        self.stops = stops
        self.hub_location = hub_location
        self.ors_client = ors_client
        self.logger = logger
        self.AVERAGE_SPEED = 30  # km/h
        self.SERVICE_TIME = 4    # minutes

    def calculate_euclidean_distance(self, point1, point2):
        """Calculate straight-line distance between two points"""
        R = 6371  # Earth's radius in km
        lat1, lon1 = math.radians(point1[1]), math.radians(point1[0])
        lat2, lon2 = math.radians(point2[1]), math.radians(point2[0])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        return R * c * 1000  # Convert to meters

    def get_random_route(self):
        """Generate random route"""
        random_stops = self.stops.copy()
        random.shuffle(random_stops)
        return random_stops

    def get_euclidean_route(self):
        """Generate route based on straight-line distances"""
        remaining_stops = self.stops.copy()
        route = []
        current = self.hub_location
        
        while remaining_stops:
            distances = [self.calculate_euclidean_distance(current, stop['coordinates']) 
                        for stop in remaining_stops]
            nearest = remaining_stops[distances.index(min(distances))]
            route.append(nearest)
            current = nearest['coordinates']
            remaining_stops.remove(nearest)
            
        return route

    def solve_ortools(self):
        """Generate route using OR-Tools"""
        # Create distance matrix
        size = len(self.stops) + 1
        matrix = np.zeros((size, size))
        locations = [self.hub_location] + [stop['coordinates'] for stop in self.stops]
        
        for i in range(size):
            for j in range(size):
                if i != j:
                    matrix[i][j] = self.ors_client.get_route_details(
                        locations[i], locations[j]
                    )['features'][0]['properties']['segments'][0]['distance']
        
        # Set up OR-Tools
        manager = pywrapcp.RoutingIndexManager(size, 1, 0)
        routing = pywrapcp.RoutingModel(manager)
        
        def distance_callback(from_idx, to_idx):
            from_node = manager.IndexToNode(from_idx)
            to_node = manager.IndexToNode(to_idx)
            return int(matrix[from_node][to_node])
            
        transit_callback_index = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
        
        # Solve
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        )
        solution = routing.SolveWithParameters(search_parameters)
        
        if solution:
            ordered_stops = []
            index = routing.Start(0)
            while not routing.IsEnd(index):
                node = manager.IndexToNode(index)
                if node > 0:  # Skip depot
                    ordered_stops.append(self.stops[node-1])
                index = solution.Value(routing.NextVar(index))
            return ordered_stops
        return None

    def calculate_metrics(self, route):
        """Calculate total distance and time for a route"""
        total_distance = 0
        total_time = 0
        current = self.hub_location
        
        for stop in route:
            # Calculate distance and time to stop
            route_details = self.ors_client.get_route_details(current, stop['coordinates'])
            distance = route_details['features'][0]['properties']['segments'][0]['distance']
            travel_time = (distance / 1000) * (60 / self.AVERAGE_SPEED)
            
            total_distance += distance
            total_time += travel_time + self.SERVICE_TIME
            current = stop['coordinates']
        
        # Add return to hub
        route_details = self.ors_client.get_route_details(current, self.hub_location)
        return_distance = route_details['features'][0]['properties']['segments'][0]['distance']
        return_time = (return_distance / 1000) * (60 / self.AVERAGE_SPEED)
        
        total_distance += return_distance
        total_time += return_time
        
        return total_distance, total_time

    def calculate_extended_metrics(self, route, total_distance, total_time):
        """Calculate additional validation metrics for a route"""
        num_stops = len(route)
        avg_time_per_stop = total_time / num_stops if num_stops > 0 else 0
        
        # Calculate route redundancy by checking revisited areas
        visited_areas = set()
        redundant_paths = 0
        
        # Define area by rounding coordinates to 4 decimal places
        for stop in route:
            area = (round(stop['coordinates'][0], 4), round(stop['coordinates'][1], 4))
            if area in visited_areas:
                redundant_paths += 1
            visited_areas.add(area)
            
        return {
            "num_stops": num_stops,
            "avg_time_per_stop": avg_time_per_stop,
            "redundant_paths": redundant_paths,
        }

    def compare_methods(self):
        """Compare different routing methods with all metrics in single table"""
        try:
            results = []
            metrics_by_method = {}
            
            # 1. Nearest Neighbor analysis
            self.logger.info("\n=== Nearest Neighbor Algorithm Analysis ===")
            nn_route = self.get_nearest_neighbor_route_detailed()
            nn_distance, nn_time = self.calculate_metrics(nn_route)
            metrics_by_method["Nearest Neighbor"] = {
                "distance": nn_distance/1000,
                "time": nn_time,
                **self.calculate_extended_metrics(nn_route, nn_distance, nn_time)
            }
            
            # Create results array with proper structure
            for method, metrics in metrics_by_method.items():
                row = [
                    method,
                    f"{metrics['distance']:.2f}",
                    f"{metrics['time']:.1f}",
                    metrics['num_stops'],
                    f"{metrics['avg_time_per_stop']:.1f}",
                    metrics['redundant_paths'],
                    metrics.get('diff_from_optimal', 'N/A')
                ]
                results.append(row)
            
            # Print results table
            headers = [
                "Method",
                "Distance (km)",
                "Time (min)",
                "Stops",
                "Avg Time/Stop",
                "Redundancy",
                "% from Optimal"
            ]
            self.logger.info("\nRoute Optimization Analysis:")
            self.logger.info(tabulate(results, headers=headers, tablefmt="grid"))
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error in compare_methods: {e}")
            return []  # Return empty list instead of None

    def get_nearest_neighbor_route_detailed(self):
        """Generate route using Nearest Neighbor algorithm with detailed logging"""
        unvisited_stops = self.stops.copy()
        route = []
        current_location = self.hub_location
        
        self.logger.info("\nNEAREST NEIGHBOR ALGORITHM - DECISION PROCESS")
        self.logger.info("============================================")
        self.logger.info(f"Starting Point: SMC Complex Hub ({self.hub_location[0]:.4f}, {self.hub_location[1]:.4f})")
        
        step = 1
        total_stops = len(unvisited_stops)
        total_distance = 0
        
        while unvisited_stops:
            self.logger.info(f"\nITERATION {step}/{total_stops}")
            self.logger.info("--------------------")
            self.logger.info(f"Current Position: ({current_location[0]:.4f}, {current_location[1]:.4f})")
            
            # Calculate and sort distances to all remaining stops
            distances = []
            self.logger.info("\nCANDIDATE STOPS ANALYSIS:")
            
            # Sort stops by distance for a clearer view of options
            for stop in unvisited_stops:
                route_details = self.ors_client.get_route_details(
                    current_location, 
                    stop['coordinates']
                )
                distance = route_details['features'][0]['properties']['segments'][0]['distance']
                distances.append({
                    'stop': stop,
                    'distance': distance
                })
                
            # Sort distances to show all options in order
            sorted_distances = sorted(distances, key=lambda x: x['distance'])
            
            # Show all options with their rankings
            for rank, option in enumerate(sorted_distances, 1):
                stop = option['stop']
                distance = option['distance']
                self.logger.info(f"\nRank {rank}:")
                self.logger.info(f"  Original Stop #{stop['stop_number']} - Zone {stop['zone']}")
                self.logger.info(f"  Distance from current: {distance/1000:.2f} km")
                self.logger.info(f"  Address: {stop['address']}")
                
            # Select nearest stop
            nearest = sorted_distances[0]
            total_distance += nearest['distance']
            
            self.logger.info("\nDECISION")
            self.logger.info("---------")
            self.logger.info(f"Selected: Original Stop #{nearest['stop']['stop_number']} (Visit Order: {step})")
            self.logger.info(f"Reason: Closest stop at {nearest['distance']/1000:.2f} km")
            self.logger.info(f"Progressive Route Distance: {total_distance/1000:.2f} km")
            
            route.append(nearest['stop'])
            current_location = nearest['stop']['coordinates']
            unvisited_stops.remove(nearest['stop'])
            step += 1