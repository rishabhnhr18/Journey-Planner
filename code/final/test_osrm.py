import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from osrm_helper import OSRMHelper, get_distance_matrix

def test_haversine():
    print("Testing Haversine Mode...")
    helper = OSRMHelper(mode="haversine")
    coords = [(24.7136, 46.6753), (24.7236, 46.6853)]
    dist, dur = get_distance_matrix(coords, helper, avg_speed_kmph=30.0)
    print(f"Coordinates: {coords}")
    print(f"Distance Matrix (km):\n{dist}")
    print(f"Duration Matrix (min):\n{dur}")
    assert dist[0, 1] > 0
    assert dur[0, 1] > 0
    print("Haversine Mode Test: PASSED\n")

def test_http_osrm():
    print("Testing OSRM HTTP Mode (against public demo server)...")
    helper = OSRMHelper(mode="http", server_url="http://router.project-osrm.org")
    # Coordinates in Riyadh (Saudi Arabia)
    coords = [(24.7136, 46.6753), (24.7236, 46.6853)]
    
    print("1. Testing Table Service...")
    table = helper.get_table(coords)
    if table:
        print("Table query succeeded!")
        print(f"Distances: {table['distances']}")
        print(f"Durations: {table['durations']}")
    else:
        print("Table query failed (Server might be unreachable, which is expected if offline or demo server is down).")

    print("\n2. Testing Route Service...")
    route = helper.get_route(coords)
    if route:
        print("Route query succeeded!")
        print(f"Distance: {route['distance']} m")
        print(f"Duration: {route['duration']} s")
        print(f"Geometry points count: {len(route['geometry'])}")
    else:
        print("Route query failed (Server might be unreachable, which is expected if offline or demo server is down).")

if __name__ == "__main__":
    test_haversine()
    try:
        test_http_osrm()
    except Exception as e:
        print(f"HTTP test failed with exception: {e}")
