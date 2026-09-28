import os
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import joblib
from datetime import datetime, timedelta
import random
import math

class RainfallPredictor:
    def __init__(self, data_path, model_path='rf_model.joblib'):
        self.data_path = data_path
        self.model_path = os.path.join(os.path.dirname(data_path), model_path)
        self.model = None
        self.accuracy = 0.0
        self.feature_importances = {}
        self.training_info = {}
        
        # Category Mappings
        self.cat_to_int = {'NR': 0, 'LD': 1, 'D': 2, 'N': 3, 'E': 4, 'LE': 5}
        self.int_to_cat = {v: k for k, v in self.cat_to_int.items()}
        
        self.features = [
            'month', 'day_of_year', 'Daily Normal', 
            'Weekly Departure Per', 'Cumulative Departure Per', 
            'Monthly Departure Per', 'is_monsoon_month'
        ]
        
        self.df = None
        self._load_and_train()

    def _load_and_train(self):
        if not os.path.exists(self.data_path):
            print(f"Dataset not found at {self.data_path}. Model will be untrained.")
            return

        try:
            print("Loading dataset for training...")
            self.df = pd.read_csv(self.data_path)
            
            # Clean column names: strip whitespace, newlines, and fix known typos
            self.df.columns = [col.replace('\r', '').replace('\n', '').strip() for col in self.df.columns]
            # Fix known typo in IMD data: "Departue" -> "Departure"
            self.df.columns = [col.replace('Departue', 'Departure') for col in self.df.columns]
            # Fix "Acutual" -> "Actual" typo
            self.df.columns = [col.replace('Acutual', 'Actual') for col in self.df.columns]
            
            print(f"Cleaned columns: {list(self.df.columns)}")
            
            # Prepare data
            # Convert Date to datetime
            self.df['Date_obj'] = pd.to_datetime(self.df['Date'], errors='coerce')
            self.df = self.df.dropna(subset=['Date_obj', 'Daily Category'])
            
            self.df['month'] = self.df['Date_obj'].dt.month
            self.df['day_of_year'] = self.df['Date_obj'].dt.dayofyear
            self.df['is_monsoon_month'] = self.df['month'].apply(lambda x: 1 if 6 <= x <= 9 else 0)
            
            # Ensure target is mapped correctly
            self.df['target'] = self.df['Daily Category'].map(self.cat_to_int)
            self.df = self.df.dropna(subset=['target'])
            
            # Convert feature columns to numeric, coercing errors
            for col in self.features:
                if col in self.df.columns:
                    self.df[col] = pd.to_numeric(self.df[col], errors='coerce')
                    if self.df[col].isnull().any():
                        self.df[col] = self.df[col].fillna(self.df[col].median())
                    
            X = self.df[self.features]
            y = self.df['target']
            
            # Train test split
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
            
            print("Training Random Forest Classifier...")
            self.model = RandomForestClassifier(n_estimators=50, max_depth=10, random_state=42, n_jobs=-1)
            self.model.fit(X_train, y_train)
            
            preds = self.model.predict(X_test)
            self.accuracy = accuracy_score(y_test, preds)
            
            # Store stats
            importances = self.model.feature_importances_
            self.feature_importances = {f: float(i) for f, i in zip(self.features, importances)}
            self.training_info = {
                "trained_on": datetime.now().isoformat(),
                "samples_used": len(X),
                "model_type": "RandomForestClassifier"
            }
            
            # Save model
            joblib.dump(self.model, self.model_path)
            print(f"Model trained successfully. Accuracy: {self.accuracy:.4f}")
            
        except Exception as e:
            print(f"Error training model: {e}")

    def predict_rainfall(self, city_name, state_name, days_ahead=5):
        if not self.model:
            return []
            
        # Get baseline features for the city/state from df
        baseline = None
        if self.df is not None:
            # Try to match district roughly by city name or state
            subset = self.df[self.df['State'].str.contains(state_name, case=False, na=False)]
            if not subset.empty:
                dist_subset = subset[subset['District'].str.contains(city_name, case=False, na=False)]
                if not dist_subset.empty:
                    baseline = dist_subset.iloc[-1]
                else:
                    baseline = subset.iloc[-1]
                    
        predictions = []
        now = datetime.now()
        
        for i in range(days_ahead):
            target_date = now + timedelta(days=i)
            
            # Construct feature vector
            if baseline is not None:
                features = [
                    target_date.month,
                    target_date.timetuple().tm_yday,
                    baseline.get('Daily Normal', random.uniform(5, 20)),
                    baseline.get('Weekly Departure Per', random.uniform(-20, 20)),
                    baseline.get('Cumulative Departure Per', random.uniform(-10, 10)),
                    baseline.get('Monthly Departure Per', random.uniform(-15, 15)),
                    1 if 6 <= target_date.month <= 9 else 0
                ]
            else:
                features = [
                    target_date.month,
                    target_date.timetuple().tm_yday,
                    random.uniform(5, 15),
                    random.uniform(-10, 10),
                    random.uniform(-5, 5),
                    random.uniform(-10, 10),
                    1 if 6 <= target_date.month <= 9 else 0
                ]
                
            pred_class = self.model.predict([features])[0]
            probs = self.model.predict_proba([features])[0]
            confidence = float(max(probs))
            
            cat_str = self.int_to_cat.get(pred_class, 'N')
            
            # Estimate MM based on category
            rain_mm = 0
            if cat_str == 'NR': rain_mm = 0
            elif cat_str == 'LD': rain_mm = random.uniform(0.1, 2.4)
            elif cat_str == 'D': rain_mm = random.uniform(2.5, 7.5)
            elif cat_str == 'N': rain_mm = random.uniform(7.6, 35.5)
            elif cat_str == 'E': rain_mm = random.uniform(35.6, 64.4)
            elif cat_str == 'LE': rain_mm = random.uniform(64.5, 200.0)
            
            predictions.append({
                "date": target_date.strftime("%Y-%m-%d"),
                "rainfall_mm": round(rain_mm, 2),
                "category": cat_str,
                "confidence_score": round(confidence, 3)
            })
            
        return predictions

    def predict_inundation(self, city_data, predicted_rainfall_mm):
        elev = city_data.get('elevation', 50)
        drainage = city_data.get('drainage_capacity_index', 0.5)
        flood_risk = city_data.get('flood_risk_rating', 5)
        
        # Rule-based calculation
        # Higher rainfall, lower elevation, lower drainage = higher risk
        risk_score = (predicted_rainfall_mm * 0.5) + (flood_risk * 10) - (elev * 0.1) - (drainage * 50)
        
        level = "low"
        depth_cm = 0
        area_pct = 0
        
        if risk_score > 100:
            level = "extreme"
            depth_cm = random.uniform(100, 300)
            area_pct = random.uniform(40, 80)
        elif risk_score > 70:
            level = "severe"
            depth_cm = random.uniform(50, 100)
            area_pct = random.uniform(20, 40)
        elif risk_score > 40:
            level = "high"
            depth_cm = random.uniform(20, 50)
            area_pct = random.uniform(10, 20)
        elif risk_score > 20:
            level = "moderate"
            depth_cm = random.uniform(5, 20)
            area_pct = random.uniform(2, 10)
        else:
            depth_cm = random.uniform(0, 5)
            area_pct = random.uniform(0, 2)
            
        # Generate zones based on city lat/lng
        lat = city_data.get('lat', 20.0)
        lng = city_data.get('lng', 77.0)
        
        zones = []
        if level in ['moderate', 'high', 'severe', 'extreme']:
            num_zones = random.randint(1, 4)
            for i in range(num_zones):
                # Offset lat/lng slightly to simulate low-lying areas
                z_lat = lat + random.uniform(-0.05, 0.05)
                z_lng = lng + random.uniform(-0.05, 0.05)
                zones.append({
                    "zone_id": f"Z-{i+1}",
                    "lat": round(z_lat, 5),
                    "lng": round(z_lng, 5),
                    "radius_km": round(random.uniform(1.0, 5.0), 2),
                    "estimated_depth_cm": round(depth_cm * random.uniform(0.8, 1.2), 1)
                })
                
        return {
            "flood_risk_level": level,
            "estimated_water_depth_cm": round(depth_cm, 1),
            "affected_area_percentage": round(area_pct, 1),
            "risk_score": round(risk_score, 2),
            "risk_zones": zones
        }

    def get_district_data(self, state, district):
        if self.df is None:
            return []
            
        mask = (self.df['State'].str.lower() == state.lower()) & (self.df['District'].str.lower() == district.lower())
        records = self.df[mask].to_dict(orient='records')
        
        # Clean NaNs for JSON serialization
        for r in records:
            for k, v in r.items():
                if isinstance(v, float) and math.isnan(v):
                    r[k] = None
        return records

    def get_model_stats(self):
        return {
            "accuracy": self.accuracy,
            "feature_importances": self.feature_importances,
            "training_info": self.training_info
        }
