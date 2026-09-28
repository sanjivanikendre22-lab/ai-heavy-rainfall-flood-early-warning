import os
import requests
import struct
import numpy as np
import random
from datetime import datetime, timedelta

OWM_API_KEY = os.environ.get('OPENWEATHERMAP_API_KEY', '')

def get_live_weather(lat, lng):
    if OWM_API_KEY:
        try:
            url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lng}&appid={OWM_API_KEY}&units=metric"
            resp = requests.get(url).json()
            return {
                "temperature": resp['main']['temp'],
                "humidity": resp['main']['humidity'],
                "pressure": resp['main']['pressure'],
                "wind_speed": resp['wind']['speed'],
                "rainfall_1h": resp.get('rain', {}).get('1h', 0),
                "simulated": False
            }
        except Exception as e:
            pass
            
    # Fallback simulation
    return {
        "temperature": round(random.uniform(22.0, 35.0), 1),
        "humidity": round(random.uniform(60, 95), 1),
        "pressure": round(random.uniform(990, 1015), 1),
        "wind_speed": round(random.uniform(2.0, 15.0), 1),
        "rainfall_1h": round(random.uniform(0, 20), 1) if random.random() > 0.5 else 0,
        "simulated": True
    }

def get_forecast(lat, lng, days=5):
    forecast = []
    base_temp = random.uniform(24, 32)
    for i in range(days):
        forecast.append({
            "day": i + 1,
            "date": (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d"),
            "temperature": round(base_temp + random.uniform(-3, 3), 1),
            "humidity": round(random.uniform(70, 95), 1),
            "predicted_rainfall_mm": round(random.uniform(0, 150), 1) if random.random() > 0.3 else 0,
        })
    return forecast

def parse_grd_file(filepath):
    """
    Parses IMD .grd binary file.
    Assumes 31x31 grid, float32, covering India ~6.5N-38.5N, 66.5E-100.5E at 0.25 deg res.
    """
    if not os.path.exists(filepath):
        return {"error": "File not found", "data": []}
        
    grid_size = 31 * 31
    data = []
    try:
        with open(filepath, 'rb') as f:
            raw_bytes = f.read()
            # 31x31 floats = 961 floats. 961 * 4 = 3844 bytes.
            if len(raw_bytes) >= grid_size * 4:
                unpacked = struct.unpack(f"{grid_size}f", raw_bytes[:grid_size*4])
                # Convert to 2D numpy array and then list
                grid_2d = np.array(unpacked).reshape((31, 31))
                data = grid_2d.tolist()
            else:
                return {"error": "Invalid GRD file size", "data": []}
        return {
            "resolution": 0.25,
            "bbox": {"lat_min": 6.5, "lat_max": 38.5, "lng_min": 66.5, "lng_max": 100.5},
            "grid_shape": [31, 31],
            "data": data
        }
    except Exception as e:
        return {"error": str(e), "data": []}

def get_radar_simulation(lat, lng):
    """Generates realistic simulated radar data patterns (reflectivity dbZ)."""
    grid = []
    # 10x10 radar grid centered on lat/lng
    for r in range(10):
        row = []
        for c in range(10):
            dist_from_center = ((r-5)**2 + (c-5)**2)**0.5
            # Higher reflectivity near center if raining
            dbz = max(0, 50 - (dist_from_center * 8) + random.uniform(-10, 10))
            row.append(round(dbz, 1))
        grid.append(row)
    return {
        "center": {"lat": lat, "lng": lng},
        "dbz_grid": grid,
        "timestamp": datetime.now().isoformat()
    }

def get_satellite_simulation(lat, lng):
    """Generates simulated satellite cloud/rain data."""
    return {
        "cloud_cover_percent": round(random.uniform(40, 100), 1),
        "cloud_top_temperature": round(random.uniform(-60, -20), 1),
        "water_vapor_index": round(random.uniform(0.5, 1.0), 2)
    }

def fuse_data_sources(live_weather, radar, satellite, imd_data):
    """Combine all sources into unified prediction input"""
    return {
        "fused_timestamp": datetime.now().isoformat(),
        "live": live_weather,
        "radar": radar,
        "satellite": satellite,
        "historical_imd": imd_data,
        "composite_risk_score": round((live_weather.get('rainfall_1h', 0) * 0.4) + 
                                     (satellite.get('cloud_cover_percent', 0) * 0.2) + 
                                     (random.uniform(0, 10)), 2)
    }
