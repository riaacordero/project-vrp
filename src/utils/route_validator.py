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
    def __init__(self, stops, hub_location, ors_client):
        self.stops = stops
        self.hub_location = hub_location
        self.ors_client = ors_client
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
        results = []
        metrics_by_method = {}
        
        # Calculate metrics for each method
        # 1. Nearest Neighbor (current solution)
        nn_distance, nn_time = self.calculate_metrics(self.stops)
        metrics_by_method["Nearest Neighbor"] = {
            "distance": nn_distance/1000,
            "time": nn_time,
            **self.calculate_extended_metrics(self.stops, nn_distance, nn_time)
        }
        
        # 2. Random Order
        random_route = self.get_random_route()
        rand_distance, rand_time = self.calculate_metrics(random_route)
        metrics_by_method["Random Order"] = {
            "distance": rand_distance/1000,
            "time": rand_time,
            **self.calculate_extended_metrics(random_route, rand_distance, rand_time)
        }
        
        # 3. Euclidean Distance
        euclidean_route = self.get_euclidean_route()
        euc_distance, euc_time = self.calculate_metrics(euclidean_route)
        metrics_by_method["Euclidean Distance"] = {
            "distance": euc_distance/1000,
            "time": euc_time,
            **self.calculate_extended_metrics(euclidean_route, euc_distance, euc_time)
        }
        
        # 4. OR-Tools (considered optimal)
        ortools_route = self.solve_ortools()
        if ortools_route:
            ort_distance, ort_time = self.calculate_metrics(ortools_route)
            metrics_by_method["OR-Tools"] = {
                "distance": ort_distance/1000,
                "time": ort_time,
                **self.calculate_extended_metrics(ortools_route, ort_distance, ort_time)
            }
            
            # Calculate % difference from optimal
            optimal_distance = ort_distance/1000
            for method, metrics in metrics_by_method.items():
                if method != "OR-Tools":
                    diff_from_optimal = ((metrics["distance"] - optimal_distance) / optimal_distance) * 100
                    metrics["diff_from_optimal"] = diff_from_optimal
        
        # Create combined results table
        for method, metrics in metrics_by_method.items():
            row = [
                method,
                f"{metrics['distance']:.2f}",
                f"{metrics['time']:.1f}",
                metrics['num_stops'],
                f"{metrics['avg_time_per_stop']:.1f}",
                metrics['redundant_paths'],
                f"{metrics.get('diff_from_optimal', 'N/A')}%" if metrics.get('diff_from_optimal') is not None else "N/A"
            ]
            results.append(row)
        
        # Print combined table
        headers = [
            "Method",
            "Distance (km)",
            "Time (min)",
            "Stops",
            "Avg Time/Stop",
            "Redundancy",
            "% from Optimal"
        ]
        print("\nRoute Optimization Analysis:")
        print(tabulate(results, headers=headers, tablefmt="grid"))
        
        return results