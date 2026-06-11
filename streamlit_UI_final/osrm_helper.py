import math
import requests
import numpy as np
from typing import List, Tuple, Dict, Any, Optional

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R    = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a    = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

class OSRMHelper:
    def __init__(self, mode: str = "haversine", server_url: str = "http://router.project-osrm.org", data_path: Optional[str] = None):
        self.mode = mode.lower() if mode else "haversine"
        self.server_url = server_url.rstrip('/') if server_url else "http://router.project-osrm.org"
        self.data_path = data_path
        self._engine = None
        self._osrm_module = None
        
        if self.mode == "native":
            try:
                import osrm
                self._osrm_module = osrm
                if self.data_path:
                    self._engine = osrm.OSRM(self.data_path)
                    print(f"[OSRM] Initialized native engine with {self.data_path}")
                else:
                    print("[OSRM WARNING] Native mode requested but no data path provided. Falling back to HTTP mode.")
                    self.mode = "http"
            except ImportError:
                print("[OSRM WARNING] Native mode requested but 'osrm-bindings' package is not installed. Falling back to HTTP mode.")
                self.mode = "http"
            except Exception as e:
                print(f"[OSRM ERROR] Failed to initialize native OSRM: {e}. Falling back to HTTP mode.")
                self.mode = "http"

    def get_table(self, coordinates: List[Tuple[float, float]]) -> Optional[Dict[str, Any]]:
        """
        coordinates: List of (latitude, longitude) tuples.
        Returns:
            Dict containing:
                "durations": 2D list of travel times in seconds
                "distances": 2D list of travel distances in meters
            or None on failure.
        """
        if not coordinates or len(coordinates) < 2:
            return None
            
        if self.mode == "native" and self._engine:
            try:
                # Native bindings coordinates: (longitude, latitude)
                lon_lat_coords = [(lng, lat) for lat, lng in coordinates]
                params = self._osrm_module.TableParameters(
                    coordinates=lon_lat_coords,
                    annotations=["duration", "distance"]
                )
                res = self._engine.Table(params)
                # Parse native result
                return {
                    "durations": res.get("durations", []),
                    "distances": res.get("distances", [])
                }
            except Exception as e:
                print(f"[OSRM ERROR] Native Table query failed: {e}")
                # Fallback to HTTP if native fails
                
        if self.mode == "http":
            n = len(coordinates)
            if n <= 100:
                # HTTP API format: lon,lat;lon,lat;...
                coord_strings = [f"{lng},{lat}" for lat, lng in coordinates]
                coord_query = ";".join(coord_strings)
                url = f"{self.server_url}/table/v1/driving/{coord_query}?annotations=duration,distance"
                
                try:
                    response = requests.get(url, timeout=4)
                    if response.status_code == 200:
                        data = response.json()
                        if data.get("code") == "Ok":
                            return {
                                "durations": data.get("durations"),
                                "distances": data.get("distances")
                            }
                        else:
                            print(f"[OSRM WARNING] HTTP Table returned code: {data.get('code')}")
                    else:
                        print(f"[OSRM WARNING] HTTP Table request failed with status: {response.status_code}")
                        try:
                            print(f"[OSRM Error Details]: {response.text}")
                        except Exception:
                            pass
                except Exception as e:
                    print(f"[OSRM ERROR] HTTP Table request failed: {e}")
                    print("[OSRM WARNING] Automatically falling back to Haversine mode for this session to prevent timeout lags.")
                    self.mode = "haversine"
            else:
                # Chunked table request to support >100 coordinates
                durations = [[0.0] * n for _ in range(n)]
                distances = [[0.0] * n for _ in range(n)]
                
                chunk_size = 45
                chunks = [list(range(i, min(i + chunk_size, n))) for i in range(0, n, chunk_size)]
                
                for r_idx, chunk_r in enumerate(chunks):
                    for s_idx, chunk_s in enumerate(chunks):
                        if r_idx == s_idx:
                            sub_coords = [coordinates[i] for i in chunk_r]
                            coord_strings = [f"{lng},{lat}" for lat, lng in sub_coords]
                            coord_query = ";".join(coord_strings)
                            url = f"{self.server_url}/table/v1/driving/{coord_query}?annotations=duration,distance"
                            try:
                                response = requests.get(url, timeout=4)
                                if response.status_code == 200:
                                    data = response.json()
                                    if data.get("code") == "Ok":
                                        sub_durs = data.get("durations")
                                        sub_dists = data.get("distances")
                                        for u_idx, u in enumerate(chunk_r):
                                            for v_idx, v in enumerate(chunk_r):
                                                durations[u][v] = sub_durs[u_idx][v_idx]
                                                distances[u][v] = sub_dists[u_idx][v_idx]
                                    else:
                                        print(f"[OSRM WARNING] HTTP Chunked Table returned code: {data.get('code')}")
                                        return None
                                else:
                                    print(f"[OSRM WARNING] HTTP Chunked Table failed with status: {response.status_code}")
                                    return None
                            except Exception as e:
                                print(f"[OSRM ERROR] HTTP Chunked Table failed: {e}")
                                print("[OSRM WARNING] Automatically falling back to Haversine mode for this session to prevent timeout lags.")
                                self.mode = "haversine"
                                return None
                        else:
                            sub_coords = [coordinates[i] for i in chunk_r] + [coordinates[j] for j in chunk_s]
                            coord_strings = [f"{lng},{lat}" for lat, lng in sub_coords]
                            coord_query = ";".join(coord_strings)
                            
                            len_r = len(chunk_r)
                            len_s = len(chunk_s)
                            
                            sources = ";".join(str(i) for i in range(len_r))
                            destinations = ";".join(str(len_r + j) for j in range(len_s))
                            
                            url = f"{self.server_url}/table/v1/driving/{coord_query}?annotations=duration,distance&sources={sources}&destinations={destinations}"
                            try:
                                response = requests.get(url, timeout=4)
                                if response.status_code == 200:
                                    data = response.json()
                                    if data.get("code") == "Ok":
                                        sub_durs = data.get("durations")
                                        sub_dists = data.get("distances")
                                        for u_idx, u in enumerate(chunk_r):
                                            for v_idx, v in enumerate(chunk_s):
                                                durations[u][v] = sub_durs[u_idx][v_idx]
                                                distances[u][v] = sub_dists[u_idx][v_idx]
                                    else:
                                        print(f"[OSRM WARNING] HTTP Chunked Table cross returned code: {data.get('code')}")
                                        return None
                                else:
                                    print(f"[OSRM WARNING] HTTP Chunked Table cross failed with status: {response.status_code}")
                                    return None
                            except Exception as e:
                                print(f"[OSRM ERROR] HTTP Chunked Table cross failed: {e}")
                                print("[OSRM WARNING] Automatically falling back to Haversine mode for this session to prevent timeout lags.")
                                self.mode = "haversine"
                                return None
                return {
                    "durations": durations,
                    "distances": distances
                }
                
        return None

    def get_route(self, coordinates: List[Tuple[float, float]], raise_errors: bool = False) -> Optional[Dict[str, Any]]:
        """
        coordinates: List of (latitude, longitude) tuples.
        Returns:
            Dict containing:
                "distance": total distance in meters
                "duration": total duration in seconds
                "geometry": list of (latitude, longitude) tuples along the road path
            or None on failure.
        """
        if not coordinates or len(coordinates) < 2:
            return None

        if self.mode == "native" and self._engine:
            try:
                lon_lat_coords = [(lng, lat) for lat, lng in coordinates]
                params = self._osrm_module.RouteParameters(
                    coordinates=lon_lat_coords,
                    geometries="geojson",
                    overview="full"
                )
                res = self._engine.Route(params)
                if "routes" in res and len(res["routes"]) > 0:
                    route = res["routes"][0]
                    distance = route.get("distance", 0.0)
                    duration = route.get("duration", 0.0)
                    geom_lon_lat = route.get("geometry", {}).get("coordinates", [])
                    geometry = [(lat, lon) for lon, lat in geom_lon_lat]
                    return {
                        "distance": distance,
                        "duration": duration,
                        "geometry": geometry
                    }
            except Exception as e:
                print(f"[OSRM ERROR] Native Route query failed: {e}")
                if raise_errors:
                    raise e

        if self.mode == "http":
            coord_strings = [f"{lng},{lat}" for lat, lng in coordinates]
            coord_query = ";".join(coord_strings)
            url = f"{self.server_url}/route/v1/driving/{coord_query}?overview=full&geometries=geojson"
            
            try:
                response = requests.get(url, timeout=4)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("code") == "Ok" and "routes" in data and len(data["routes"]) > 0:
                        route = data["routes"][0]
                        distance = route.get("distance", 0.0)
                        duration = route.get("duration", 0.0)
                        geom_lon_lat = route.get("geometry", {}).get("coordinates", [])
                        geometry = [(lat, lon) for lon, lat in geom_lon_lat]
                        return {
                            "distance": distance,
                            "duration": duration,
                            "geometry": geometry
                        }
                    else:
                        print(f"[OSRM WARNING] HTTP Route returned code: {data.get('code')}")
                        if raise_errors:
                            raise Exception(f"OSRM returned code: {data.get('code')}")
                else:
                    print(f"[OSRM WARNING] HTTP Route request failed with status: {response.status_code}")
                    try:
                        print(f"[OSRM Error Details]: {response.text}")
                    except Exception:
                        pass
                    if raise_errors:
                        raise Exception(f"HTTP request failed with status: {response.status_code}. Response: {response.text[:200]}")
            except Exception as e:
                print(f"[OSRM ERROR] HTTP Route request failed: {e}")
                if raise_errors:
                    raise e
                
        return None

def get_distance_matrix(coordinates: List[Tuple[float, float]], helper: Optional[OSRMHelper], avg_speed_kmph: float) -> Tuple[np.ndarray, np.ndarray]:
    """
    coordinates: List of (latitude, longitude) tuples.
    Returns:
        distances_km: 2D numpy array of pairwise distances in km.
        durations_min: 2D numpy array of pairwise travel times in minutes.
    """
    n = len(coordinates)
    distances_km = np.zeros((n, n))
    durations_min = np.zeros((n, n))
    
    osrm_data = None
    if helper and helper.mode != "haversine":
        osrm_data = helper.get_table(coordinates)
        
    if osrm_data and "distances" in osrm_data and "durations" in osrm_data:
        dist_matrix = osrm_data["distances"]
        dur_matrix = osrm_data["durations"]
        if dist_matrix and len(dist_matrix) == n and dur_matrix and len(dur_matrix) == n:
            for i in range(n):
                for j in range(n):
                    # distance in meters -> km
                    distances_km[i, j] = dist_matrix[i][j] / 1000.0 if dist_matrix[i][j] is not None else 0.0
                    # duration in seconds -> minutes
                    durations_min[i, j] = dur_matrix[i][j] / 60.0 if dur_matrix[i][j] is not None else 0.0
            return distances_km, durations_min

    # Fallback to Haversine
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            km = _haversine_km(coordinates[i][0], coordinates[i][1], coordinates[j][0], coordinates[j][1])
            distances_km[i, j] = km
            durations_min[i, j] = (km / avg_speed_kmph) * 60.0
            
    return distances_km, durations_min
