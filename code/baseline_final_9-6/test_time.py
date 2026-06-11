import time
import pandas as pd
import numpy as np
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

# Define a simple haversine function
import math
def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R    = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a    = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def test_solver(use_gls=True, time_limit_sec=1):
    # Let's generate a mock daily route with 15 customer stops
    np.random.seed(42)
    start_lat, start_lng = 24.5790, 46.8237  # Riyadh warehouse
    n_cust = 15
    df_c = pd.DataFrame({
        "gps_lat": np.random.uniform(24.5, 24.9, n_cust),
        "gps_lng": np.random.uniform(46.5, 46.9, n_cust)
    })

    def _get_node_coords(node_idx: int) -> tuple[float, float]:
        if node_idx <= 0 or node_idx > n_cust:
            return (start_lat, start_lng)
        row_c = df_c.loc[node_idx - 1]
        return (float(row_c["gps_lat"]), float(row_c["gps_lng"]))

    n_nodes = n_cust + 1
    manager = pywrapcp.RoutingIndexManager(n_nodes, 1, 0)
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        if to_node <= 0 or to_node > n_cust:
            return 0
        lat_i, lng_i = _get_node_coords(from_node)
        lat_j, lng_j = _get_node_coords(to_node)
        return int(_haversine_km(lat_i, lng_i, lat_j, lng_j) * 1000)

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    if use_gls:
        search_parameters.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )
    search_parameters.time_limit.seconds = time_limit_sec

    start = time.perf_counter()
    solution = routing.SolveWithParameters(search_parameters)
    end = time.perf_counter()

    if solution:
        # Get cost
        cost = solution.ObjectiveValue()
        # Reconstruct path
        index = routing.Start(0)
        path = []
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            if node > 0:
                path.append(node - 1)
            index = solution.Value(routing.NextVar(index))
        return True, cost, path, (end - start) * 1000
    else:
        return False, None, None, (end - start) * 1000

print("Running test...")
# Test 1: GLS with 1 second limit
ok, cost, path, duration = test_solver(use_gls=True, time_limit_sec=1)
print(f"GLS 1s: Found={ok}, Cost={cost}, Duration={duration:.2f}ms, Path={path}")

# Test 2: GLS with 5 second limit
ok, cost, path, duration = test_solver(use_gls=True, time_limit_sec=5)
print(f"GLS 5s: Found={ok}, Cost={cost}, Duration={duration:.2f}ms, Path={path}")

# Test 3: No GLS (Default Local Search) with 5 second limit
ok, cost, path, duration = test_solver(use_gls=False, time_limit_sec=5)
print(f"No GLS 5s: Found={ok}, Cost={cost}, Duration={duration:.2f}ms, Path={path}")

# Test 4: No GLS (Default Local Search) with 1 second limit
ok, cost, path, duration = test_solver(use_gls=False, time_limit_sec=1)
print(f"No GLS 1s: Found={ok}, Cost={cost}, Duration={duration:.2f}ms, Path={path}")
