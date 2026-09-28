class MapManager {
    constructor() {
        this.map = null;
        this.layers = {
            heatmap: null,
            inundation: null,
            cities: null,
            stations: null
        };
        this.onCitySelect = null; // Callback for dashboard
        this.colors = {
            RED: '#ef4444',
            ORANGE: '#f97316',
            YELLOW: '#f59e0b',
            GREEN: '#10b981'
        };
    }

    initMap(containerId) {
        // Center on India
        this.map = L.map(containerId, {
            zoomControl: false
        }).setView([22.5, 82.0], 5);

        // Add Zoom Control at bottom right
        L.control.zoom({ position: 'bottomright' }).addTo(this.map);

        // Dark tile layer (Esri World Dark Gray)
        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
            attribution: '&copy; Esri, HERE, Garmin, &copy; OpenStreetMap contributors, and the GIS User Community',
            maxZoom: 16
        }).addTo(this.map);

        // Initialize Layer Groups
        this.layers.inundation = L.layerGroup().addTo(this.map);
        this.layers.heatmap = L.layerGroup().addTo(this.map);
        this.layers.cities = L.layerGroup().addTo(this.map);
        this.layers.stations = L.layerGroup(); // Not added by default

        // Add Layer Control
        const overlays = {
            "Rainfall Heatmap": this.layers.heatmap,
            "Inundation Zones": this.layers.inundation,
            "Cities": this.layers.cities,
            "Weather Stations": this.layers.stations
        };
        L.control.layers(null, overlays, { position: 'topright' }).addTo(this.map);

        this.addLegend();
    }

    updateRainfallHeatmap(stationsData) {
        this.layers.heatmap.clearLayers();
        
        if (!stationsData || stationsData.length === 0 || !L.heatLayer) return;

        // Extract [lat, lng, intensity]
        const heatData = stationsData.map(st => {
            // Randomize slightly for demo or use actual lat/lng
            const lat = st.lat || 20 + Math.random() * 10;
            const lng = st.lng || 75 + Math.random() * 10;
            const intensity = st.rain_today ? st.rain_today / 200 : Math.random(); // Normalize
            return [lat, lng, intensity];
        });

        const heatLayer = L.heatLayer(heatData, {
            radius: 25,
            blur: 15,
            maxZoom: 10,
            gradient: {
                0.2: 'green',
                0.4: 'yellow',
                0.6: 'orange',
                0.8: 'red',
                1.0: 'darkred'
            }
        });

        this.layers.heatmap.addLayer(heatLayer);
    }

    updateInundationZones(inundationData) {
        this.layers.inundation.clearLayers();
        
        if (!inundationData || !inundationData.risk_zones) return;

        inundationData.risk_zones.forEach(zone => {
            // Map depth to opacity and color
            const opacity = Math.min(0.8, 0.3 + (zone.estimated_depth_cm / 500));
            let color = '#3b82f6'; // blue-500
            if (zone.estimated_depth_cm > 200) color = '#1d4ed8'; // blue-700
            if (zone.estimated_depth_cm > 400) color = '#1e3a8a'; // blue-900

            const circle = L.circle([zone.lat, zone.lng], {
                color: color,
                fillColor: color,
                fillOpacity: opacity,
                radius: zone.radius_km * 1000,
                weight: 1
            });

            circle.bindPopup(`
                <div style="text-align: center;">
                    <strong>Inundation Zone</strong><br>
                    Depth: ${zone.estimated_depth_cm}cm<br>
                    Radius: ${zone.radius_km}km
                </div>
            `);

            this.layers.inundation.addLayer(circle);
        });
    }

    updateCityMarkers(citiesData, alertsData = []) {
        this.layers.cities.clearLayers();
        
        if (!citiesData) return;

        // Map alerts for quick lookup
        const alertMap = {};
        alertsData.forEach(a => { alertMap[a.city] = a.level; });

        citiesData.forEach(city => {
            const level = alertMap[city.name] || 'GREEN';
            const color = this.colors[level];
            
            // Marker styling based on alert level
            const markerOptions = {
                radius: level === 'RED' ? 10 : 6,
                fillColor: color,
                color: '#fff',
                weight: 1.5,
                opacity: 1,
                fillOpacity: 0.8
            };

            // Use dummy coords if API doesn't provide them
            const lat = city.lat || 20 + (Math.random() * 10 - 5);
            const lng = city.lng || 80 + (Math.random() * 10 - 5);

            const marker = L.circleMarker([lat, lng], markerOptions);
            
            // Popup
            const popupContent = `
                <div>
                    <h4>${city.name}</h4>
                    <p>Alert Level: <strong style="color:${color}">${level}</strong></p>
                    <button onclick="window.mapManager.triggerCitySelect('${city.name}')" 
                            style="margin-top:5px; padding:3px 8px; background:#4facfe; border:none; color:white; border-radius:3px; cursor:pointer;">
                        View Details
                    </button>
                </div>
            `;
            
            marker.bindPopup(popupContent);
            
            // Store city name in marker for highlighting
            marker.cityName = city.name;

            this.layers.cities.addLayer(marker);
        });
    }

    updateStationMarkers(stationsData) {
        this.layers.stations.clearLayers();
        if (!stationsData) return;

        stationsData.forEach(st => {
            const lat = st.lat || 20 + (Math.random() * 10 - 5);
            const lng = st.lng || 80 + (Math.random() * 10 - 5);
            
            const marker = L.circleMarker([lat, lng], {
                radius: 3,
                fillColor: '#9ca3af',
                color: '#fff',
                weight: 1,
                fillOpacity: 0.8
            });
            
            marker.bindPopup(`<p>Station: ${st.name}</p>`);
            this.layers.stations.addLayer(marker);
        });
    }

    highlightCity(cityName) {
        let targetMarker = null;
        
        this.layers.cities.eachLayer(marker => {
            if (marker.cityName === cityName) {
                targetMarker = marker;
            }
        });

        if (targetMarker) {
            const latLng = targetMarker.getLatLng();
            this.map.flyTo(latLng, 9, { duration: 1.5 });
            targetMarker.openPopup();
        }
    }

    clearInundationZones() {
        this.layers.inundation.clearLayers();
    }

    addLegend() {
        const legend = L.control({ position: 'bottomleft' });
        
        legend.onAdd = function (map) {
            const div = L.DomUtil.create('div', 'info legend map-legend');
            div.innerHTML = `
                <div style="font-weight:bold; margin-bottom:8px;">Map Legend</div>
                <div class="legend-item"><div class="legend-color" style="background:#ef4444"></div> RED Alert</div>
                <div class="legend-item"><div class="legend-color" style="background:#f97316"></div> ORANGE Alert</div>
                <div class="legend-item"><div class="legend-color" style="background:#f59e0b"></div> YELLOW Alert</div>
                <div class="legend-item"><div class="legend-color" style="background:#10b981"></div> GREEN Alert</div>
                <hr style="border-color:rgba(255,255,255,0.1); margin:8px 0;">
                <div class="legend-item"><div class="legend-color" style="background:linear-gradient(to right, lightblue, darkblue)"></div> Inundation Depth</div>
            `;
            return div;
        };
        
        legend.addTo(this.map);
    }

    triggerCitySelect(cityName) {
        if (this.onCitySelect) {
            this.onCitySelect(cityName);
        }
    }
}

// Make accessible globally for popup buttons
window.mapManager = new MapManager();
