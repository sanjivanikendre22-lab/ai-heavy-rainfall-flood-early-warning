import os
import json
import uuid
from datetime import datetime, timedelta

class AlertManager:
    def __init__(self):
        self.alerts = []
        
    def generate_alerts(self, predictions):
        """
        Generates alerts based on rainfall predictions and inundation risk.
        predictions: list of dicts with city_name, state_name, predicted_rainfall_mm, inundation_risk_level
        """
        new_alerts = []
        now = datetime.now()
        
        for pred in predictions:
            rain = pred.get('predicted_rainfall_mm', 0)
            risk = pred.get('inundation_risk_level', 'low')
            
            # Determine level based on IMD guidelines
            level = "GREEN"
            if rain >= 115 or risk in ['severe', 'extreme']:
                level = "RED"
            elif rain >= 64 or risk == 'high':
                level = "ORANGE"
            elif rain >= 15 or risk == 'moderate':
                level = "YELLOW"
                
            if level != "GREEN":
                alert = {
                    "id": str(uuid.uuid4()),
                    "city": pred.get('city_name'),
                    "state": pred.get('state_name'),
                    "level": level,
                    "message": self._generate_message(level, rain, risk, pred.get('city_name')),
                    "issued_at": now.isoformat(),
                    "valid_until": (now + timedelta(days=1)).isoformat(),
                    "rainfall_predicted": rain,
                    "inundation_risk": risk,
                    "affected_population": pred.get('population', 0)
                }
                new_alerts.append(alert)
                
        # Append new alerts
        self.alerts.extend(new_alerts)
        return new_alerts

    def _generate_message(self, level, rain, risk, city):
        if level == "RED":
            return f"CRITICAL ALERT: Extreme rainfall ({rain:.1f}mm) expected in {city}. High inundation risk ({risk}). Take immediate action."
        elif level == "ORANGE":
            return f"WARNING: Heavy rainfall ({rain:.1f}mm) expected in {city}. Moderate to high inundation risk ({risk}). Be prepared."
        elif level == "YELLOW":
            return f"WATCH: Moderate rainfall ({rain:.1f}mm) expected in {city}. Low to moderate inundation risk ({risk}). Stay updated."
        return "Normal conditions."

    def get_active_alerts(self):
        now = datetime.now().isoformat()
        return [a for a in self.alerts if a['valid_until'] > now]

    def get_alert_history(self):
        return self.alerts

    def get_alerts_by_level(self, level):
        return [a for a in self.get_active_alerts() if a['level'].upper() == level.upper()]
