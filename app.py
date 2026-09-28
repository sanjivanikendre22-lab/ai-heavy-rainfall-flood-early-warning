import os
import json
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from ml_model import RainfallPredictor
from alert_system import AlertManager
import data_sources

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# Global instances
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
IMD_CSV_PATH = os.path.join(DATA_DIR, 'rainfall_districtwise_daily_imd.csv')
CITIES_JSON_PATH = os.path.join(DATA_DIR, 'indian_cities.json')

predictor = RainfallPredictor(IMD_CSV_PATH)
alert_manager = AlertManager()

cities_data = []
if os.path.exists(CITIES_JSON_PATH):
    with open(CITIES_JSON_PATH, 'r') as f:
        cities_data = json.load(f)

def get_city_by_name(name):
    for c in cities_data:
        if c['name'].lower() == name.lower():
            return c
    return None

@app.route('/')
def index():
    # Ensure templates/index.html exists, or serve a simple response
    if os.path.exists(os.path.join(app.template_folder, 'index.html')):
        return send_from_directory(app.template_folder, 'index.html')
    return jsonify({"status": "success", "message": "SIH Prototype API Running"})

@app.route('/api/weather/<city>')
def api_weather(city):
    city_info = get_city_by_name(city)
    if not city_info:
        return jsonify({"status": "error", "message": "City not found"}), 404
        
    weather = data_sources.get_live_weather(city_info['lat'], city_info['lng'])
    return jsonify({"status": "success", "data": weather})

@app.route('/api/forecast/<city>')
def api_forecast(city):
    city_info = get_city_by_name(city)
    if not city_info:
        return jsonify({"status": "error", "message": "City not found"}), 404
        
    predictions = predictor.predict_rainfall(city_info['name'], city_info['state'], days_ahead=5)
    return jsonify({"status": "success", "data": predictions})

@app.route('/api/inundation/<city>')
def api_inundation(city):
    city_info = get_city_by_name(city)
    if not city_info:
        return jsonify({"status": "error", "message": "City not found"}), 404
        
    # Get short-term prediction to feed inundation model
    predictions = predictor.predict_rainfall(city_info['name'], city_info['state'], days_ahead=1)
    rain_mm = predictions[0]['rainfall_mm'] if predictions else 0
    
    inundation = predictor.predict_inundation(city_info, rain_mm)
    return jsonify({"status": "success", "data": inundation})

@app.route('/api/alerts')
def api_alerts():
    level = request.args.get('level')
    if level:
        alerts = alert_manager.get_alerts_by_level(level)
    else:
        alerts = alert_manager.get_active_alerts()
    return jsonify({"status": "success", "data": alerts})

@app.route('/api/alerts/generate')
def api_alerts_generate():
    all_preds = []
    for city in cities_data[:10]: # Demo: generate for top 10 cities
        preds = predictor.predict_rainfall(city['name'], city['state'], days_ahead=1)
        if preds:
            rain = preds[0]['rainfall_mm']
            inun = predictor.predict_inundation(city, rain)
            all_preds.append({
                "city_name": city['name'],
                "state_name": city['state'],
                "predicted_rainfall_mm": rain,
                "inundation_risk_level": inun['flood_risk_level'],
                "population": city.get('population', 0)
            })
            
    new_alerts = alert_manager.generate_alerts(all_preds)
    return jsonify({"status": "success", "data": {"generated_count": len(new_alerts), "alerts": new_alerts}})

@app.route('/api/historical/<city>')
def api_historical(city):
    city_info = get_city_by_name(city)
    if not city_info:
        return jsonify({"status": "error", "message": "City not found"}), 404
        
    records = predictor.get_district_data(city_info['state'], city_info['name'])
    return jsonify({"status": "success", "data": records[:100]}) # Limit to 100 for payload size

@app.route('/api/stations')
def api_stations():
    return jsonify({"status": "success", "data": cities_data})

@app.route('/api/district/<state>/<district>')
def api_district(state, district):
    records = predictor.get_district_data(state, district)
    return jsonify({"status": "success", "data": records[:100]})

@app.route('/api/model/stats')
def api_model_stats():
    return jsonify({"status": "success", "data": predictor.get_model_stats()})

@app.route('/api/radar/<city>')
def api_radar(city):
    city_info = get_city_by_name(city)
    if not city_info:
        return jsonify({"status": "error", "message": "City not found"}), 404
    data = data_sources.get_radar_simulation(city_info['lat'], city_info['lng'])
    return jsonify({"status": "success", "data": data})

@app.route('/api/satellite/<city>')
def api_satellite(city):
    city_info = get_city_by_name(city)
    if not city_info:
        return jsonify({"status": "error", "message": "City not found"}), 404
    data = data_sources.get_satellite_simulation(city_info['lat'], city_info['lng'])
    return jsonify({"status": "success", "data": data})

@app.route('/api/data-sources')
def api_data_sources_info():
    info = {
        "sources": [
            {"name": "IMD CSV", "type": "historical", "status": "active" if os.path.exists(IMD_CSV_PATH) else "missing"},
            {"name": "IMD GRD", "type": "binary grid", "status": "active" if os.path.exists(os.path.join(DATA_DIR, '07092026.grd')) else "missing"},
            {"name": "OpenWeatherMap API", "type": "live", "status": "active" if 'OPENWEATHERMAP_API_KEY' in os.environ else "simulated"}
        ]
    }
    return jsonify({"status": "success", "data": info})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
