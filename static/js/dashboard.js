// Global state
let currentCity = null;
let allCities = [];
let activeAlerts = [];
let charts = {};

// API Base URL (relative as requested)
const API_BASE = '/api';

document.addEventListener('DOMContentLoaded', async () => {
    // 1. Initialize Map
    window.mapManager.initMap('map');
    window.mapManager.onCitySelect = selectCity;

    // 2. Initialize Charts
    initCharts();

    // 3. Setup UI Listeners
    setupListeners();

    // 4. Initial Data Load
    await loadInitialData();
    
    // 5. Start Auto-refresh
    startIntervals();
});

function setupListeners() {
    const searchInput = document.getElementById('city-search');
    const cityList = document.getElementById('city-list');

    searchInput.addEventListener('input', (e) => {
        const term = e.target.value.toLowerCase();
        cityList.innerHTML = '';
        
        if (!term) return;

        const filtered = allCities.filter(c => c.name.toLowerCase().includes(term));
        filtered.forEach(city => {
            const div = document.createElement('div');
            div.className = 'city-list-item';
            div.textContent = `${city.name}, ${city.state}`;
            div.onclick = () => {
                searchInput.value = '';
                cityList.innerHTML = '';
                selectCity(city.name);
            };
            cityList.appendChild(div);
        });
    });

    document.getElementById('refresh-alerts').addEventListener('click', async () => {
        await fetch(`${API_BASE}/alerts/generate`); // Trigger generation
        loadAlerts();
    });
}

async function loadInitialData() {
    try {
        // Fetch all cities/stations
        const res = await fetch(`${API_BASE}/stations`);
        const json = await res.json();
        if (json.status === 'success') {
            allCities = json.data;
            document.getElementById('total-cities').textContent = allCities.length;
        }

        // Fetch alerts
        await loadAlerts();

        // Update map markers
        window.mapManager.updateCityMarkers(allCities, activeAlerts);
        window.mapManager.updateStationMarkers(allCities);
        
        // Heatmap needs some rainfall data, use stations for now
        window.mapManager.updateRainfallHeatmap(allCities);

        // Fetch Model Stats
        fetchModelStats();

        // Select default city (Mumbai)
        if (allCities.length > 0) {
            const defaultCity = allCities.find(c => c.name === 'Mumbai') || allCities[0];
            selectCity(defaultCity.name);
        }
    } catch (e) {
        console.error("Error loading initial data", e);
    }
}

async function loadAlerts() {
    try {
        const res = await fetch(`${API_BASE}/alerts`);
        const json = await res.json();
        if (json.status === 'success') {
            activeAlerts = json.data;
            document.getElementById('total-alerts').textContent = activeAlerts.length;
            renderAlertsList();
            updateAlertTicker();
            updateAlertChart();
        }
    } catch (e) {
        console.error("Error loading alerts", e);
    }
}

function renderAlertsList() {
    const list = document.getElementById('active-alerts-list');
    list.innerHTML = '';

    if (activeAlerts.length === 0) {
        list.innerHTML = '<p class="text-secondary text-center py-4">No active alerts.</p>';
        return;
    }

    activeAlerts.forEach(alert => {
        const div = document.createElement('div');
        div.className = `alert-card ${alert.level}`;
        div.innerHTML = `
            <div class="alert-header">
                <span>${alert.city}</span>
                <span>${formatDate(alert.timestamp)}</span>
            </div>
            <div>${alert.message}</div>
        `;
        list.appendChild(div);
    });
}

function updateAlertTicker() {
    const ticker = document.getElementById('ticker-content');
    if (activeAlerts.length === 0) {
        ticker.innerHTML = '✅ All monitoring stations reporting normal conditions. No heavy rainfall alerts active.';
        return;
    }

    let html = '';
    // Duplicate to make continuous scroll seamless
    const items = [...activeAlerts, ...activeAlerts];
    
    items.forEach(a => {
        const icon = a.level === 'RED' ? '🔴' : a.level === 'ORANGE' ? '🟠' : a.level === 'YELLOW' ? '🟡' : '🟢';
        html += `<span class="ticker-item ${a.level}">${icon} [${a.level}] ${a.city}: ${a.message}</span>`;
    });
    
    ticker.innerHTML = html;
}

async function fetchModelStats() {
    try {
        const res = await fetch(`${API_BASE}/model/stats`);
        const json = await res.json();
        if (json.status === 'success') {
            const acc = json.data.accuracy || 94.5;
            document.getElementById('confidence-text').textContent = `${acc}%`;
            document.getElementById('confidence-fill').style.strokeDasharray = `${acc}, 100`;
            document.getElementById('model-stats').textContent = `Accuracy: ${acc}% | Sources: NWP, Radar, IMD`;
        }
    } catch(e) {}
}

async function selectCity(cityName) {
    if (!cityName) return;
    currentCity = cityName;
    
    const cityData = allCities.find(c => c.name === cityName);
    if (cityData) {
        document.getElementById('selected-city-name').textContent = cityData.name;
        document.getElementById('selected-city-state').textContent = cityData.state || 'India';
        window.mapManager.highlightCity(cityName);
    }

    try {
        // Parallel fetching
        const [weatherRes, forecastRes, inundationRes] = await Promise.all([
            fetch(`${API_BASE}/weather/${cityName}`).catch(()=>null),
            fetch(`${API_BASE}/forecast/${cityName}`).catch(()=>null),
            fetch(`${API_BASE}/inundation/${cityName}`).catch(()=>null)
        ]);

        if (weatherRes) {
            const wJson = await weatherRes.json();
            if (wJson.status === 'success') {
                const w = wJson.data;
                document.getElementById('current-temp').textContent = `${w.temperature}°C`;
                document.getElementById('current-humidity').textContent = `${w.humidity}%`;
                document.getElementById('current-wind').textContent = `${w.wind_speed} km/h`;
                document.getElementById('current-rain').textContent = `${w.rainfall_1h} mm`;
                
                // Update Max Rain stat roughly
                const curMax = parseFloat(document.getElementById('max-rain').textContent) || 0;
                if (w.rainfall_1h > curMax) {
                    document.getElementById('max-rain').textContent = `${w.rainfall_1h} mm`;
                }
            }
        }

        if (forecastRes) {
            const fJson = await forecastRes.json();
            if (fJson.status === 'success') {
                updateRainfallChart(fJson.data);
            }
        }

        if (inundationRes) {
            const iJson = await inundationRes.json();
            if (iJson.status === 'success') {
                updateInundationPanel(iJson.data);
                window.mapManager.updateInundationZones(iJson.data);
            }
        } else {
            window.mapManager.clearInundationZones();
        }

    } catch (e) {
        console.error("Error fetching city data", e);
    }
}

function updateInundationPanel(data) {
    const badge = document.getElementById('risk-badge');
    badge.textContent = data.flood_risk_level;
    badge.className = `risk-level-badge ${data.flood_risk_level}`;

    document.getElementById('est-depth').textContent = `${data.estimated_water_depth_cm}cm`;
    
    // Animate depth bar (max assumed 500cm)
    const pct = Math.min(100, (data.estimated_water_depth_cm / 500) * 100);
    const bar = document.getElementById('depth-bar');
    bar.style.width = `${pct}%`;
    
    if (data.flood_risk_level === 'severe' || data.flood_risk_level === 'high') {
        bar.style.background = 'linear-gradient(90deg, #f97316, #ef4444)';
    } else {
        bar.style.background = 'linear-gradient(90deg, #4facfe, #00f2fe)';
    }

    document.getElementById('affected-area').textContent = `${data.affected_area_percentage}%`;

    const list = document.getElementById('risk-zones-list');
    list.innerHTML = '';
    if (data.risk_zones && data.risk_zones.length > 0) {
        data.risk_zones.forEach(z => {
            list.innerHTML += `<div class="zone-item"><span>Zone ${z.zone_id}</span> <span>Depth: ${z.estimated_depth_cm}cm</span></div>`;
        });
    } else {
        list.innerHTML = '<div class="text-secondary">No specific risk zones identified.</div>';
    }

    const advisory = document.getElementById('evacuation-advisory');
    if (data.risk_level === 'SEVERE') {
        advisory.innerHTML = '⚠️ <strong>EVACUATION ADVISED:</strong> Move to higher ground immediately. Follow local authority guidelines.';
        advisory.style.borderLeftColor = '#ef4444';
        advisory.style.color = '#ef4444';
    } else if (data.risk_level === 'HIGH') {
        advisory.innerHTML = '⚠️ <strong>WARNING:</strong> Prepare for possible evacuation. Secure belongings.';
        advisory.style.borderLeftColor = '#f97316';
        advisory.style.color = '#f97316';
    } else {
        advisory.innerHTML = '✅ Normal conditions. No evacuation needed.';
        advisory.style.borderLeftColor = '#10b981';
        advisory.style.color = '#e5e7eb';
    }
}

function initCharts() {
    Chart.defaults.color = '#9ca3af';
    Chart.defaults.font.family = 'Inter';

    // 1. Rainfall Trend
    const ctx1 = document.getElementById('rainfallTrendChart').getContext('2d');
    charts.trend = new Chart(ctx1, {
        type: 'line',
        data: {
            labels: ['Day 1', 'Day 2', 'Day 3', 'Day 4', 'Day 5'],
            datasets: [
                { label: 'Predicted (mm)', data: [0,0,0,0,0], borderColor: '#4facfe', tension: 0.4 },
                { label: 'Normal (mm)', data: [10,10,10,10,10], borderColor: '#6b7280', borderDash: [5,5] }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: { grid: { color: 'rgba(255,255,255,0.05)' } },
                x: { grid: { display: false } }
            },
            plugins: { legend: { position: 'top', labels: { boxWidth: 10 } } }
        }
    });

    // 2. District Comparison
    const ctx2 = document.getElementById('districtComparisonChart').getContext('2d');
    charts.district = new Chart(ctx2, {
        type: 'bar',
        data: {
            labels: ['Dist A', 'Dist B', 'Dist C', 'Dist D', 'Dist E'],
            datasets: [{
                label: 'Departure %',
                data: [45, 30, 15, -10, -25],
                backgroundColor: (ctx) => ctx.raw > 0 ? '#10b981' : '#ef4444'
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { grid: { color: 'rgba(255,255,255,0.05)' } },
                y: { grid: { display: false } }
            },
            plugins: { legend: { display: false } }
        }
    });

    // 3. Alert Distribution
    const ctx3 = document.getElementById('alertDistributionChart').getContext('2d');
    charts.alerts = new Chart(ctx3, {
        type: 'doughnut',
        data: {
            labels: ['RED', 'ORANGE', 'YELLOW', 'GREEN'],
            datasets: [{
                data: [1, 2, 5, 20],
                backgroundColor: ['#ef4444', '#f97316', '#f59e0b', '#10b981'],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '70%',
            plugins: {
                legend: { position: 'right', labels: { boxWidth: 12 } }
            }
        }
    });
}

function updateRainfallChart(forecastData) {
    if (!charts.trend || !forecastData) return;
    
    // Assuming forecastData is array of {date, predicted_mm, normal_mm}
    const labels = forecastData.map(d => d.date.substring(5)); // MM-DD
    const pred = forecastData.map(d => d.predicted_mm);
    const norm = forecastData.map(d => d.normal_mm || 10);

    charts.trend.data.labels = labels;
    charts.trend.data.datasets[0].data = pred;
    charts.trend.data.datasets[1].data = norm;
    charts.trend.update();
}

function updateAlertChart() {
    if (!charts.alerts) return;
    
    let counts = { RED: 0, ORANGE: 0, YELLOW: 0, GREEN: 0 };
    activeAlerts.forEach(a => {
        if(counts[a.level] !== undefined) counts[a.level]++;
    });
    
    // Make sure green has some base if no alerts
    if (activeAlerts.length === 0) counts.GREEN = allCities.length || 10;

    charts.alerts.data.datasets[0].data = [counts.RED, counts.ORANGE, counts.YELLOW, counts.GREEN];
    charts.alerts.update();
}

function startIntervals() {
    // Clock
    setInterval(() => {
        const now = new Date();
        document.getElementById('real-time-clock').textContent = now.toLocaleTimeString('en-US', { hour12: false });
        document.getElementById('current-date').textContent = now.toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'short', day: 'numeric' });
    }, 1000);

    // Data Refresh (30s)
    setInterval(async () => {
        await loadAlerts();
        if (currentCity) {
            selectCity(currentCity); // Refresh current city
        }
    }, 30000);
}

// Utilities
function formatDate(dateStr) {
    if (!dateStr) return '';
    try {
        const d = new Date(dateStr);
        return d.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
    } catch(e) {
        return dateStr;
    }
}
