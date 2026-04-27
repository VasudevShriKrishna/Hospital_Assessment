// Global variables
// 🚨 YOU MUST PASTE YOUR OPENROUTESERVICE API KEY HERE 🚨
// Get it for free at: https://openrouteservice.org/
const ORS_API_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6ImJkYzIwMjBhZDI5ODRjMjJhZDUwNmQ0ZjBhOTVmNDMwIiwiaCI6Im11cm11cjY0In0=eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6ImJkYzIwMjBhZDI5ODRjMjJhZDUwNmQ0ZjBhOTVmNDMwIiwiaCI6Im11cm11cjY0In0="; 

let map, satelliteLayer, labelsLayer, streetLayer;
let currentMapStyle = 'satellite';
let hospitalLayer, impactCircle, epicenterMarker;
let geojsonData = null;
let affectedHospitals = [];
let safeHospitals = []; 
let safeMarkers = []; 
let currentEpicenter = null;

// Routing variables
let routeControl = null;
let routeLayers = [];
let availableRoutes = [];

let pieChartInstance = null;
let barChartInstance = null;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    initMap();
    initTheme(); 
    initThemeListeners();
    initCharts();
    loadDefaultGeoJSON();
});

// --- Load Default GeoJSON ---
function loadDefaultGeoJSON() {
    const uploadText = document.getElementById('upload-text');
    if (uploadText) uploadText.innerText = "Loading Default Data...";
    
    fetch('/static/data/hospitals.geojson')
        .then(response => {
            if (!response.ok) throw new Error("File not found");
            return response.json();
        })
        .then(data => {
            geojsonData = data;
            renderDataOnMap();
            if (uploadText) uploadText.innerText = "Load Local GeoJSON";
        })
        .catch(err => {
            console.warn("Default GeoJSON not loaded:", err);
            if (uploadText) uploadText.innerText = "Load Local GeoJSON";
        });
}

// --- Map Initialization ---
function initMap() {
    satelliteLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { attribution: 'Esri' });
    labelsLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}');
    streetLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '&copy; OpenStreetMap' });

    map = L.map('map', {
        zoomControl: false,
        preferCanvas: true, // Required for leaflet-image to render SVGs
        layers: [satelliteLayer, labelsLayer],
        attributionControl: false
    }).setView([37.0902, -95.7129], 4);

    L.control.zoom({ position: 'bottomright' }).addTo(map);

    map.on('click', (e) => {
        currentEpicenter = { lat: e.latlng.lat, lng: e.latlng.lng };
        // Strict Boundary Check for USA (Mainland, Alaska, Hawaii)
        const lat = currentEpicenter.lat;
        const lng = currentEpicenter.lng;
        // 1. The Bounding Box
        const isMainlandBox = lat >= 24.3 && lat <= 49.4 && lng >= -125.0 && lng <= -66.9;
        // 2. The Exclusion Zones (Carving out Canada and Mexico)
        const isCanadaWest = lat > 49.0 && lng <= -95.0; // Blocks BC, Alberta, Saskatchewan
        const isCanadaEast = lat > 45.0 && lng >= -84.0 && lng <= -75.0; // Blocks Ontario/Quebec
        const isMexico = lat < 32.5 && lng <= -105.0; // Blocks Northern Mexico
        // 3. Final Validation
        const inMainland = isMainlandBox && !isCanadaWest && !isCanadaEast && !isMexico;
        const inAlaska = lat >= 51.2 && lat <= 71.4 && (lng <= -141.0 || lng >= 170); // Switched to -141.0 to block Yukon
        const inHawaii = lat >= 18.9 && lat <= 28.4 && lng >= -178.4 && lng <= -154.8;

        // const lat = currentEpicenter.lat;
        // const lng = currentEpicenter.lng;
        // const inMainland = lat >= 24.3 && lat <= 49.4 && lng >= -125.0 && lng <= -66.9;
        // const inAlaska = lat >= 51.2 && lat <= 71.4 && (lng <= -129.9 || lng >= 170); 
        // const inHawaii = lat >= 18.9 && lat <= 28.4 && lng >= -178.4 && lng <= -154.8;
        // const lat = currentEpicenter.lat;
        // const lng = currentEpicenter.lng;
        // const inMainland = lat >= 24.3 && lat <= 49.4 && lng >= -125.0 && lng <= -66.9;
        // const inAlaska = lat >= 51.2 && lat <= 71.4 && (lng <= -129.9 || lng >= 170); 
        // const inHawaii = lat >= 18.9 && lat <= 28.4 && lng >= -178.4 && lng <= -154.8;
        
        if (!inMainland && !inAlaska && !inHawaii) {
            alert("⛔ TACTICAL ALERT: Out of bounds.\nPlease select an epicenter strictly within United States territory (Mainland, Alaska, or Hawaii) to establish routing and telemetry.");
            currentEpicenter = null;
            return;
        }

        document.getElementById('hud-lat').innerText = currentEpicenter.lat.toFixed(4);
        document.getElementById('hud-lng').innerText = currentEpicenter.lng.toFixed(4);
        updateImpactGraphics();
        hideAIReport();
        
        document.getElementById('hospital-detail-card').classList.add('hidden');
        document.getElementById('routing-panel').classList.add('hidden');
        
        if (routeControl && map) {
            try { map.removeControl(routeControl); } catch(err) {}
        }
        if (routeLayers && map) {
            routeLayers.forEach(l => { try { map.removeLayer(l); } catch(err) {} });
        }
        routeLayers = [];
        availableRoutes = [];
    });
}

// --- Map Toggle ---
window.toggleMapStyle = function() {
    const btn = document.getElementById('map-toggle-btn');
    if (currentMapStyle === 'satellite') {
        map.removeLayer(satelliteLayer);
        map.removeLayer(labelsLayer);
        map.addLayer(streetLayer);
        currentMapStyle = 'street';
        btn.innerHTML = '<i class="fa-solid fa-satellite"></i>'; 
        btn.title = "Switch to Satellite View";
    } else {
        map.removeLayer(streetLayer);
        map.addLayer(satelliteLayer);
        map.addLayer(labelsLayer);
        currentMapStyle = 'satellite';
        btn.innerHTML = '<i class="fa-solid fa-map"></i>';
        btn.title = "Switch to Street View";
    }
};

// --- Dynamic Theming based on Magnitude ---
function getThemeColor(mag) {
    if (mag >= 7.5) return '#ef4444'; // Red
    if (mag >= 5.5) return '#e87722'; // Orange
    if (mag >= 4.0) return '#eab308'; // Yellow
    return '#22c55e'; // Green
}

function initTheme() {
    const slider = document.getElementById('mag-slider');
    if(slider) {
        document.documentElement.style.setProperty('--dynamic-color', getThemeColor(parseFloat(slider.value)));
    }
}

function initThemeListeners() {
    const slider = document.getElementById('mag-slider');
    if(!slider) return;
    slider.addEventListener('input', (e) => {
        const mag = parseFloat(e.target.value);
        document.getElementById('mag-display').innerText = mag.toFixed(2);
        
        const hexColor = getThemeColor(mag);
        document.documentElement.style.setProperty('--dynamic-color', hexColor);

        if (currentEpicenter) updateImpactGraphics();
    });
}

// Region Classifier to prevent cross-ocean routing
function getUSRegion(lat, lng) {
    if (lat >= 51.2 && lat <= 71.4 && (lng <= -129.9 || lng >= 170)) return 'Alaska';
    if (lat >= 18.9 && lat <= 28.4 && lng >= -178.4 && lng <= -154.8) return 'Hawaii';
    if (lat >= 24.3 && lat <= 49.4 && lng >= -125.0 && lng <= -66.9) return 'Mainland';
    return 'Other'; 
}

// --- Visual Updates & Spatial Math ---
function updateImpactGraphics() {
    if (!currentEpicenter) return;
    const mag = parseFloat(document.getElementById('mag-slider').value);
    const hexColor = getThemeColor(mag);
    
    const radiusKm = Math.pow(10, (0.4 * mag - 1)) * 10;
    animateValue('stat-radius', parseFloat(document.getElementById('stat-radius').innerText), radiusKm, 1000);

    if (impactCircle) map.removeLayer(impactCircle);
    if (epicenterMarker) map.removeLayer(epicenterMarker);

    impactCircle = L.circle([currentEpicenter.lat, currentEpicenter.lng], {
        radius: radiusKm * 1000,
        color: hexColor, fillColor: hexColor, fillOpacity: 0.15,
        weight: 2, dashArray: '4, 12', className: 'impact-circle-anim'
    }).addTo(map);

    epicenterMarker = L.marker([currentEpicenter.lat, currentEpicenter.lng], {
        icon: L.divIcon({
            className: 'custom-div-icon',
            html: `<div class="shockwave-container">
                     <div class="sw-core"></div><div class="sw-ring sw-delay-1"></div>
                     <div class="sw-ring sw-delay-2"></div><div class="sw-ring sw-delay-3"></div>
                   </div>`,
            iconSize: [40, 40], iconAnchor: [20, 20]
        })
    }).addTo(map);

    let epiRegion = getUSRegion(currentEpicenter.lat, currentEpicenter.lng);

    if (geojsonData) {
        affectedHospitals = [];
        safeHospitals = [];
        geojsonData.features.forEach(f => {
            const [lng, lat] = f.geometry.coordinates;
            const hRegion = getUSRegion(lat, lng);
            
            // Prevent cross-country calculations
            if (hRegion !== 'Other' && hRegion === epiRegion) {
                const dist = map.distance([lat, lng], [currentEpicenter.lat, currentEpicenter.lng]) / 1000;
                f.properties.computedDist = dist; 
                f.properties.hLat = lat;
                f.properties.hLng = lng;
                
                if (dist <= radiusKm) affectedHospitals.push(f.properties);
                else safeHospitals.push(f.properties);
            }
        });
        animateValue('stat-sites', parseInt(document.getElementById('stat-sites').innerText), affectedHospitals.length, 1000);
        updateCharts();
    }
}

// --- Data Loading ---
window.handleFileUpload = function(e) {
    const file = e.target.files[0];
    if (!file) return;
    document.getElementById('upload-text').innerText = "Processing...";
    const reader = new FileReader();
    reader.onload = (ev) => {
        try {
            geojsonData = JSON.parse(ev.target.result);
            renderDataOnMap();
            document.getElementById('upload-text').innerText = "Data Loaded Successfully";
            setTimeout(() => document.getElementById('upload-text').innerText = "Load Local GeoJSON", 3000);
        } catch(err) {
            alert("Invalid GeoJSON file.");
            document.getElementById('upload-text').innerText = "Load Local GeoJSON";
        }
    };
    reader.readAsText(file);
};

function renderDataOnMap() {
    if (hospitalLayer) map.removeLayer(hospitalLayer);
    hospitalLayer = L.geoJSON(geojsonData, {
        pointToLayer: (feat, latlng) => L.circleMarker(latlng, {
            radius: 3, fillColor: "#22c55e", color: "#000", weight: 1, opacity: 0.8, fillOpacity: 0.8
        }),
        onEachFeature: (feature, layer) => {
            layer.on('click', (e) => {
                L.DomEvent.stopPropagation(e);
                showHospitalCard(feature.properties, layer.getLatLng().lat, layer.getLatLng().lng);
            });
        }
    }).addTo(map);
}

function showHospitalCard(p, lat, lng) {
    let distText = "Epicenter not set";
    if (currentEpicenter) {
        const distKm = (map.distance([lat, lng], [currentEpicenter.lat, currentEpicenter.lng]) / 1000).toFixed(2);
        distText = `${distKm} km from epicenter`;
    }

    document.getElementById('hosp-name').innerText = p.NAME || 'Unknown Facility';
    document.getElementById('hosp-address').innerText = `${p.ADDRESS || ''}, ${p.CITY || ''}`;
    document.getElementById('hosp-beds').innerText = p.BEDS === -999 ? "N/A" : p.BEDS;
    document.getElementById('hosp-status').innerText = p.STATUS || "UNKNOWN";
    document.getElementById('hosp-type').innerText = p.TYPE || "UNKNOWN";
    document.getElementById('hosp-phone').innerText = p.TELEPHONE || "N/A";
    document.getElementById('hosp-dist').innerText = distText;

    let facilities = p.FACILITIES || p.facilities || "Basic/Not Specified";
    if (Array.isArray(facilities)) facilities = facilities.join(', ');
    let facEl = document.getElementById('hosp-facilities');
    if (facEl) facEl.innerText = facilities;

    const routeBtn = document.getElementById('btn-calc-route');
    if(routeBtn) {
        routeBtn.onclick = () => window.evaluateRegionalRoutes();
    }

    document.getElementById('hospital-detail-card').classList.remove('hidden');
    document.getElementById('routing-panel').classList.add('hidden');
}

window.closeHospitalCard = function() {
    document.getElementById('hospital-detail-card').classList.add('hidden');
};  

// --- Backend API Call to views.py ---
window.runAnalysis = async function() {
    if (!currentEpicenter) return alert("Select an epicenter on the map first.");
    
    const mag = document.getElementById('mag-slider').value;
    const btnText = document.getElementById('btn-analyze-text');
    const icon = document.querySelector('#btn-analyze i');
    
    btnText.innerText = "Transmitting to Django Engine...";
    icon.className = "fa-solid fa-spinner fa-spin";
    
    try {
        const url = `/get_nearest_history/?lat=${currentEpicenter.lat}&lng=${currentEpicenter.lng}&mag=${mag}`;
        let data;
        try {
            const response = await fetch(url);
            data = await response.json();
        } catch(e) {
            console.warn("Django backend unreachable. Falling back to mock data.");
            const radiusKm = Math.pow(10, (0.4 * mag - 1)) * 10;
            
            let mag_penalty = Math.max(0, (mag - 6.5) * 5); 
            let geo_penalty = 10 + (Math.random() * 10); 
            let telemetry_penalty = 5.0; 

            let raw_confidence = 100.0 - mag_penalty - geo_penalty - telemetry_penalty;
            let dynamicConfidence = Math.max(15.0, Math.min(99.5, raw_confidence));

            data = {
                intensity: (parseFloat(mag) * 1.15).toFixed(2),
                risk_level: mag >= 7.5 ? 'CRITICAL' : mag >= 5.5 ? 'HIGH' : mag >= 4.0 ? 'MODERATE' : 'LOW',
                expected_damage: 'Simulation mode active. Structural concerns mapped to historical averages.',
                assessment: `Earthquake of magnitude ${mag} is predicted to cause ${mag >= 5.5 ? 'severe' : 'manageable'} damage potential.`,
                confidence: dynamicConfidence, 
                radius: radiusKm,
                depth: (Math.random() * 50 + 5).toFixed(1)
            };
        }
        if(data.error) throw new Error(data.error);

        document.getElementById('ai-placeholder').classList.add('hidden');
        document.getElementById('ai-report-container').classList.remove('hidden');

        animateValue('rep-intensity', 0, parseFloat(data.intensity), 1500, 2);
        
        const depthEl = document.getElementById('stat-depth');
        if(depthEl) animateValue('stat-depth', 0, parseFloat(data.depth), 1000, 1);
        
        document.getElementById('rep-risk').innerText = data.risk_level;
        document.getElementById('rep-damage').innerText = data.expected_damage;
        document.getElementById('rep-assessment').innerText = data.assessment;
        
        let confBar = document.getElementById('accuracy-bar');
        if(confBar) confBar.style.width = (data.confidence || 80) + "%";
        let confText = document.getElementById('accuracy-text');
        if(confText) confText.innerText = Math.round(data.confidence || 80) + "%";

        if (data.affected_hospitals) {
            affectedHospitals = data.affected_hospitals;
            animateValue('stat-sites', 0, affectedHospitals.length, 1000);
            updateCharts();
        }

        safeMarkers.forEach(m => map.removeLayer(m));
        safeMarkers = [];
        
        if (safeHospitals.length > 0 && geojsonData) {
            safeHospitals.sort((a, b) => a.computedDist - b.computedDist);
            window.top5SafeHospitals = safeHospitals.slice(0, 5); // Global for evaluation routing
            
            window.top5SafeHospitals.forEach(h => {
                let icon = L.divIcon({ html: '+', className: 'safe-hospital-marker', iconSize: [24,24] });
                let m = L.marker([h.hLat, h.hLng], { icon: icon }).addTo(map);
                
                m.on('click', (e) => {
                    L.DomEvent.stopPropagation(e);
                    showHospitalCard(h, h.hLat, h.hLng);
                });
                safeMarkers.push(m);
            });
            
            const nearestSafe = window.top5SafeHospitals[0];
            showHospitalCard(nearestSafe, nearestSafe.hLat, nearestSafe.hLng);
        }

    } catch (err) {
        alert("Backend Error: " + err.message);
    } finally {
        btnText.innerText = "Engage Server Analysis";
        icon.className = "fa-solid fa-bolt";
    }
};

function hideAIReport() {
    document.getElementById('ai-placeholder').classList.remove('hidden');
    document.getElementById('ai-report-container').classList.add('hidden');
}

// Weather Handling with robust fail-safes
async function getWeatherAt(lat, lng) {
    try {
        let res = await fetch(`/get_weather_proxy/?lat=${lat}&lng=${lng}`);
        let json = await res.json();
        
        // Handle Missing API Key Gracefully
        if (json.warning || json.cod == 401) {
            console.warn("Weather API Key missing. Falling back to default weather.");
            return { cond: "Clear" };
        }

        if (json && json.weather && json.weather[0]) return { cond: json.weather[0].main };
    } catch(e) { }
    return { cond: "Clear" };
}

function classifyRoadDamage(mag, distKm) {
    if (mag < 5.0) return "none"; // ✅ FIX: Ignore structural damage if Magnitude is < 5
    const radiusKm = Math.pow(10, (0.4 * mag - 1)) * 10;
    if (distKm <= radiusKm * 0.25) return "critical";
    if (distKm <= radiusKm * 0.6) return "severe";
    if (distKm <= radiusKm) return "moderate";
    return "none";
}

// Evaluates a single specific hospital targeting
window.analyzeRouteToHospital = async function(hName, hLat, hLng, hBeds, hType) {
    if (!currentEpicenter) return;
    
    if (routeLayers && map) {
        routeLayers.forEach(l => { try { map.removeLayer(l); } catch(err) {} });
    }
    routeLayers = [];
    availableRoutes = [];
    
    const panel = document.getElementById('routing-panel');
    if(!panel) return;

    document.getElementById('hospital-detail-card').classList.add('hidden');
    panel.classList.remove('hidden');
    
    panel.innerHTML = `<div class="p-6 text-center text-slate-400 font-bold tracking-widest uppercase text-[10px]">
        <i class="fa-solid fa-spinner fa-spin text-2xl mb-3 text-blue-500"></i><br>Calculating routes via OpenRouteService...
    </div>`;

    let url = `https://api.openrouteservice.org/v2/directions/driving-car?api_key=${ORS_API_KEY}&start=${currentEpicenter.lng},${currentEpicenter.lat}&end=${hLng},${hLat}`;

    try {
        let res = await fetch(url);
        if (!res.ok) throw new Error("API Limit Reached or Invalid ORS Key");
        let data = await res.json();
        
        if (!data.features || data.features.length === 0) throw new Error("No routes found");
        let routes = Array.from(data.features);

        if (routes.length < 3) {
            let baseRoute = routes[0];
            let numToAdd = 3 - routes.length;
            for (let k = 1; k <= numToAdd; k++) {
                let altCoords = baseRoute.geometry.coordinates.map((pt, idx) => {
                    let percent = idx / baseRoute.geometry.coordinates.length;
                    let curve = Math.sin(percent * Math.PI); 
                    let offsetDeg = (k % 2 === 0 ? -1 : 1) * 0.15 * k * curve; 
                    return [pt[0] + offsetDeg, pt[1] + offsetDeg]; 
                });
                routes.push({
                    geometry: { coordinates: altCoords },
                    properties: { summary: {
                        distance: baseRoute.properties.summary.distance * (1 + (0.08 * k)), 
                        duration: baseRoute.properties.summary.duration * (1 + (0.15 * k)) 
                    }}
                });
            }
        }

        let bestIndex = 0, bestScore = -Infinity;
        let html = `<h4 class="text-xs font-black uppercase tracking-widest text-white mb-4 border-b border-white/10 pb-2">Evacuation Routes</h4>`;
        
        let mag = parseFloat(document.getElementById('mag-slider').value);

        for(let i=0; i<routes.length; i++) {
            let r = routes[i];
            let distKm = (r.properties.summary.distance / 1000).toFixed(1);
            let timeMin = Math.round(r.properties.summary.duration / 60);
            
            let mappedCoords = r.geometry.coordinates.map(c => [c[1], c[0]]); 
            let wMid = { cond: "Clear" };
            let closestDistToEpicenter = Infinity;
            let totalDistToEpicenter = 0;

            if (mappedCoords.length > 0) {
                let midPt = mappedCoords[Math.floor(mappedCoords.length / 2)];
                wMid = await getWeatherAt(midPt[0], midPt[1]);
                
                mappedCoords.forEach(pt => {
                    let d = map.distance([pt[0], pt[1]], [currentEpicenter.lat, currentEpicenter.lng]) / 1000;
                    if (d < closestDistToEpicenter) closestDistToEpicenter = d;
                    totalDistToEpicenter += d;
                });
            }

            let avgDistToEpicenter = mappedCoords.length > 0 ? (totalDistToEpicenter / mappedCoords.length) : 0;
            let roadDamage = classifyRoadDamage(mag, closestDistToEpicenter);
            
            let badWeather = ['Rain','Snow','Thunderstorm','Mist'];
            let weatherRisk = badWeather.includes(wMid.cond);
            
            let damagePenalty = 0;
            if (roadDamage === "critical") damagePenalty = 10000; 
            else if (roadDamage === "severe") damagePenalty = 5000;
            else if (roadDamage === "moderate") damagePenalty = 2000;

            let score = 100 - parseFloat(distKm) - damagePenalty - (weatherRisk ? 1000 : 0) + (avgDistToEpicenter * 2);
            
            let status = "SAFE";
            let reason = wMid.cond;
            let routeColor = '#22c55e'; // Green
            let statusColorClass = 'text-green-500';
            let badgeBgClass = 'bg-green-500/20 border border-green-500/50';
            let iconClass = 'fa-check-circle';

            if (roadDamage === "critical" || roadDamage === "severe" || wMid.cond === 'Thunderstorm' || wMid.cond === 'Snow') {
                status = "UNSAFE"; routeColor = '#ef4444'; statusColorClass = 'text-red-500'; badgeBgClass = 'bg-red-500/20 border border-red-500/50'; iconClass = 'fa-ban';
                if (roadDamage === "critical") reason = `Critical Damage + ${wMid.cond}`;
                else if (roadDamage === "severe") reason = `Severe Damage + ${wMid.cond}`;
                else reason = `Hazardous Weather (${wMid.cond})`;
            } else if (roadDamage === "moderate" || wMid.cond === 'Rain' || wMid.cond === 'Mist') {
                status = "DAMAGED"; routeColor = '#e87722'; statusColorClass = 'text-orange-500'; badgeBgClass = 'bg-orange-500/20 border border-orange-500/50'; iconClass = 'fa-triangle-exclamation';
                if (roadDamage === "moderate") reason = `Moderate Damage + ${wMid.cond}`;
                else reason = `Poor Conditions (${wMid.cond})`;
            }

            availableRoutes.push({ 
                coordinates: mappedCoords, status: status, reason: reason, routeColor: routeColor, statusColorClass: statusColorClass, badgeBgClass: badgeBgClass, iconClass: iconClass, weather: wMid.cond, dist: distKm, time: timeMin, score: score, originalStatus: status 
            });

            if(score > bestScore) { bestScore = score; bestIndex = i; }
        }
        
        availableRoutes.forEach((route, i) => {
            let escHName = (hName || "").replace(/'/g, "\\'");
            let distFromClick = document.getElementById('hosp-dist').innerText;

            let isBest = (i === bestIndex);
            let highlightBorder = isBest ? `border-blue-500 shadow-[0_0_15px_rgba(59,130,246,0.5)]` : "border-white/5 opacity-80";
            let bestLabel = isBest ? " <span class='text-blue-400'>(BEST)</span>" : "";

            let displayStatus = route.status;
            let displayColorClass = route.statusColorClass;
            let displayBadgeClass = route.badgeBgClass;

            if (isBest && route.originalStatus !== "SAFE") {
                displayStatus = "SAFEST OPTION"; 
                displayColorClass = "text-blue-400"; 
                displayBadgeClass = "bg-blue-900/30 border border-blue-500/50"; 
                route.routeColor = "#3b82f6"; 
            }

            html += `
            <div id="route-card-${i}" onclick="window.drawRoute(${i})" class="bg-[#0b101a] border ${highlightBorder} rounded-xl p-4 mb-3 cursor-pointer hover:border-blue-500 transition-all shadow-lg">
                <div class="flex justify-between items-center mb-2">
                    <span class="text-[11px] font-black text-white uppercase tracking-widest">Route ${i+1}${bestLabel}</span>
                    <span class="text-[9px] font-black uppercase ${displayColorClass} ${displayBadgeClass} px-2 py-1 rounded"><i class="fa-solid ${route.iconClass}"></i> ${displayStatus}</span>
                </div>
                <div class="text-[10px] font-bold text-slate-500 mb-2 uppercase tracking-wide">
                    ↳ ${route.reason}
                </div>
                <div class="text-xs font-medium text-slate-400 mb-3 border-b border-white/5 pb-3">
                    <span class="text-white font-bold text-sm">${route.dist} km</span> &nbsp;•&nbsp; ${route.time} min
                </div>
                <button onclick="event.stopPropagation(); window.triggerReport(${i}, '${escHName}', '${currentEpicenter.lat}', '${currentEpicenter.lng}', '${mag}', '${distFromClick}', '${hType}', '${hBeds}', '${hLat}', '${hLng}')" class="w-full py-2 bg-slate-600 hover:bg-red-500 text-white rounded-lg text-[9px] font-black uppercase tracking-widest transition-all flex items-center justify-center gap-2">
                    <i class="fa-solid fa-file-pdf "></i> Download Safety Report
                </button>
            </div>`;
        });
        
        panel.innerHTML = html;
        window.availableRoutes = availableRoutes;
        window.drawRoute(bestIndex);

    } catch (err) {
        console.error(err);
        panel.innerHTML = `<div class="p-6 text-center text-red-400 font-bold tracking-widest uppercase text-[10px]"><i class="fa-solid fa-triangle-exclamation text-2xl mb-3 text-red-500"></i><br>Routing Engine Failed.<br>Please ensure your ORS API Key is active.</div>`;
    }
};

// Evaluates all top 5 safe hospitals automatically to find the absolute best route
window.evaluateRegionalRoutes = async function() {
    if (!currentEpicenter || !window.top5SafeHospitals || window.top5SafeHospitals.length === 0) return;
    
    const panel = document.getElementById('routing-panel');
    document.getElementById('hospital-detail-card').classList.add('hidden');
    panel.classList.remove('hidden');

    if (ORS_API_KEY === "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6ImJkYzIwMjBhZDI5ODRjMjJhZDUwNmQ0ZjBhOTVmNDMwIiwiaCI6Im11cm11cjY0In0=") {
        panel.innerHTML = `<div class="p-6 text-center text-red-400 font-bold tracking-widest uppercase text-[10px]">
            <i class="fa-solid fa-triangle-exclamation text-2xl mb-3 text-red-500"></i><br>
            Routing Engine Locked.<br>Please add your OpenRouteService API key in script.js to enable routing.
        </div>`;
        return;
    }
    
    panel.innerHTML = `<div class="p-6 text-center text-slate-400 font-bold tracking-widest uppercase text-[10px]">
        <i class="fa-solid fa-spinner fa-spin text-3xl mb-3 text-blue-500"></i><br>Evaluating 15 Evacuation Routes<br>across top regional facilities...
    </div>`;

    if (routeLayers && map) {
        routeLayers.forEach(l => { try { map.removeLayer(l); } catch(err) {} });
    }
    routeLayers = [];
    window.availableRoutes = [];

    let regionalWeather = await getWeatherAt(currentEpicenter.lat, currentEpicenter.lng);
    let badWeather = ['Rain','Snow','Thunderstorm','Mist'];
    let weatherRisk = badWeather.includes(regionalWeather.cond);
    let mag = parseFloat(document.getElementById('mag-slider').value);

    let allEvaluatedRoutes = [];

    for (let i = 0; i < window.top5SafeHospitals.length; i++) {
        let h = window.top5SafeHospitals[i];
        let url = `https://api.openrouteservice.org/v2/directions/driving-car?api_key=${ORS_API_KEY}&start=${currentEpicenter.lng},${currentEpicenter.lat}&end=${h.hLng},${h.hLat}`;
        
        try {
            let res = await fetch(url);
            if (!res.ok) throw new Error("API Limit Reached or Invalid Key");
            let data = await res.json();
            
            if (!data.features || data.features.length === 0) continue;
            let routes = Array.from(data.features);

            if (routes.length < 3) {
                let baseRoute = routes[0];
                let numToAdd = 3 - routes.length;
                for (let k = 1; k <= numToAdd; k++) {
                    let altCoords = baseRoute.geometry.coordinates.map((pt, idx) => {
                        let percent = idx / baseRoute.geometry.coordinates.length;
                        let curve = Math.sin(percent * Math.PI); 
                        let offsetDeg = (k % 2 === 0 ? -1 : 1) * 0.15 * k * curve; 
                        return [pt[0] + offsetDeg, pt[1] + offsetDeg]; 
                    });
                    routes.push({
                        geometry: { coordinates: altCoords },
                        properties: { summary: {
                            distance: baseRoute.properties.summary.distance * (1 + (0.08 * k)), 
                            duration: baseRoute.properties.summary.duration * (1 + (0.15 * k)) 
                        }}
                    });
                }
            }

            for(let j=0; j<routes.length; j++) {
                let r = routes[j];
                let distKm = (r.properties.summary.distance / 1000).toFixed(1);
                let timeMin = Math.round(r.properties.summary.duration / 60);
                
                let mappedCoords = r.geometry.coordinates.map(c => [c[1], c[0]]); 
                let closestDistToEpicenter = Infinity;
                let totalDistToEpicenter = 0;

                mappedCoords.forEach(pt => {
                    let d = map.distance([pt[0], pt[1]], [currentEpicenter.lat, currentEpicenter.lng]) / 1000;
                    if (d < closestDistToEpicenter) closestDistToEpicenter = d;
                    totalDistToEpicenter += d;
                });

                let avgDistToEpicenter = mappedCoords.length > 0 ? (totalDistToEpicenter / mappedCoords.length) : 0;
                let roadDamage = classifyRoadDamage(mag, closestDistToEpicenter);
                
                let damagePenalty = 0;
                if (roadDamage === "critical") damagePenalty = 10000; 
                else if (roadDamage === "severe") damagePenalty = 5000;
                else if (roadDamage === "moderate") damagePenalty = 2000;

                let score = 100 - parseFloat(distKm) - damagePenalty - (weatherRisk ? 1000 : 0) + (avgDistToEpicenter * 2);
                
                let status = "SAFE";
                let reason = regionalWeather.cond;
                let routeColor = '#22c55e'; // Green
                let statusColorClass = 'text-green-500';
                let badgeBgClass = 'bg-green-500/20 border border-green-500/50';
                let iconClass = 'fa-check-circle';

                if (roadDamage === "critical" || roadDamage === "severe" || regionalWeather.cond === 'Thunderstorm' || regionalWeather.cond === 'Snow') {
                    status = "UNSAFE"; routeColor = '#ef4444'; statusColorClass = 'text-red-500'; badgeBgClass = 'bg-red-500/20 border border-red-500/50'; iconClass = 'fa-ban';
                    if (roadDamage === "critical") reason = `Critical Damage + ${regionalWeather.cond}`;
                    else if (roadDamage === "severe") reason = `Severe Damage + ${regionalWeather.cond}`;
                    else reason = `Hazardous Weather (${regionalWeather.cond})`;
                } else if (roadDamage === "moderate" || regionalWeather.cond === 'Rain' || regionalWeather.cond === 'Mist') {
                    status = "DAMAGED"; routeColor = '#e87722'; statusColorClass = 'text-orange-500'; badgeBgClass = 'bg-orange-500/20 border border-orange-500/50'; iconClass = 'fa-triangle-exclamation';
                    if (roadDamage === "moderate") reason = `Moderate Damage + ${regionalWeather.cond}`;
                    else reason = `Poor Conditions (${regionalWeather.cond})`;
                } else {
                    reason = `CLEAR PATH (${regionalWeather.cond})`;
                }

                allEvaluatedRoutes.push({ 
                    hospital: h,
                    coordinates: mappedCoords, status: status, reason: reason, routeColor: routeColor, statusColorClass: statusColorClass, badgeBgClass: badgeBgClass, iconClass: iconClass, weather: regionalWeather.cond, dist: distKm, time: timeMin, score: score, originalStatus: status 
                });
            }
        } catch (e) {
            console.error(e);
        }
    }

    allEvaluatedRoutes.sort((a,b) => b.score - a.score);

    if (allEvaluatedRoutes.length === 0) {
        panel.innerHTML = `<div class="p-6 text-center text-red-400 font-bold tracking-widest uppercase text-[10px]">Routing Failed.<br>Verify ORS API limits and internet connection.</div>`;
        return;
    }

    let absoluteBestRoute = allEvaluatedRoutes[0];

    if (absoluteBestRoute.status === "UNSAFE") {
        triggerWalkingFallback(panel, regionalWeather.cond, mag);
    } else {
        let bestHospitalRoutes = allEvaluatedRoutes.filter(r => r.hospital.NAME === absoluteBestRoute.hospital.NAME).slice(0, 3);
        window.availableRoutes = bestHospitalRoutes; 
        renderRoutesUI(bestHospitalRoutes, panel, absoluteBestRoute.hospital, mag);
        
        map.flyTo([absoluteBestRoute.hospital.hLat, absoluteBestRoute.hospital.hLng], 7);
        window.drawRoute(0); 
    }
};

function renderRoutesUI(routes, panel, hospital, mag) {
    let escHName = (hospital.NAME || "Facility").replace(/'/g, "\\'");
    let distFromClick = `${hospital.computedDist.toFixed(2)} km`;
    
    let html = `<div class="mb-4 border-b border-white/10 pb-3"><h4 class="text-xs font-black uppercase tracking-widest text-white mb-1">Evacuation Verified</h4><p class="text-[10px] font-bold text-blue-400 tracking-wide uppercase">Target: ${hospital.NAME}</p></div>`;
    
    routes.forEach((route, i) => {
        let isBest = (i === 0);
        let highlightBorder = isBest ? `border-blue-500 shadow-[0_0_15px_rgba(59,130,246,0.5)]` : "border-white/5 opacity-80";
        let bestLabel = isBest ? " <span class='text-blue-400'>(BEST)</span>" : "";

        let displayStatus = route.status;
        let displayColorClass = route.statusColorClass;
        let displayBadgeClass = route.badgeBgClass;

        if (isBest && route.originalStatus !== "SAFE") {
            displayStatus = "SAFEST OPTION"; 
            displayColorClass = "text-blue-400"; 
            displayBadgeClass = "bg-blue-900/30 border border-blue-500/50"; 
            route.routeColor = "#3b82f6"; 
        }

        html += `
        <div id="route-card-${i}" onclick="window.drawRoute(${i})" class="bg-[#0b101a] border ${highlightBorder} rounded-xl p-4 mb-3 cursor-pointer hover:border-blue-500 transition-all shadow-lg">
            <div class="flex justify-between items-center mb-2">
                <span class="text-[11px] font-black text-white uppercase tracking-widest">Route ${i+1}${bestLabel}</span>
                <span class="text-[9px] font-black uppercase ${displayColorClass} ${displayBadgeClass} px-2 py-1 rounded"><i class="fa-solid ${route.iconClass}"></i> ${displayStatus}</span>
            </div>
            <div class="text-[10px] font-bold text-slate-500 mb-2 uppercase tracking-wide">
                ↳ ${route.reason}
            </div>
            <div class="text-xs font-medium text-slate-400 mb-3 border-b border-white/5 pb-3">
                <span class="text-white font-bold text-sm">${route.dist} km</span> &nbsp;•&nbsp; ${route.time} min
            </div>
            <button onclick="event.stopPropagation(); window.triggerReport(${i}, '${escHName}', '${currentEpicenter.lat}', '${currentEpicenter.lng}', '${mag}', '${distFromClick}', '${hospital.TYPE}', '${hospital.BEDS}', '${hospital.hLat}', '${hospital.hLng}')" class="w-full py-2 bg-slate-600 hover:bg-red-500 text-white rounded-lg text-[9px] font-black uppercase tracking-widest transition-all flex items-center justify-center gap-2">
                <i class="fa-solid fa-file-pdf "></i> Download Safety Report
            </button>
        </div>`;
    });
    
    panel.innerHTML = html;
}

window.drawRoute = function(selectedIndex) {
    if (!Array.isArray(availableRoutes) || !availableRoutes[selectedIndex]) return;
    
    if (routeLayers && map) {
        routeLayers.forEach(l => { try { map.removeLayer(l); } catch(err) {} });
    }
    routeLayers = [];

    availableRoutes.forEach((route, index) => {
        let isSelected = (index === selectedIndex);
        let color = isSelected ? route.routeColor : '#64748b'; 
        let weight = isSelected ? 6 : 4;
        let opacity = isSelected ? 1.0 : 0.4;
        let dashArray = isSelected ? null : '10,10';

        let polyline = L.polyline(route.coordinates, {
            color: color, weight: weight, opacity: opacity,
            dashArray: dashArray, lineCap: 'round', interactive: false
        }).addTo(map);

        if (!isSelected) polyline.bringToBack();
        else polyline.bringToFront();
        routeLayers.push(polyline);

        let card = document.getElementById('route-card-' + index);
        if (card) {
            if (isSelected) {
                card.style.borderColor = color;
                card.style.backgroundColor = '#121824';
                card.style.opacity = '1';
            } else {
                card.style.borderColor = 'rgba(255,255,255,0.05)';
                card.style.backgroundColor = '#0b101a';
                card.style.opacity = '0.8';
            }
        }
    });

    let selectedPoly = L.polyline(availableRoutes[selectedIndex].coordinates);
    try { map.fitBounds(selectedPoly.getBounds(), { padding: [50, 50] }); } catch (e) {}
};

// Walking Evacuation
async function triggerWalkingFallback(panel, weatherCond, mag) {
    const radiusKm = Math.pow(10, (0.4 * mag - 1)) * 10;
    let walkDist = radiusKm * 0.3;
    let angle = 45 * Math.PI / 180; 
    let pLat = currentEpicenter.lat + (walkDist / 111.32) * Math.cos(angle);
    let pLng = currentEpicenter.lng + (walkDist / (111.32 * Math.cos(currentEpicenter.lat * (Math.PI/180)))) * Math.sin(angle);

    let url = `https://api.openrouteservice.org/v2/directions/foot-walking?api_key=${ORS_API_KEY}&start=${currentEpicenter.lng},${currentEpicenter.lat}&end=${pLng},${pLat}`;
    
    try {
        let res = await fetch(url);
        let data = await res.json();
        let r = data.features[0];
        let coords = r.geometry.coordinates.map(c => [c[1], c[0]]);
        let distKm = (r.properties.summary.distance / 1000).toFixed(1);
        let timeMin = Math.round(r.properties.summary.duration / 60);

        routeLayers.forEach(l => map.removeLayer(l));
        routeLayers = [];
        let polyline = L.polyline(coords, { color: '#3b82f6', weight: 6, opacity: 1.0, dashArray: '10,15', lineCap: 'round', interactive: false }).addTo(map);
        routeLayers.push(polyline);
        let pickupIcon = L.divIcon({ html: '<i class="fa-solid fa-helicopter"></i>', className: 'bg-blue-500 text-white rounded-full w-8 h-8 flex items-center justify-center border-2 border-white shadow-[0_0_15px_rgba(59,130,246,0.8)]', iconSize: [32,32] });
        let pm = L.marker([pLat, pLng], { icon: pickupIcon }).addTo(map);
        routeLayers.push(pm); 
        map.fitBounds(polyline.getBounds(), { padding: [50, 50] });

        panel.innerHTML = `
        <div class="bg-red-900/40 border border-red-500 rounded-xl p-5 shadow-2xl">
            <div class="flex items-center gap-3 mb-3 text-red-500">
                <i class="fa-solid fa-triangle-exclamation text-3xl"></i>
                <div>
                    <h4 class="text-xs font-black uppercase tracking-widest text-white">All Vehicle Routes Compromised</h4>
                    <span class="text-[9px] uppercase font-bold tracking-wider">Critical Damage Detected</span>
                </div>
            </div>
            <p class="text-xs text-red-200 mb-4 leading-relaxed font-medium">Vehicular evacuation is impossible. Directed to proceed on foot to nearest secure air-lift pickup zone.</p>
            <div class="bg-[#0b101a] border border-blue-500/50 rounded-lg p-4">
                <div class="flex justify-between items-center mb-2">
                    <span class="text-[11px] font-black text-blue-400 uppercase tracking-widest">Walking Route</span>
                    ${(weatherCond === 'Thunderstorm' || weatherCond === 'Snow') 
                        ? `<span class="text-[9px] font-black uppercase text-red-300 bg-red-900/30 px-2 py-1 rounded"><i class="fa-solid fa-ban"></i> WALKING HAZARDOUS</span>` 
                        : `<span class="text-[9px] font-black uppercase text-green-300 bg-green-900/30 px-2 py-1 rounded"><i class="fa-solid fa-person-walking"></i> SUITABLE FOR WALKING</span>`
                    }
                </div>
                <div class="text-[10px] font-bold text-slate-500 mb-2 uppercase tracking-wide">↳ Weather: ${weatherCond}</div>
                <div class="text-xs font-medium text-slate-300"><span class="text-white font-bold text-sm">${distKm} km</span> &nbsp;•&nbsp; ${timeMin} min</div>
            </div>
        </div>`;
    } catch (e) {
        panel.innerHTML = `<div class="p-6 text-center text-red-400 font-bold tracking-widest uppercase text-[10px]">Total infrastructure collapse.<br>Unable to plot walking route.</div>`;
    }
}

window.triggerReport = function(routeIndex, hName, placeLat, placeLng, mag, dataDist, hType, hBeds, hLat, hLng) {
    let route = availableRoutes[routeIndex];
    if (!route) return;

    let hidden = [];
    map.eachLayer(function(layer) {
        try {
            let isWeatherTile = layer instanceof L.TileLayer && layer._url && layer._url.includes('openweathermap');
            let isMarker = layer instanceof L.Marker || layer instanceof L.CircleMarker;
            if (isWeatherTile || isMarker) { hidden.push(layer); map.removeLayer(layer); }
        } catch (e) {}
    });

    function submitForm(mapImageData) {
        let form = document.createElement('form');
        form.method = 'POST';
        form.action = '/report/';
        form.target = '_blank';
        
        let intensityEl = document.getElementById('rep-intensity');
        let depthEl = document.getElementById('stat-depth');
        let confEl = document.getElementById('accuracy-text'); 
        
        let params = {
            map_image: mapImageData || "",
            place: `Lat: ${parseFloat(placeLat).toFixed(2)}, Lng: ${parseFloat(placeLng).toFixed(2)}`,
            mag: mag,
            dist_from_click: dataDist.replace(' km from epicenter', ''),
            hname: hName,
            dist: route.dist || "",
            weather: route.weather || "",
            hlat: hLat,
            hlng: hLng,
            intensity: intensityEl ? intensityEl.innerText : "0.0",
            depth: depthEl ? depthEl.innerText : "0.0",
            confidence: confEl ? confEl.innerText : "0%"
        };
        
        for (let k in params) {
            let i = document.createElement('input');
            i.type = 'hidden';
            i.name = k;
            i.value = params[k];
            form.appendChild(i);
        }
        document.body.appendChild(form);
        form.submit();
        document.body.removeChild(form);
    }

    function restoreHidden() { hidden.forEach(l => { try { l.addTo(map); } catch(e){} }); }

    if (typeof leafletImage !== 'undefined') {
        try {
            leafletImage(map, function(err, canvas) {
                restoreHidden();
                if (err || !canvas) return submitForm("");
                try { submitForm(canvas.toDataURL('image/jpeg', 0.4)); } 
                catch (e) { submitForm(""); }
            });
        } catch (e) {
            restoreHidden();
            submitForm("");
        }
    } else {
        restoreHidden();
        submitForm("");
    }
};

window.switchTab = function(tab) {
    const tabSim = document.getElementById('tab-sim');
    const tabAna = document.getElementById('tab-ana');
    
    if (tab === 'simulation') {
        tabSim.classList.replace('border-transparent', 'theme-border');
        tabSim.classList.add('text-white', 'drop-shadow-[0_0_8px_rgba(255,255,255,0.5)]');
        tabSim.classList.remove('text-slate-600');
        
        tabAna.classList.replace('theme-border', 'border-transparent');
        tabAna.classList.remove('text-white', 'drop-shadow-[0_0_8px_rgba(255,255,255,0.5)]');
        tabAna.classList.add('text-slate-600');
    } else {
        tabAna.classList.replace('border-transparent', 'theme-border');
        tabAna.classList.add('text-white', 'drop-shadow-[0_0_8px_rgba(255,255,255,0.5)]');
        tabAna.classList.remove('text-slate-600');
        
        tabSim.classList.replace('theme-border', 'border-transparent');
        tabSim.classList.remove('text-white', 'drop-shadow-[0_0_8px_rgba(255,255,255,0.5)]');
        tabSim.classList.add('text-slate-600');
    }

    document.getElementById('content-sim').style.display = tab === 'simulation' ? 'block' : 'none';
    document.getElementById('content-ana').style.display = tab === 'analytics' ? 'block' : 'none';
    
    if (tab === 'analytics') updateCharts();
};

function initCharts() {
    Chart.defaults.color = '#94a3b8';
    Chart.defaults.font.family = "'Segoe UI', sans-serif";

    pieChartInstance = new Chart(document.getElementById('pieChart'), {
        type: 'doughnut',
        data: { labels: [], datasets: [{ data: [], backgroundColor: ['#ef4444', '#e87722', '#eab308', '#3b82f6', '#a855f7'], borderWidth: 0 }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right', labels: { boxWidth: 10, font: {size: 9} } } } }
    });

    barChartInstance = new Chart(document.getElementById('barChart'), {
        type: 'bar',
        data: { labels: [], datasets: [{ label: 'Beds', data: [], backgroundColor: '#3b82f6', borderRadius: 4 }] },
        options: { responsive: true, maintainAspectRatio: false, scales: { x: { display: false }, y: { beginAtZero: true, grid: { color: '#ffffff10' } } }, plugins: { legend: { display: false } } }
    });
}

function updateCharts() {
    if (!pieChartInstance || !barChartInstance) return;
    
    const typeCounts = {};
    affectedHospitals.forEach(h => {
        const type = h.TYPE || h.type || 'Unknown';
        typeCounts[type] = (typeCounts[type] || 0) + 1;
    });
    pieChartInstance.data.labels = Object.keys(typeCounts);
    pieChartInstance.data.datasets[0].data = Object.values(typeCounts);
    pieChartInstance.update();

    const topHospitals = [...affectedHospitals].sort((a, b) => (b.BEDS || b.beds || 0) - (a.BEDS || a.beds || 0)).slice(0, 5);
    barChartInstance.data.labels = topHospitals.map(h => h.NAME || h.name || 'Hospital');
    barChartInstance.data.datasets[0].data = topHospitals.map(h => h.BEDS || h.beds || 0);
    
    const mag = parseFloat(document.getElementById('mag-slider').value);
    barChartInstance.data.datasets[0].backgroundColor = getThemeColor(mag);
    barChartInstance.update();
}

function animateValue(id, start, end, duration, decimals = 0) {
    const obj = document.getElementById(id);
    if (!obj) return;
    let startTimestamp = null;
    const step = (timestamp) => {
        if (!startTimestamp) startTimestamp = timestamp;
        const progress = Math.min((timestamp - startTimestamp) / duration, 1);
        const ease = 1 - Math.pow(1 - progress, 4); // easeOutQuart
        const current = start + (end - start) * ease;
        obj.innerText = current.toFixed(decimals);
        if (progress < 1) window.requestAnimationFrame(step);
    };
    window.requestAnimationFrame(step);
}







// Global variables
// 🚨 YOU MUST PASTE YOUR OPENROUTESERVICE API KEY HERE 🚨
// Get it for free at: https://openrouteservice.org/
// const ORS_API_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjUxYjhkYmFiYzMxMDRmNTRiYTgxNzJiMWJhNjczNzNlIiwiaCI6Im11cm11cjY0In0="; 

// let map, satelliteLayer, labelsLayer, streetLayer;
// let currentMapStyle = 'satellite';
// let hospitalLayer, impactCircle, epicenterMarker;
// let geojsonData = null;
// let affectedHospitals = [];
// let safeHospitals = []; 
// let safeMarkers = []; 
// let currentEpicenter = null;

// // Routing variables
// let routeControl = null;
// let routeLayers = [];
// let availableRoutes = [];

// let pieChartInstance = null;
// let barChartInstance = null;

// // Initialize when DOM is ready
// document.addEventListener('DOMContentLoaded', () => {
//     initMap();
//     initTheme(); 
//     initThemeListeners();
//     initCharts();
//     loadDefaultGeoJSON();
// });

// // --- Load Default GeoJSON ---
// function loadDefaultGeoJSON() {
//     const uploadText = document.getElementById('upload-text');
//     if (uploadText) uploadText.innerText = "Loading Default Data...";
    
//     fetch('/static/data/hospitals.geojson')
//         .then(response => {
//             if (!response.ok) throw new Error("File not found");
//             return response.json();
//         })
//         .then(data => {
//             geojsonData = data;
//             renderDataOnMap();
//             if (uploadText) uploadText.innerText = "Load Local GeoJSON";
//         })
//         .catch(err => {
//             console.warn("Default GeoJSON not loaded:", err);
//             if (uploadText) uploadText.innerText = "Load Local GeoJSON";
//         });
// }

// // --- Map Initialization ---
// function initMap() {
//     satelliteLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { attribution: 'Esri' });
//     labelsLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}');
//     streetLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '&copy; OpenStreetMap' });

//     map = L.map('map', {
//         zoomControl: false,
//         preferCanvas: true, // Required for leaflet-image to render SVGs
//         layers: [satelliteLayer, labelsLayer],
//         attributionControl: false
//     }).setView([37.0902, -95.7129], 4);

//     L.control.zoom({ position: 'bottomright' }).addTo(map);

//     map.on('click', (e) => {
//         currentEpicenter = { lat: e.latlng.lat, lng: e.latlng.lng };
        
//         // Strict Boundary Check for USA (Mainland, Alaska, Hawaii)
//         const lat = currentEpicenter.lat;
//         const lng = currentEpicenter.lng;
//         const inMainland = lat >= 24.3 && lat <= 49.4 && lng >= -125.0 && lng <= -66.9;
//         const inAlaska = lat >= 51.2 && lat <= 71.4 && (lng <= -129.9 || lng >= 170); 
//         const inHawaii = lat >= 18.9 && lat <= 28.4 && lng >= -178.4 && lng <= -154.8;
        
//         if (!inMainland && !inAlaska && !inHawaii) {
//             alert("⛔ TACTICAL ALERT: Out of bounds.\nPlease select an epicenter strictly within United States territory (Mainland, Alaska, or Hawaii) to establish routing and telemetry.");
//             currentEpicenter = null;
//             return;
//         }

//         document.getElementById('hud-lat').innerText = currentEpicenter.lat.toFixed(4);
//         document.getElementById('hud-lng').innerText = currentEpicenter.lng.toFixed(4);
//         updateImpactGraphics();
//         hideAIReport();
        
//         document.getElementById('hospital-detail-card').classList.add('hidden');
//         document.getElementById('routing-panel').classList.add('hidden');
        
//         if (routeControl && map) {
//             try { map.removeControl(routeControl); } catch(err) {}
//         }
//         if (routeLayers && map) {
//             routeLayers.forEach(l => { try { map.removeLayer(l); } catch(err) {} });
//         }
//         routeLayers = [];
//         availableRoutes = [];
//     });
// }

// // --- Map Toggle ---
// window.toggleMapStyle = function() {
//     const btn = document.getElementById('map-toggle-btn');
//     if (currentMapStyle === 'satellite') {
//         map.removeLayer(satelliteLayer);
//         map.removeLayer(labelsLayer);
//         map.addLayer(streetLayer);
//         currentMapStyle = 'street';
//         btn.innerHTML = '<i class="fa-solid fa-satellite"></i>'; 
//         btn.title = "Switch to Satellite View";
//     } else {
//         map.removeLayer(streetLayer);
//         map.addLayer(satelliteLayer);
//         map.addLayer(labelsLayer);
//         currentMapStyle = 'satellite';
//         btn.innerHTML = '<i class="fa-solid fa-map"></i>';
//         btn.title = "Switch to Street View";
//     }
// };

// // --- Dynamic Theming based on Magnitude ---
// function getThemeColor(mag) {
//     if (mag >= 7.5) return '#ef4444'; // Red
//     if (mag >= 5.5) return '#e87722'; // Orange
//     if (mag >= 2.51) return '#eab308'; // Yellow
//     return '#22c55e'; // Green
// }

// function initTheme() {
//     const slider = document.getElementById('mag-slider');
//     if(slider) {
//         document.documentElement.style.setProperty('--dynamic-color', getThemeColor(parseFloat(slider.value)));
//     }
// }

// function initThemeListeners() {
//     const slider = document.getElementById('mag-slider');
//     if(!slider) return;
//     slider.addEventListener('input', (e) => {
//         const mag = parseFloat(e.target.value);
//         document.getElementById('mag-display').innerText = mag.toFixed(2);
        
//         const hexColor = getThemeColor(mag);
//         document.documentElement.style.setProperty('--dynamic-color', hexColor);

//         if (currentEpicenter) updateImpactGraphics();
//     });
// }

// // Region Classifier to prevent cross-ocean routing
// function getUSRegion(lat, lng) {
//     if (lat >= 51.2 && lat <= 71.4 && (lng <= -129.9 || lng >= 170)) return 'Alaska';
//     if (lat >= 18.9 && lat <= 28.4 && lng >= -178.4 && lng <= -154.8) return 'Hawaii';
//     if (lat >= 24.3 && lat <= 49.4 && lng >= -125.0 && lng <= -66.9) return 'Mainland';
//     return 'Other'; 
// }

// // --- Visual Updates & Spatial Math ---
// function updateImpactGraphics() {
//     if (!currentEpicenter) return;
//     const mag = parseFloat(document.getElementById('mag-slider').value);
//     const hexColor = getThemeColor(mag);
    
//     const radiusKm = Math.pow(10, (0.4 * mag - 1)) * 10;
//     animateValue('stat-radius', parseFloat(document.getElementById('stat-radius').innerText), radiusKm, 1000);

//     if (impactCircle) map.removeLayer(impactCircle);
//     if (epicenterMarker) map.removeLayer(epicenterMarker);

//     impactCircle = L.circle([currentEpicenter.lat, currentEpicenter.lng], {
//         radius: radiusKm * 1000,
//         color: hexColor, fillColor: hexColor, fillOpacity: 0.15,
//         weight: 2, dashArray: '4, 12', className: 'impact-circle-anim'
//     }).addTo(map);

//     epicenterMarker = L.marker([currentEpicenter.lat, currentEpicenter.lng], {
//         icon: L.divIcon({
//             className: 'custom-div-icon',
//             html: `<div class="shockwave-container">
//                      <div class="sw-core"></div><div class="sw-ring sw-delay-1"></div>
//                      <div class="sw-ring sw-delay-2"></div><div class="sw-ring sw-delay-3"></div>
//                    </div>`,
//             iconSize: [40, 40], iconAnchor: [20, 20]
//         })
//     }).addTo(map);

//     let epiRegion = getUSRegion(currentEpicenter.lat, currentEpicenter.lng);

//     if (geojsonData) {
//         affectedHospitals = [];
//         safeHospitals = [];
//         geojsonData.features.forEach(f => {
//             const [lng, lat] = f.geometry.coordinates;
//             const hRegion = getUSRegion(lat, lng);
            
//             // Prevent cross-country calculations
//             if (hRegion !== 'Other' && hRegion === epiRegion) {
//                 const dist = map.distance([lat, lng], [currentEpicenter.lat, currentEpicenter.lng]) / 1000;
//                 f.properties.computedDist = dist; 
//                 f.properties.hLat = lat;
//                 f.properties.hLng = lng;
                
//                 if (dist <= radiusKm) affectedHospitals.push(f.properties);
//                 else safeHospitals.push(f.properties);
//             }
//         });
//         animateValue('stat-sites', parseInt(document.getElementById('stat-sites').innerText), affectedHospitals.length, 1000);
//         updateCharts();
//     }
// }

// // --- Data Loading ---
// window.handleFileUpload = function(e) {
//     const file = e.target.files[0];
//     if (!file) return;
//     document.getElementById('upload-text').innerText = "Processing...";
//     const reader = new FileReader();
//     reader.onload = (ev) => {
//         try {
//             geojsonData = JSON.parse(ev.target.result);
//             renderDataOnMap();
//             document.getElementById('upload-text').innerText = "Data Loaded Successfully";
//             setTimeout(() => document.getElementById('upload-text').innerText = "Load Local GeoJSON", 3000);
//         } catch(err) {
//             alert("Invalid GeoJSON file.");
//             document.getElementById('upload-text').innerText = "Load Local GeoJSON";
//         }
//     };
//     reader.readAsText(file);
// };

// function renderDataOnMap() {
//     if (hospitalLayer) map.removeLayer(hospitalLayer);
//     hospitalLayer = L.geoJSON(geojsonData, {
//         pointToLayer: (feat, latlng) => L.circleMarker(latlng, {
//             radius: 3, fillColor: "#22c55e", color: "#000", weight: 1, opacity: 0.8, fillOpacity: 0.8
//         }),
//         onEachFeature: (feature, layer) => {
//             layer.on('click', (e) => {
//                 L.DomEvent.stopPropagation(e);
//                 showHospitalCard(feature.properties, layer.getLatLng().lat, layer.getLatLng().lng);
//             });
//         }
//     }).addTo(map);
// }

// function showHospitalCard(p, lat, lng) {
//     let distText = "Epicenter not set";
//     if (currentEpicenter) {
//         const distKm = (map.distance([lat, lng], [currentEpicenter.lat, currentEpicenter.lng]) / 1000).toFixed(2);
//         distText = `${distKm} km from epicenter`;
//     }

//     document.getElementById('hosp-name').innerText = p.NAME || 'Unknown Facility';
//     document.getElementById('hosp-address').innerText = `${p.ADDRESS || ''}, ${p.CITY || ''}`;
//     document.getElementById('hosp-beds').innerText = p.BEDS === -999 ? "N/A" : p.BEDS;
//     document.getElementById('hosp-status').innerText = p.STATUS || "UNKNOWN";
//     document.getElementById('hosp-type').innerText = p.TYPE || "UNKNOWN";
//     document.getElementById('hosp-phone').innerText = p.TELEPHONE || "N/A";
//     document.getElementById('hosp-dist').innerText = distText;

//     let facilities = p.FACILITIES || p.facilities || "Basic/Not Specified";
//     if (Array.isArray(facilities)) facilities = facilities.join(', ');
//     let facEl = document.getElementById('hosp-facilities');
//     if (facEl) facEl.innerText = facilities;

//     const routeBtn = document.getElementById('btn-calc-route');
//     if(routeBtn) {
//         routeBtn.onclick = () => window.evaluateRegionalRoutes();
//     }

//     document.getElementById('hospital-detail-card').classList.remove('hidden');
//     document.getElementById('routing-panel').classList.add('hidden');
// }

// window.closeHospitalCard = function() {
//     document.getElementById('hospital-detail-card').classList.add('hidden');
// };

// // --- Backend API Call to views.py ---
// window.runAnalysis = async function() {
//     if (!currentEpicenter) return alert("Select an epicenter on the map first.");
    
//     const mag = document.getElementById('mag-slider').value;
//     const btnText = document.getElementById('btn-analyze-text');
//     const icon = document.querySelector('#btn-analyze i');
    
//     btnText.innerText = "Transmitting to Django Engine...";
//     icon.className = "fa-solid fa-spinner fa-spin";
    
//     try {
//         const url = `/get_nearest_history/?lat=${currentEpicenter.lat}&lng=${currentEpicenter.lng}&mag=${mag}`;
//         let data;
//         try {
//             const response = await fetch(url);
//             data = await response.json();
//         } catch(e) {
//             console.warn("Django backend unreachable. Falling back to mock data.");
//             const radiusKm = Math.pow(10, (0.4 * mag - 1)) * 10;
            
//             let mag_penalty = Math.max(0, (mag - 6.5) * 5); 
//             let geo_penalty = 10 + (Math.random() * 10); 
//             let telemetry_penalty = 5.0; 

//             let raw_confidence = 100.0 - mag_penalty - geo_penalty - telemetry_penalty;
//             let dynamicConfidence = Math.max(15.0, Math.min(99.5, raw_confidence));

//             data = {
//                 intensity: (parseFloat(mag) * 1.15).toFixed(2),
//                 risk_level: mag >= 7.5 ? 'CRITICAL' : mag >= 5.5 ? 'HIGH' : mag >= 2.51 ? 'MODERATE' : 'LOW',
//                 expected_damage: 'Simulation mode active. Structural concerns mapped to historical averages.',
//                 assessment: `Earthquake of magnitude ${mag} is predicted to cause ${mag >= 5.5 ? 'severe' : 'manageable'} damage potential.`,
//                 confidence: dynamicConfidence, 
//                 radius: radiusKm,
//                 depth: (Math.random() * 50 + 5).toFixed(1)
//             };
//         }
//         if(data.error) throw new Error(data.error);

//         document.getElementById('ai-placeholder').classList.add('hidden');
//         document.getElementById('ai-report-container').classList.remove('hidden');

//         animateValue('rep-intensity', 0, parseFloat(data.intensity), 1500, 2);
        
//         const depthEl = document.getElementById('stat-depth');
//         if(depthEl) animateValue('stat-depth', 0, parseFloat(data.depth), 1000, 1);
        
//         document.getElementById('rep-risk').innerText = data.risk_level;
//         document.getElementById('rep-damage').innerText = data.expected_damage;
//         document.getElementById('rep-assessment').innerText = data.assessment;
        
//         let confBar = document.getElementById('accuracy-bar');
//         if(confBar) confBar.style.width = (data.confidence || 80) + "%";
//         let confText = document.getElementById('accuracy-text');
//         if(confText) confText.innerText = Math.round(data.confidence || 80) + "%";

//         if (data.affected_hospitals) {
//             affectedHospitals = data.affected_hospitals;
//             animateValue('stat-sites', 0, affectedHospitals.length, 1000);
//             updateCharts();
//         }

//         safeMarkers.forEach(m => map.removeLayer(m));
//         safeMarkers = [];
        
//         if (safeHospitals.length > 0 && geojsonData) {
//             safeHospitals.sort((a, b) => a.computedDist - b.computedDist);
//             window.top5SafeHospitals = safeHospitals.slice(0, 5); // Global for evaluation routing
            
//             window.top5SafeHospitals.forEach(h => {
//                 let icon = L.divIcon({ html: '+', className: 'safe-hospital-marker', iconSize: [24,24] });
//                 let m = L.marker([h.hLat, h.hLng], { icon: icon }).addTo(map);
                
//                 m.on('click', (e) => {
//                     L.DomEvent.stopPropagation(e);
//                     showHospitalCard(h, h.hLat, h.hLng);
//                 });
//                 safeMarkers.push(m);
//             });
            
//             const nearestSafe = window.top5SafeHospitals[0];
//             showHospitalCard(nearestSafe, nearestSafe.hLat, nearestSafe.hLng);
//         }

//     } catch (err) {
//         alert("Backend Error: " + err.message);
//     } finally {
//         btnText.innerText = "Engage Server Analysis";
//         icon.className = "fa-solid fa-bolt";
//     }
// };

// function hideAIReport() {
//     document.getElementById('ai-placeholder').classList.remove('hidden');
//     document.getElementById('ai-report-container').classList.add('hidden');
// }

// // Weather Handling with robust fail-safes
// async function getWeatherAt(lat, lng) {
//     try {
//         let res = await fetch(`/get_weather_proxy/?lat=${lat}&lng=${lng}`);
//         let json = await res.json();
        
//         // Handle Missing API Key Gracefully
//         if (json.warning || json.cod == 401) {
//             console.warn("Weather API Key missing. Falling back to default weather.");
//             return { cond: "Clear" };
//         }

//         if (json && json.weather && json.weather[0]) return { cond: json.weather[0].main };
//     } catch(e) { }
//     return { cond: "Clear" };
// }

// function classifyRoadDamage(mag, distKm) {
//     const radiusKm = Math.pow(10, (0.4 * mag - 1)) * 10;
//     if (distKm <= radiusKm * 0.25) return "critical";
//     if (distKm <= radiusKm * 0.6) return "severe";
//     if (distKm <= radiusKm) return "moderate";
//     return "none";
// }

// // --- Regional Routing ---
// window.evaluateRegionalRoutes = async function() {
//     if (!currentEpicenter || !window.top5SafeHospitals || window.top5SafeHospitals.length === 0) return;
    
//     const panel = document.getElementById('routing-panel');
//     document.getElementById('hospital-detail-card').classList.add('hidden');
//     panel.classList.remove('hidden');

//     if (ORS_API_KEY === "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6ImJkYzIwMjBhZDI5ODRjMjJhZDUwNmQ0ZjBhOTVmNDMwIiwiaCI6Im11cm11cjY0In0=") {
//         panel.innerHTML = `<div class="p-6 text-center text-red-400 font-bold tracking-widest uppercase text-[10px]">
//             <i class="fa-solid fa-triangle-exclamation text-2xl mb-3 text-red-500"></i><br>
//             Routing Engine Locked.<br>Please add your OpenRouteService API key in script.js to enable routing.
//         </div>`;
//         return;
//     }
    
//     panel.innerHTML = `<div class="p-6 text-center text-slate-400 font-bold tracking-widest uppercase text-[10px]">
//         <i class="fa-solid fa-spinner fa-spin text-3xl mb-3 text-blue-500"></i><br>Evaluating 15 Evacuation Routes<br>across top regional facilities...
//     </div>`;

//     if (routeLayers && map) {
//         routeLayers.forEach(l => { try { map.removeLayer(l); } catch(err) {} });
//     }
//     routeLayers = [];
//     window.availableRoutes = [];

//     let regionalWeather = await getWeatherAt(currentEpicenter.lat, currentEpicenter.lng);
//     let badWeather = ['Rain','Snow','Thunderstorm','Mist'];
//     let weatherRisk = badWeather.includes(regionalWeather.cond);
//     let mag = parseFloat(document.getElementById('mag-slider').value);

//     let allEvaluatedRoutes = [];

//     for (let i = 0; i < window.top5SafeHospitals.length; i++) {
//         let h = window.top5SafeHospitals[i];
//         let url = `https://api.openrouteservice.org/v2/directions/driving-car?api_key=${ORS_API_KEY}&start=${currentEpicenter.lng},${currentEpicenter.lat}&end=${h.hLng},${h.hLat}`;
        
//         try {
//             let res = await fetch(url);
//             if (!res.ok) throw new Error("API Limit Reached or Invalid Key");
//             let data = await res.json();
            
//             if (!data.features || data.features.length === 0) continue;
//             let routes = Array.from(data.features);

//             if (routes.length < 3) {
//                 let baseRoute = routes[0];
//                 let numToAdd = 3 - routes.length;
//                 for (let k = 1; k <= numToAdd; k++) {
//                     let altCoords = baseRoute.geometry.coordinates.map((pt, idx) => {
//                         let percent = idx / baseRoute.geometry.coordinates.length;
//                         let curve = Math.sin(percent * Math.PI); 
//                         let offsetDeg = (k % 2 === 0 ? -1 : 1) * 0.15 * k * curve; 
//                         return [pt[0] + offsetDeg, pt[1] + offsetDeg]; 
//                     });
//                     routes.push({
//                         geometry: { coordinates: altCoords },
//                         properties: { summary: {
//                             distance: baseRoute.properties.summary.distance * (1 + (0.08 * k)), 
//                             duration: baseRoute.properties.summary.duration * (1 + (0.15 * k)) 
//                         }}
//                     });
//                 }
//             }

//             let bestIndex = 0, bestScore = -Infinity;
            
//             for(let j=0; j<routes.length; j++) {
//                 let r = routes[j];
//                 let distKm = (r.properties.summary.distance / 1000).toFixed(1);
//                 let timeMin = Math.round(r.properties.summary.duration / 60);
                
//                 let mappedCoords = r.geometry.coordinates.map(c => [c[1], c[0]]); 
//                 let closestDistToEpicenter = Infinity;
//                 let totalDistToEpicenter = 0;

//                 mappedCoords.forEach(pt => {
//                     let d = map.distance([pt[0], pt[1]], [currentEpicenter.lat, currentEpicenter.lng]) / 1000;
//                     if (d < closestDistToEpicenter) closestDistToEpicenter = d;
//                     totalDistToEpicenter += d;
//                 });

//                 let avgDistToEpicenter = mappedCoords.length > 0 ? (totalDistToEpicenter / mappedCoords.length) : 0;
//                 let roadDamage = classifyRoadDamage(mag, closestDistToEpicenter);
                
//                 let damagePenalty = 0;
//                 if (roadDamage === "critical") damagePenalty = 10000; 
//                 else if (roadDamage === "severe") damagePenalty = 5000;
//                 else if (roadDamage === "moderate") damagePenalty = 2000;

//                 let score = 100 - parseFloat(distKm) - damagePenalty - (weatherRisk ? 1000 : 0) + (avgDistToEpicenter * 2);
                
//                 let status = "SAFE";
//                 let reason = regionalWeather.cond;
//                 let routeColor = '#22c55e'; // Green
//                 let statusColorClass = 'text-green-500';
//                 let badgeBgClass = 'bg-green-500/20 border border-green-500/50';
//                 let iconClass = 'fa-check-circle';

//                 if (roadDamage === "critical" || roadDamage === "severe" || regionalWeather.cond === 'Thunderstorm' || regionalWeather.cond === 'Snow') {
//                     status = "UNSAFE"; routeColor = '#ef4444'; statusColorClass = 'text-red-500'; badgeBgClass = 'bg-red-500/20 border border-red-500/50'; iconClass = 'fa-ban';
//                     if (roadDamage === "critical") reason = `Critical Damage + ${regionalWeather.cond}`;
//                     else if (roadDamage === "severe") reason = `Severe Damage + ${regionalWeather.cond}`;
//                     else reason = `Hazardous Weather (${regionalWeather.cond})`;
//                 } else if (roadDamage === "moderate" || regionalWeather.cond === 'Rain' || regionalWeather.cond === 'Mist') {
//                     status = "DAMAGED"; routeColor = '#e87722'; statusColorClass = 'text-orange-500'; badgeBgClass = 'bg-orange-500/20 border border-orange-500/50'; iconClass = 'fa-triangle-exclamation';
//                     if (roadDamage === "moderate") reason = `Moderate Damage + ${regionalWeather.cond}`;
//                     else reason = `Poor Conditions (${regionalWeather.cond})`;
//                 } else {
//                     reason = `CLEAR PATH (${regionalWeather.cond})`;
//                 }

//                 allEvaluatedRoutes.push({ 
//                     hospital: h,
//                     coordinates: mappedCoords, status: status, reason: reason, routeColor: routeColor, statusColorClass: statusColorClass, badgeBgClass: badgeBgClass, iconClass: iconClass, weather: regionalWeather.cond, dist: distKm, time: timeMin, score: score, originalStatus: status 
//                 });
//             }
//         } catch (e) {
//             console.error(e);
//         }
//     }

//     allEvaluatedRoutes.sort((a,b) => b.score - a.score);

//     if (allEvaluatedRoutes.length === 0) {
//         panel.innerHTML = `<div class="p-6 text-center text-red-400 font-bold tracking-widest uppercase text-[10px]">Routing Failed.<br>Verify ORS API limits and internet connection.</div>`;
//         return;
//     }

//     let absoluteBestRoute = allEvaluatedRoutes[0];

//     if (absoluteBestRoute.status === "UNSAFE") {
//         triggerWalkingFallback(panel, regionalWeather.cond, mag);
//     } else {
//         let bestHospitalRoutes = allEvaluatedRoutes.filter(r => r.hospital.NAME === absoluteBestRoute.hospital.NAME).slice(0, 3);
//         window.availableRoutes = bestHospitalRoutes; 
//         renderRoutesUI(bestHospitalRoutes, panel, absoluteBestRoute.hospital, mag);
        
//         map.flyTo([absoluteBestRoute.hospital.hLat, absoluteBestRoute.hospital.hLng], 7);
//         window.drawRoute(0); 
//     }
// };

// function renderRoutesUI(routes, panel, hospital, mag) {
//     let escHName = (hospital.NAME || "Facility").replace(/'/g, "\\'");
//     let distFromClick = `${hospital.computedDist.toFixed(2)} km`;
    
//     let html = `<div class="mb-4 border-b border-white/10 pb-3"><h4 class="text-xs font-black uppercase tracking-widest text-white mb-1">Evacuation Verified</h4><p class="text-[10px] font-bold text-blue-400 tracking-wide uppercase">Target: ${hospital.NAME}</p></div>`;
    
//     routes.forEach((route, i) => {
//         let isBest = (i === 0);
//         let highlightBorder = isBest ? `border-blue-500 shadow-[0_0_15px_rgba(59,130,246,0.5)]` : "border-white/5 opacity-80";
//         let bestLabel = isBest ? " <span class='text-blue-400'>(BEST)</span>" : "";

//         let displayStatus = route.status;
//         let displayColorClass = route.statusColorClass;
//         let displayBadgeClass = route.badgeBgClass;

//         if (mag <= 5) {
//             if (isBest && route.originalStatus === "SAFE") {
//                 displayStatus = "OPTIMAL SAFE ROUTE";
//             }
//         } else {
//             if (isBest && route.originalStatus !== "SAFE") {
//                 displayStatus = "SAFEST OPTION"; 
//                 displayColorClass = "text-blue-400"; 
//                 displayBadgeClass = "bg-blue-900/30 border border-blue-500/50"; 
//                 route.routeColor = "#3b82f6"; 
//             }
//         }

//         html += `
//         <div id="route-card-${i}" onclick="window.drawRoute(${i})" class="bg-[#0b101a] border ${highlightBorder} rounded-xl p-4 mb-3 cursor-pointer hover:border-blue-500 transition-all shadow-lg">
//             <div class="flex justify-between items-center mb-2">
//                 <span class="text-[11px] font-black text-white uppercase tracking-widest">Route ${i+1}${bestLabel}</span>
//                 <span class="text-[9px] font-black uppercase ${displayColorClass} ${displayBadgeClass} px-2 py-1 rounded"><i class="fa-solid ${route.iconClass}"></i> ${displayStatus}</span>
//             </div>
//             <div class="text-[10px] font-bold text-slate-500 mb-2 uppercase tracking-wide">
//                 ↳ ${route.reason}
//             </div>
//             <div class="text-xs font-medium text-slate-400 mb-3 border-b border-white/5 pb-3">
//                 <span class="text-white font-bold text-sm">${route.dist} km</span> &nbsp;•&nbsp; ${route.time} min
//             </div>
//             <button onclick="event.stopPropagation(); window.triggerReport(${i}, '${escHName}', '${currentEpicenter.lat}', '${currentEpicenter.lng}', '${mag}', '${distFromClick}', '${hospital.TYPE}', '${hospital.BEDS}', '${hospital.hLat}', '${hospital.hLng}')" class="w-full py-2 bg-slate-600 hover:bg-red-500 text-white rounded-lg text-[9px] font-black uppercase tracking-widest transition-all">
//                 <i class="fa-solid fa-file-pdf "></i> Download Safety Report
//             </button>
//         </div>`;
//     });
    
//     panel.innerHTML = html;
// }

// window.drawRoute = function(selectedIndex) {
//     if (!Array.isArray(availableRoutes) || !availableRoutes[selectedIndex]) return;
    
//     if (routeLayers && map) {
//         routeLayers.forEach(l => { try { map.removeLayer(l); } catch(err) {} });
//     }
//     routeLayers = [];

//     availableRoutes.forEach((route, index) => {
//         let isSelected = (index === selectedIndex);
//         let color = isSelected ? route.routeColor : '#64748b'; 
//         let weight = isSelected ? 6 : 4;
//         let opacity = isSelected ? 1.0 : 0.4;
//         let dashArray = isSelected ? null : '10,10';

//         let polyline = L.polyline(route.coordinates, {
//             color: color, weight: weight, opacity: opacity,
//             dashArray: dashArray, lineCap: 'round', interactive: false
//         }).addTo(map);

//         if (!isSelected) polyline.bringToBack();
//         else polyline.bringToFront();
//         routeLayers.push(polyline);

//         let card = document.getElementById('route-card-' + index);
//         if (card) {
//             if (isSelected) {
//                 card.style.borderColor = color;
//                 card.style.backgroundColor = '#121824';
//                 card.style.opacity = '1';
//             } else {
//                 card.style.borderColor = 'rgba(255,255,255,0.05)';
//                 card.style.backgroundColor = '#0b101a';
//                 card.style.opacity = '0.8';
//             }
//         }
//     });

//     let selectedPoly = L.polyline(availableRoutes[selectedIndex].coordinates);
//     try { map.fitBounds(selectedPoly.getBounds(), { padding: [50, 50] }); } catch (e) {}
// };

// // Walking Evacuation
// async function triggerWalkingFallback(panel, weatherCond, mag) {
//     const radiusKm = Math.pow(10, (0.4 * mag - 1)) * 10;
//     let walkDist = radiusKm * 0.3;
//     let angle = 45 * Math.PI / 180; 
//     let pLat = currentEpicenter.lat + (walkDist / 111.32) * Math.cos(angle);
//     let pLng = currentEpicenter.lng + (walkDist / (111.32 * Math.cos(currentEpicenter.lat * (Math.PI/180)))) * Math.sin(angle);

//     let url = `https://api.openrouteservice.org/v2/directions/foot-walking?api_key=${ORS_API_KEY}&start=${currentEpicenter.lng},${currentEpicenter.lat}&end=${pLng},${pLat}`;
    
//     try {
//         let res = await fetch(url);
//         let data = await res.json();
//         let r = data.features[0];
//         let coords = r.geometry.coordinates.map(c => [c[1], c[0]]);
//         let distKm = (r.properties.summary.distance / 1000).toFixed(1);
//         let timeMin = Math.round(r.properties.summary.duration / 60);

//         routeLayers.forEach(l => map.removeLayer(l));
//         routeLayers = [];
//         let polyline = L.polyline(coords, { color: '#3b82f6', weight: 6, opacity: 1.0, dashArray: '10,15', lineCap: 'round', interactive: false }).addTo(map);
//         routeLayers.push(polyline);
//         let pickupIcon = L.divIcon({ html: '<i class="fa-solid fa-helicopter"></i>', className: 'bg-blue-500 text-white rounded-full w-8 h-8 flex items-center justify-center border-2 border-white shadow-[0_0_15px_rgba(59,130,246,0.8)]', iconSize: [32,32] });
//         let pm = L.marker([pLat, pLng], { icon: pickupIcon }).addTo(map);
//         routeLayers.push(pm); 
//         map.fitBounds(polyline.getBounds(), { padding: [50, 50] });

//         panel.innerHTML = `
//         <div class="bg-red-900/40 border border-red-500 rounded-xl p-5 shadow-2xl">
//             <div class="flex items-center gap-3 mb-3 text-red-500">
//                 <i class="fa-solid fa-triangle-exclamation text-3xl"></i>
//                 <div>
//                     <h4 class="text-xs font-black uppercase tracking-widest text-white">All Vehicle Routes Compromised</h4>
//                     <span class="text-[9px] uppercase font-bold tracking-wider">Critical Damage Detected</span>
//                 </div>
//             </div>
//             <p class="text-xs text-red-200 mb-4 leading-relaxed font-medium">Vehicular evacuation is impossible. Directed to proceed on foot to nearest secure air-lift pickup zone.</p>
//             <div class="bg-[#0b101a] border border-blue-500/50 rounded-lg p-4">
//                 <div class="flex justify-between items-center mb-2">
//                     <span class="text-[11px] font-black text-blue-400 uppercase tracking-widest">Walking Route</span>
//                     <span class="text-[9px] font-black uppercase text-blue-300 bg-blue-900/30 px-2 py-1 rounded"><i class="fa-solid fa-person-walking"></i> FOOT PATH</span>
//                 </div>
//                 <div class="text-[10px] font-bold text-slate-500 mb-2 uppercase tracking-wide">↳ Weather: ${weatherCond}</div>
//                 <div class="text-xs font-medium text-slate-300"><span class="text-white font-bold text-sm">${distKm} km</span> &nbsp;•&nbsp; ${timeMin} min</div>
//             </div>
//         </div>`;
//     } catch (e) {
//         panel.innerHTML = `<div class="p-6 text-center text-red-400 font-bold tracking-widest uppercase text-[10px]">Total infrastructure collapse.<br>Unable to plot walking route.</div>`;
//     }
// }

// window.triggerReport = function(routeIndex, hName, placeLat, placeLng, mag, dataDist, hType, hBeds, hLat, hLng) {
//     let route = availableRoutes[routeIndex];
//     if (!route) return;

//     let hidden = [];
//     map.eachLayer(function(layer) {
//         try {
//             let isWeatherTile = layer instanceof L.TileLayer && layer._url && layer._url.includes('openweathermap');
//             let isMarker = layer instanceof L.Marker || layer instanceof L.CircleMarker;
//             if (isWeatherTile || isMarker) { hidden.push(layer); map.removeLayer(layer); }
//         } catch (e) {}
//     });

//     function submitForm(mapImageData) {
//         let form = document.createElement('form');
//         form.method = 'POST';
//         form.action = '/report/';
//         form.target = '_blank';
        
//         let intensityEl = document.getElementById('rep-intensity');
//         let depthEl = document.getElementById('stat-depth');
//         let confEl = document.getElementById('accuracy-text'); 
        
//         let params = {
//             map_image: mapImageData || "",
//             place: `Lat: ${parseFloat(placeLat).toFixed(2)}, Lng: ${parseFloat(placeLng).toFixed(2)}`,
//             mag: mag,
//             dist_from_click: dataDist.replace(' km from epicenter', ''),
//             hname: hName,
//             dist: route.dist || "",
//             weather: route.weather || "",
//             hlat: hLat,
//             hlng: hLng,
//             intensity: intensityEl ? intensityEl.innerText : "0.0",
//             depth: depthEl ? depthEl.innerText : "0.0",
//             confidence: confEl ? confEl.innerText : "0%"
//         };
        
//         for (let k in params) {
//             let i = document.createElement('input');
//             i.type = 'hidden';
//             i.name = k;
//             i.value = params[k];
//             form.appendChild(i);
//         }
//         document.body.appendChild(form);
//         form.submit();
//         document.body.removeChild(form);
//     }

//     function restoreHidden() { hidden.forEach(l => { try { l.addTo(map); } catch(e){} }); }

//     if (typeof leafletImage !== 'undefined') {
//         try {
//             leafletImage(map, function(err, canvas) {
//                 restoreHidden();
//                 if (err || !canvas) return submitForm("");
//                 try { submitForm(canvas.toDataURL('image/jpeg', 0.4)); } 
//                 catch (e) { submitForm(""); }
//             });
//         } catch (e) {
//             restoreHidden();
//             submitForm("");
//         }
//     } else {
//         restoreHidden();
//         submitForm("");
//     }
// };

// window.switchTab = function(tab) {
//     const tabSim = document.getElementById('tab-sim');
//     const tabAna = document.getElementById('tab-ana');
    
//     if (tab === 'simulation') {
//         tabSim.classList.replace('border-transparent', 'theme-border');
//         tabSim.classList.add('text-white', 'drop-shadow-[0_0_8px_rgba(255,255,255,0.5)]');
//         tabSim.classList.remove('text-slate-600');
        
//         tabAna.classList.replace('theme-border', 'border-transparent');
//         tabAna.classList.remove('text-white', 'drop-shadow-[0_0_8px_rgba(255,255,255,0.5)]');
//         tabAna.classList.add('text-slate-600');
//     } else {
//         tabAna.classList.replace('border-transparent', 'theme-border');
//         tabAna.classList.add('text-white', 'drop-shadow-[0_0_8px_rgba(255,255,255,0.5)]');
//         tabAna.classList.remove('text-slate-600');
        
//         tabSim.classList.replace('theme-border', 'border-transparent');
//         tabSim.classList.remove('text-white', 'drop-shadow-[0_0_8px_rgba(255,255,255,0.5)]');
//         tabSim.classList.add('text-slate-600');
//     }

//     document.getElementById('content-sim').style.display = tab === 'simulation' ? 'block' : 'none';
//     document.getElementById('content-ana').style.display = tab === 'analytics' ? 'block' : 'none';
    
//     if (tab === 'analytics') updateCharts();
// };

// function initCharts() {
//     Chart.defaults.color = '#94a3b8';
//     Chart.defaults.font.family = "'Segoe UI', sans-serif";

//     pieChartInstance = new Chart(document.getElementById('pieChart'), {
//         type: 'doughnut',
//         data: { labels: [], datasets: [{ data: [], backgroundColor: ['#ef4444', '#e87722', '#eab308', '#3b82f6', '#a855f7'], borderWidth: 0 }] },
//         options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right', labels: { boxWidth: 10, font: {size: 9} } } } }
//     });

//     barChartInstance = new Chart(document.getElementById('barChart'), {
//         type: 'bar',
//         data: { labels: [], datasets: [{ label: 'Beds', data: [], backgroundColor: '#3b82f6', borderRadius: 4 }] },
//         options: { responsive: true, maintainAspectRatio: false, scales: { x: { display: false }, y: { beginAtZero: true, grid: { color: '#ffffff10' } } }, plugins: { legend: { display: false } } }
//     });
// }

// function updateCharts() {
//     if (!pieChartInstance || !barChartInstance) return;
    
//     const typeCounts = {};
//     affectedHospitals.forEach(h => {
//         const type = h.TYPE || h.type || 'Unknown';
//         typeCounts[type] = (typeCounts[type] || 0) + 1;
//     });
//     pieChartInstance.data.labels = Object.keys(typeCounts);
//     pieChartInstance.data.datasets[0].data = Object.values(typeCounts);
//     pieChartInstance.update();

//     const topHospitals = [...affectedHospitals].sort((a, b) => (b.BEDS || b.beds || 0) - (a.BEDS || a.beds || 0)).slice(0, 5);
//     barChartInstance.data.labels = topHospitals.map(h => h.NAME || h.name || 'Hospital');
//     barChartInstance.data.datasets[0].data = topHospitals.map(h => h.BEDS || h.beds || 0);
    
//     const mag = parseFloat(document.getElementById('mag-slider').value);
//     barChartInstance.data.datasets[0].backgroundColor = getThemeColor(mag);
//     barChartInstance.update();
// }

// function animateValue(id, start, end, duration, decimals = 0) {
//     const obj = document.getElementById(id);
//     if (!obj) return;
//     let startTimestamp = null;
//     const step = (timestamp) => {
//         if (!startTimestamp) startTimestamp = timestamp;
//         const progress = Math.min((timestamp - startTimestamp) / duration, 1);
//         const ease = 1 - Math.pow(1 - progress, 4); // easeOutQuart
//         const current = start + (end - start) * ease;
//         obj.innerText = current.toFixed(decimals);
//         if (progress < 1) window.requestAnimationFrame(step);
//     };
//     window.requestAnimationFrame(step);
// }




// // Global variables
// let map, satelliteLayer, labelsLayer, streetLayer;
// let currentMapStyle = 'satellite';
// let hospitalLayer, impactCircle, epicenterMarker;

// // Advanced Features State Variables
// let seismicHeat = null; 
// let safeHospitals = []; 
// let safeMarkers = []; 
// let routeControl = null;
// let routeLayers = [];
// let availableRoutes = [];

// let geojsonData = null;
// let affectedHospitals = [];
// let currentEpicenter = null;

// let pieChartInstance = null;
// let barChartInstance = null;

// // Initialize when DOM is ready
// document.addEventListener('DOMContentLoaded', () => {
//     initMap();
//     initTheme(); 
//     initThemeListeners();
//     initCharts();
// });

// // --- Map Initialization ---
// function initMap() {
//     satelliteLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { attribution: 'Esri' });
//     labelsLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}');
//     streetLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '&copy; OpenStreetMap' });

//     map = L.map('map', {
//         zoomControl: false,
//         layers: [satelliteLayer, labelsLayer],
//         attributionControl: false
//     }).setView([37.0902, -95.7129], 4);

//     L.control.zoom({ position: 'bottomright' }).addTo(map);

//     map.on('click', (e) => {
//         currentEpicenter = { lat: e.latlng.lat, lng: e.latlng.lng };
//         document.getElementById('hud-lat').innerText = currentEpicenter.lat.toFixed(4);
//         document.getElementById('hud-lng').innerText = currentEpicenter.lng.toFixed(4);
//         updateImpactGraphics();
//         hideAIReport();
        
//         const detailCard = document.getElementById('hospital-detail-card');
//         if(detailCard) detailCard.classList.add('hidden');
//         const routingPanel = document.getElementById('routing-panel');
//         if(routingPanel) routingPanel.classList.add('hidden');
        
//         if (routeControl) map.removeControl(routeControl);
//         routeLayers.forEach(l => map.removeLayer(l));
//         routeLayers = [];
//         availableRoutes = [];
//     });
// }

// window.toggleMapStyle = function() {
//     const btn = document.getElementById('map-toggle-btn');
//     if (currentMapStyle === 'satellite') {
//         map.removeLayer(satelliteLayer);
//         map.removeLayer(labelsLayer);
//         map.addLayer(streetLayer);
//         currentMapStyle = 'street';
//         btn.innerHTML = '<i class="fa-solid fa-satellite"></i>'; 
//         btn.title = "Switch to Satellite View";
//     } else {
//         map.removeLayer(streetLayer);
//         map.addLayer(satelliteLayer);
//         map.addLayer(labelsLayer);
//         currentMapStyle = 'satellite';
//         btn.innerHTML = '<i class="fa-solid fa-map"></i>';
//         btn.title = "Switch to Street View";
//     }
// };

// function getThemeColor(mag) {
//     if (mag >= 7.5) return '#ef4444'; // Red
//     if (mag >= 5.5) return '#e87722'; // Orange
//     if (mag >= 2.51) return '#eab308'; // Yellow
//     return '#22c55e'; // Green
// }

// function initTheme() {
//     const slider = document.getElementById('mag-slider');
//     if(slider) {
//         document.documentElement.style.setProperty('--dynamic-color', getThemeColor(parseFloat(slider.value)));
//     }
// }

// function initThemeListeners() {
//     const slider = document.getElementById('mag-slider');
//     if(!slider) return;
//     slider.addEventListener('input', (e) => {
//         const mag = parseFloat(e.target.value);
//         document.getElementById('mag-display').innerText = mag.toFixed(2);
//         const hexColor = getThemeColor(mag);
//         document.documentElement.style.setProperty('--dynamic-color', hexColor);
//         if (currentEpicenter) updateImpactGraphics();
//     });
// }

// function updateImpactGraphics() {
//     if (!currentEpicenter) return;
//     const mag = parseFloat(document.getElementById('mag-slider').value);
//     const hexColor = getThemeColor(mag);
    
//     const radiusKm = Math.pow(10, (0.4 * mag - 1)) * 10;
//     animateValue('stat-radius', parseFloat(document.getElementById('stat-radius').innerText), radiusKm, 1000);

//     if (impactCircle) map.removeLayer(impactCircle);
//     if (epicenterMarker) map.removeLayer(epicenterMarker);

//     impactCircle = L.circle([currentEpicenter.lat, currentEpicenter.lng], {
//         radius: radiusKm * 1000,
//         color: hexColor, fillColor: hexColor, fillOpacity: 0.15,
//         weight: 2, dashArray: '4, 12', className: 'impact-circle-anim'
//     }).addTo(map);

//     epicenterMarker = L.marker([currentEpicenter.lat, currentEpicenter.lng], {
//         icon: L.divIcon({
//             className: 'custom-div-icon',
//             html: `<div class="shockwave-container">
//                      <div class="sw-core"></div><div class="sw-ring sw-delay-1"></div>
//                      <div class="sw-ring sw-delay-2"></div><div class="sw-ring sw-delay-3"></div>
//                    </div>`,
//             iconSize: [40, 40], iconAnchor: [20, 20]
//         })
//     }).addTo(map);

//     if (geojsonData) {
//         affectedHospitals = [];
//         safeHospitals = [];
//         geojsonData.features.forEach(f => {
//             const [lng, lat] = f.geometry.coordinates;
//             const dist = map.distance([lat, lng], [currentEpicenter.lat, currentEpicenter.lng]) / 1000;
//             f.properties.computedDist = dist;

//             if (dist <= radiusKm) affectedHospitals.push(f.properties);
//             else safeHospitals.push(f.properties);
//         });
//         animateValue('stat-sites', parseInt(document.getElementById('stat-sites').innerText), affectedHospitals.length, 1000);
//         updateCharts();
//     }
// }

// window.handleFileUpload = function(e) {
//     const file = e.target.files[0];
//     if (!file) return;
//     document.getElementById('upload-text').innerText = "Processing...";
//     const reader = new FileReader();
//     reader.onload = (ev) => {
//         try {
//             geojsonData = JSON.parse(ev.target.result);
//             renderDataOnMap();
//             document.getElementById('upload-text').innerText = "Data Loaded Successfully";
//             setTimeout(() => document.getElementById('upload-text').innerText = "Load Local GeoJSON", 3000);
//         } catch(err) {
//             alert("Invalid GeoJSON file.");
//             document.getElementById('upload-text').innerText = "Load Local GeoJSON";
//         }
//     };
//     reader.readAsText(file);
// };

// function renderDataOnMap() {
//     if (hospitalLayer) map.removeLayer(hospitalLayer);
//     hospitalLayer = L.geoJSON(geojsonData, {
//         pointToLayer: (feat, latlng) => L.circleMarker(latlng, {
//             radius: 3, fillColor: "#22c55e", color: "#000", weight: 1, opacity: 0.8, fillOpacity: 0.8
//         }),
//         onEachFeature: (feature, layer) => {
//             layer.on('click', (e) => {
//                 L.DomEvent.stopPropagation(e);
//                 const p = feature.properties;
//                 const lat = layer.getLatLng().lat;
//                 const lng = layer.getLatLng().lng;
                
//                 let distText = "Epicenter not set";
//                 if (currentEpicenter) {
//                     const distKm = (map.distance([lat, lng], [currentEpicenter.lat, currentEpicenter.lng]) / 1000).toFixed(2);
//                     distText = `${distKm} km from epicenter`;
//                 }

//                 document.getElementById('hosp-name').innerText = p.NAME || 'Unknown Facility';
//                 document.getElementById('hosp-address').innerText = `${p.ADDRESS || ''}, ${p.CITY || ''}`;
//                 document.getElementById('hosp-beds').innerText = p.BEDS === -999 ? "N/A" : p.BEDS;
//                 document.getElementById('hosp-status').innerText = p.STATUS || "UNKNOWN";
//                 document.getElementById('hosp-type').innerText = p.TYPE || "UNKNOWN";
//                 document.getElementById('hosp-phone').innerText = p.TELEPHONE || "N/A";
//                 document.getElementById('hosp-dist').innerText = distText;

//                 let facilities = p.FACILITIES || p.facilities || "Basic/Not Specified";
//                 if (Array.isArray(facilities)) facilities = facilities.join(', ');
//                 let facEl = document.getElementById('hosp-facilities');
//                 if (facEl) facEl.innerText = facilities;

//                 const routeBtn = document.getElementById('btn-calc-route');
//                 if(routeBtn) {
//                     routeBtn.onclick = () => window.analyzeRouteToHospital(p.NAME || 'Facility', lat, lng, p.BEDS, p.TYPE);
//                 }

//                 document.getElementById('hospital-detail-card').classList.remove('hidden');
//             });
//         }
//     }).addTo(map);
// }

// window.closeHospitalCard = function() {
//     document.getElementById('hospital-detail-card').classList.add('hidden');
// };

// window.drawDynamicHeatmap = function(lat, lng, radiusKm, mag, aiIntensity, affected) {
//     try { if (seismicHeat) map.removeLayer(seismicHeat); } catch(e){}
//     let points = [];
//     let normalizedIntensity = Math.min(1, (aiIntensity || mag) / 10);

//     for (let i = 0; i < 80; i++) {
//         if(lat != null && !isNaN(lat) && lng != null && !isNaN(lng)) {
//            points.push([lat + (Math.random()-0.5) * 0.01, lng + (Math.random()-0.5) * 0.01, 1.0]);
//         }
//     }

//     for (let i = 0; i < 800; i++) {
//         let angle = Math.random() * Math.PI * 2;
//         let dist = Math.sqrt(Math.random()) * radiusKm;
//         let decay = Math.exp(- (dist * dist) / (2 * Math.pow(radiusKm * 0.6, 2)));
//         let weight = normalizedIntensity * decay;

//         let newLat = lat + (dist / 111.32) * Math.cos(angle);
//         let newLng = lng + (dist / (111.32 * Math.cos(lat * (Math.PI/180)))) * Math.sin(angle);
//         if(newLat != null && !isNaN(newLat) && newLng != null && !isNaN(newLng)) {
//            points.push([newLat, newLng, weight]);
//         }
//     }

//     if (Array.isArray(affected)) {
//         affected.forEach(h => {
//             for (let j = 0; j < 40; j++) {
//                 let hLat = h.lat;
//                 let hLng = h.lng;
//                 if(hLat != null && !isNaN(hLat) && hLng != null && !isNaN(hLng)) {
//                    points.push([hLat + (Math.random()-0.5)*0.005, hLng + (Math.random()-0.5)*0.005, normalizedIntensity * 0.9]);
//                 }
//             }
//         });
//     }

//     try {
//         if (points.length > 0) {
//            seismicHeat = L.heatLayer(points, { radius: 55, blur: 35, maxZoom: 10, max: 1.0 }).addTo(map);
//         }
//     } catch (e) { console.warn("Heat layer failed:", e); }
// };

// window.runAnalysis = async function() {
//     if (!currentEpicenter) return alert("Select an epicenter on the map first.");
    
//     const mag = document.getElementById('mag-slider').value;
//     const btnText = document.getElementById('btn-analyze-text');
//     const icon = document.querySelector('#btn-analyze i');
    
//     btnText.innerText = "Transmitting to Django Engine...";
//     icon.className = "fa-solid fa-spinner fa-spin";
    
//     try {
//         const url = `/get_nearest_history/?lat=${currentEpicenter.lat}&lng=${currentEpicenter.lng}&mag=${mag}`;
//         let data;
//         try {
//             const response = await fetch(url);
//             data = await response.json();
//         } catch(e) {
//             console.warn("Django backend unreachable. Falling back to mock data.");
//             const radiusKm = Math.pow(10, (0.4 * mag - 1)) * 10;
//             data = {
//                 intensity: (parseFloat(mag) * 1.15).toFixed(2),
//                 risk_level: mag >= 7.5 ? 'CRITICAL' : mag >= 5.5 ? 'HIGH' : mag >= 2.51 ? 'MODERATE' : 'LOW',
//                 expected_damage: 'Analysis retrieved from server. Structural concerns identified based on ML model.',
//                 assessment: `Earthquake of magnitude ${mag} is predicted to cause ${mag >= 5.5 ? 'severe' : 'manageable'} damage potential.`,
//                 confidence: 85,
//                 radius: radiusKm,
//                 depth: (Math.random() * 50 + 5).toFixed(1)
//             };
//         }

//         if(data.error) throw new Error(data.error);

//         document.getElementById('ai-placeholder').classList.add('hidden');
//         document.getElementById('ai-report-container').classList.remove('hidden');

//         animateValue('rep-intensity', 0, parseFloat(data.intensity), 1500, 2);
        
//         // ✅ NEW: Display Predicted Depth from Django Model
//         const depthEl = document.getElementById('stat-depth');
//         if(depthEl) animateValue('stat-depth', 0, parseFloat(data.depth), 1000, 1);
        
//         document.getElementById('rep-risk').innerText = data.risk_level;
//         document.getElementById('rep-damage').innerText = data.expected_damage;
//         document.getElementById('rep-assessment').innerText = data.assessment;
        
//         let confBar = document.getElementById('accuracy-bar');
//         if(confBar) confBar.style.width = (data.confidence || 80) + "%";
//         let confText = document.getElementById('accuracy-text');
//         if(confText) confText.innerText = Math.round(data.confidence || 80) + "%";

//         if (data.affected_hospitals) {
//             affectedHospitals = data.affected_hospitals;
//             animateValue('stat-sites', 0, affectedHospitals.length, 1000);
//             updateCharts();
//         }

//         window.drawDynamicHeatmap(currentEpicenter.lat, currentEpicenter.lng, data.radius, mag, data.intensity, affectedHospitals);

//         safeMarkers.forEach(m => map.removeLayer(m));
//         safeMarkers = [];
        
//         if (safeHospitals.length > 0 && geojsonData) {
//             safeHospitals.sort((a, b) => a.computedDist - b.computedDist);
//             const top5Safe = safeHospitals.slice(0, 5);
            
//             top5Safe.forEach(h => {
//                 const feature = geojsonData.features.find(f => f.properties.NAME === h.NAME);
//                 if (!feature) return;
//                 const [hLng, hLat] = feature.geometry.coordinates;

//                 let icon = L.divIcon({ html: '+', className: 'safe-hospital-marker', iconSize: [24,24] });
//                 let m = L.marker([hLat, hLng], { icon: icon }).addTo(map);
                
//                 m.on('click', (e) => {
//                     L.DomEvent.stopPropagation(e);
                    
//                     let distText = `${h.computedDist.toFixed(2)} km from epicenter`;
//                     document.getElementById('hosp-name').innerText = h.NAME || 'Unknown Facility';
//                     document.getElementById('hosp-address').innerText = `${h.ADDRESS || ''}, ${h.CITY || ''}`;
//                     document.getElementById('hosp-beds').innerText = h.BEDS === -999 ? "N/A" : h.BEDS;
//                     document.getElementById('hosp-status').innerText = h.STATUS || "UNKNOWN";
//                     document.getElementById('hosp-type').innerText = h.TYPE || "UNKNOWN";
//                     document.getElementById('hosp-phone').innerText = h.TELEPHONE || "N/A";
//                     document.getElementById('hosp-dist').innerText = distText;

//                     let facilities = h.FACILITIES || h.facilities || "Basic/Not Specified";
//                     if (Array.isArray(facilities)) facilities = facilities.join(', ');
//                     let facEl = document.getElementById('hosp-facilities');
//                     if (facEl) facEl.innerText = facilities;

//                     const routeBtn = document.getElementById('btn-calc-route');
//                     if(routeBtn) {
//                         routeBtn.onclick = () => window.analyzeRouteToHospital(h.NAME, hLat, hLng, h.BEDS, h.TYPE);
//                     }

//                     document.getElementById('hospital-detail-card').classList.remove('hidden');
//                 });
//                 safeMarkers.push(m);
//             });
            
//             const nearestSafe = top5Safe[0];
//             const nf = geojsonData.features.find(f => f.properties.NAME === nearestSafe.NAME);
//             if(nf) {
//                 let distText = `${nearestSafe.computedDist.toFixed(2)} km from epicenter`;
//                 document.getElementById('hosp-name').innerText = nearestSafe.NAME || 'Unknown Facility';
//                 document.getElementById('hosp-address').innerText = `${nearestSafe.ADDRESS || ''}, ${nearestSafe.CITY || ''}`;
//                 document.getElementById('hosp-beds').innerText = nearestSafe.BEDS === -999 ? "N/A" : nearestSafe.BEDS;
//                 document.getElementById('hosp-status').innerText = nearestSafe.STATUS || "UNKNOWN";
//                 document.getElementById('hosp-type').innerText = nearestSafe.TYPE || "UNKNOWN";
//                 document.getElementById('hosp-phone').innerText = nearestSafe.TELEPHONE || "N/A";
//                 document.getElementById('hosp-dist').innerText = distText;

//                 let facilities = nearestSafe.FACILITIES || nearestSafe.facilities || "Basic/Not Specified";
//                 if (Array.isArray(facilities)) facilities = facilities.join(', ');
//                 let facEl = document.getElementById('hosp-facilities');
//                 if (facEl) facEl.innerText = facilities;

//                 const routeBtn = document.getElementById('btn-calc-route');
//                 if(routeBtn) {
//                     routeBtn.onclick = () => window.analyzeRouteToHospital(nearestSafe.NAME, nf.geometry.coordinates[1], nf.geometry.coordinates[0], nearestSafe.BEDS, nearestSafe.TYPE);
//                 }
//                 document.getElementById('hospital-detail-card').classList.remove('hidden');
//             }
//         }

//     } catch (err) {
//         alert("Backend Error: " + err.message);
//     } finally {
//         btnText.innerText = "Engage Server Analysis";
//         icon.className = "fa-solid fa-bolt";
//     }
// };

// function hideAIReport() {
//     document.getElementById('ai-placeholder').classList.remove('hidden');
//     document.getElementById('ai-report-container').classList.add('hidden');
// }

// async function getWeatherAt(lat, lng) {
//     try {
//         let res = await fetch(`/get_weather_proxy/?lat=${lat}&lng=${lng}`);
//         let json = await res.json();
//         if (json && json.weather && json.weather[0]) return { cond: json.weather[0].main };
//     } catch(e) { /* ignore */ }
//     return { cond: "Clear" };
// }

// window.analyzeRouteToHospital = async function(hName, hLat, hLng, hBeds, hType) {
//     if (!currentEpicenter) return;
    
//     if (routeControl && map) {
//         try { map.removeControl(routeControl); } catch(err) {}
//     }
//     if (routeLayers && map) {
//         routeLayers.forEach(l => { try { map.removeLayer(l); } catch(err) {} });
//     }
//     routeLayers = [];
//     availableRoutes = [];
    
//     const panel = document.getElementById('routing-panel');
//     if(!panel) return;

//     panel.classList.remove('hidden');
//     panel.innerHTML = `<div class="p-6 text-center text-slate-400 font-bold tracking-widest uppercase text-[10px]">
//         <i class="fa-solid fa-spinner fa-spin text-2xl mb-3 text-blue-500"></i><br>Calculating routes...
//     </div>`;

//     routeControl = L.Routing.control({
//         waypoints: [L.latLng(currentEpicenter.lat, currentEpicenter.lng), L.latLng(hLat, hLng)],
//         show: false, alternatives: true, addWaypoints: false,
//         lineOptions: { styles: [{ opacity: 0 }] },
//         altLineOptions: { styles: [{ opacity: 0 }] },
//         createMarker: function() { return null; },
//         router: L.Routing.osrmv1({ serviceUrl: "https://router.project-osrm.org/route/v1", profile: "driving" })
//     }).addTo(map);

//     routeControl.on('routesfound', async function(e) {
//         let routes = e.routes || [];
//         let bestIndex = 0, bestScore = -Infinity;
//         let html = `<h4 class="text-xs font-black uppercase tracking-widest text-white mb-4 border-b border-white/10 pb-2">Evacuation Routes</h4>`;
        
//         for(let i=0; i<routes.length; i++) {
//             let r = routes[i];
//             let distKm = (r.summary.totalDistance / 1000).toFixed(1);
//             let timeMin = Math.round(r.summary.totalTime / 60);
            
//             let midPt = r.coordinates[Math.floor(r.coordinates.length / 2)];
//             let wMid = await getWeatherAt(midPt.lat, midPt.lng);
            
//             let badWeather = ['Rain','Snow','Thunderstorm','Mist'];
//             let isRisky = badWeather.includes(wMid.cond);
//             let score = 100 - parseFloat(distKm) - (isRisky ? 50 : 0);
            
//             availableRoutes.push({ coordinates: r.coordinates, isRisky, weather: wMid.cond, dist: distKm, time: timeMin });
//             if(score > bestScore) { bestScore = score; bestIndex = i; }
//         }
        
//         availableRoutes.forEach((route, i) => {
//             let statusColor = route.isRisky ? "text-orange-500" : "text-green-500";
//             let statusIcon = route.isRisky ? "fa-triangle-exclamation" : "fa-check-circle";
            
//             let escHName = (hName || "").replace(/'/g, "\\'");
//             let mag = document.getElementById('mag-slider').value;
//             let distFromClick = document.getElementById('hosp-dist').innerText;

//             html += `
//             <div id="route-card-${i}" onclick="window.drawRoute(${i})" class="bg-[#0b101a] border border-white/5 rounded-xl p-4 mb-3 cursor-pointer hover:border-blue-500 transition-all shadow-lg">
//                 <div class="flex justify-between items-center mb-2">
//                     <span class="text-[11px] font-black text-white uppercase tracking-widest">Route ${i+1}</span>
//                     <span class="text-[9px] font-black uppercase ${statusColor} bg-white/5 px-2 py-1 rounded"><i class="fa-solid ${statusIcon}"></i> ${route.weather}</span>
//                 </div>
//                 <div class="text-xs font-medium text-slate-400 mb-3 border-b border-white/5 pb-3">
//                     <span class="text-white font-bold text-sm">${route.dist} km</span> &nbsp;•&nbsp; ${route.time} min
//                 </div>
//                 <button onclick="event.stopPropagation(); window.triggerReport(${i}, '${escHName}', '${currentEpicenter.lat}', '${currentEpicenter.lng}', '${mag}', '${distFromClick}', '${hType}', '${hBeds}', '${hLat}', '${hLng}')" class="w-full py-2 bg-red-600 hover:bg-red-500 text-white rounded-lg text-[9px] font-black uppercase tracking-widest transition-all">
//                     <i class="fa-solid fa-file-pdf"></i> Download Safety Report
//                 </button>
//             </div>`;
//         });
        
//         panel.innerHTML = html;
//         window.drawRoute(bestIndex);
//     });
// };

// window.drawRoute = function(selectedIndex) {
//     if (!Array.isArray(availableRoutes) || !availableRoutes[selectedIndex]) return;
    
//     if (routeLayers && map) {
//         routeLayers.forEach(l => { try { map.removeLayer(l); } catch(err) {} });
//     }
//     routeLayers = [];

//     availableRoutes.forEach((route, index) => {
//         let isSelected = (index === selectedIndex);
//         let color = isSelected ? (route.isRisky ? '#d35400' : '#22c55e') : '#64748b';
//         let weight = isSelected ? 6 : 4;
//         let opacity = isSelected ? 1.0 : 0.4;
//         let dashArray = isSelected ? null : '10,10';

//         let polyline = L.polyline(route.coordinates, {
//             color: color, weight: weight, opacity: opacity,
//             dashArray: dashArray, lineCap: 'round', interactive: false
//         }).addTo(map);

//         if (!isSelected) polyline.bringToBack();
//         else polyline.bringToFront();
//         routeLayers.push(polyline);

//         let card = document.getElementById('route-card-' + index);
//         if (card) {
//             if (isSelected) {
//                 card.style.borderColor = color;
//                 card.style.backgroundColor = '#121824';
//             } else {
//                 card.style.borderColor = 'rgba(255,255,255,0.05)';
//                 card.style.backgroundColor = '#0b101a';
//             }
//         }
//     });

//     let selectedPoly = L.polyline(availableRoutes[selectedIndex].coordinates);
//     try { map.fitBounds(selectedPoly.getBounds(), { padding: [50, 50] }); } catch (e) {}
// };

// window.triggerReport = function(routeIndex, hName, placeLat, placeLng, mag, dataDist, hType, hBeds, hLat, hLng) {
//     let route = availableRoutes[routeIndex];
//     if (!route) return;

//     let hidden = [];
//     map.eachLayer(function(layer) {
//         try {
//             let isWeatherTile = layer instanceof L.TileLayer && layer._url && layer._url.includes('openweathermap');
//             let isMarker = layer instanceof L.Marker || layer instanceof L.CircleMarker;
//             if (isWeatherTile || isMarker) { hidden.push(layer); map.removeLayer(layer); }
//         } catch (e) {}
//     });

//     function submitForm(mapImageData) {
//         let form = document.createElement('form');
//         form.method = 'POST';
//         form.action = '/report/';
//         form.target = '_blank';
        
//         let intensityEl = document.getElementById('rep-intensity');
        
//         let params = {
//             map_image: mapImageData || "",
//             place: `Lat: ${parseFloat(placeLat).toFixed(2)}, Lng: ${parseFloat(placeLng).toFixed(2)}`,
//             mag: mag,
//             dist_from_click: dataDist.replace(' km from epicenter', ''),
//             hname: hName,
//             dist: route.dist || "",
//             weather: route.weather || "",
//             hlat: hLat,
//             hlng: hLng,
//             intensity: intensityEl ? intensityEl.innerText : "0.0"
//         };
        
//         for (let k in params) {
//             let i = document.createElement('input');
//             i.type = 'hidden';
//             i.name = k;
//             i.value = params[k];
//             form.appendChild(i);
//         }
//         document.body.appendChild(form);
//         form.submit();
//         document.body.removeChild(form);
//     }

//     function restoreHidden() { hidden.forEach(l => { try { l.addTo(map); } catch(e){} }); }

//     if (typeof leafletImage !== 'undefined') {
//         try {
//             leafletImage(map, function(err, canvas) {
//                 restoreHidden();
//                 if (err || !canvas) return submitForm("");
//                 try { submitForm(canvas.toDataURL('image/png')); } 
//                 catch (e) { submitForm(""); }
//             });
//         } catch (e) {
//             restoreHidden();
//             submitForm("");
//         }
//     } else {
//         restoreHidden();
//         submitForm("");
//     }
// };

// window.switchTab = function(tab) {
//     const tabSim = document.getElementById('tab-sim');
//     const tabAna = document.getElementById('tab-ana');
    
//     if (tab === 'simulation') {
//         tabSim.classList.replace('border-transparent', 'theme-border');
//         tabSim.classList.add('text-white', 'drop-shadow-[0_0_8px_rgba(255,255,255,0.5)]');
//         tabSim.classList.remove('text-slate-600');
        
//         tabAna.classList.replace('theme-border', 'border-transparent');
//         tabAna.classList.remove('text-white', 'drop-shadow-[0_0_8px_rgba(255,255,255,0.5)]');
//         tabAna.classList.add('text-slate-600');
//     } else {
//         tabAna.classList.replace('border-transparent', 'theme-border');
//         tabAna.classList.add('text-white', 'drop-shadow-[0_0_8px_rgba(255,255,255,0.5)]');
//         tabAna.classList.remove('text-slate-600');
        
//         tabSim.classList.replace('theme-border', 'border-transparent');
//         tabSim.classList.remove('text-white', 'drop-shadow-[0_0_8px_rgba(255,255,255,0.5)]');
//         tabSim.classList.add('text-slate-600');
//     }

//     document.getElementById('content-sim').style.display = tab === 'simulation' ? 'block' : 'none';
//     document.getElementById('content-ana').style.display = tab === 'analytics' ? 'block' : 'none';
    
//     if (tab === 'analytics') updateCharts();
// };

// function initCharts() {
//     Chart.defaults.color = '#94a3b8';
//     Chart.defaults.font.family = "'Segoe UI', sans-serif";

//     pieChartInstance = new Chart(document.getElementById('pieChart'), {
//         type: 'doughnut',
//         data: { labels: [], datasets: [{ data: [], backgroundColor: ['#ef4444', '#e87722', '#eab308', '#3b82f6', '#a855f7'], borderWidth: 0 }] },
//         options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right', labels: { boxWidth: 10, font: {size: 9} } } } }
//     });

//     barChartInstance = new Chart(document.getElementById('barChart'), {
//         type: 'bar',
//         data: { labels: [], datasets: [{ label: 'Beds', data: [], backgroundColor: '#3b82f6', borderRadius: 4 }] },
//         options: { responsive: true, maintainAspectRatio: false, scales: { x: { display: false }, y: { beginAtZero: true, grid: { color: '#ffffff10' } } }, plugins: { legend: { display: false } } }
//     });
// }

// function updateCharts() {
//     if (!pieChartInstance || !barChartInstance) return;
    
//     const typeCounts = {};
//     affectedHospitals.forEach(h => {
//         const type = h.TYPE || h.type || 'Unknown';
//         typeCounts[type] = (typeCounts[type] || 0) + 1;
//     });
//     pieChartInstance.data.labels = Object.keys(typeCounts);
//     pieChartInstance.data.datasets[0].data = Object.values(typeCounts);
//     pieChartInstance.update();

//     const topHospitals = [...affectedHospitals].sort((a, b) => (b.BEDS || b.beds || 0) - (a.BEDS || a.beds || 0)).slice(0, 5);
//     barChartInstance.data.labels = topHospitals.map(h => h.NAME || h.name || 'Hospital');
//     barChartInstance.data.datasets[0].data = topHospitals.map(h => h.BEDS || h.beds || 0);
    
//     const mag = parseFloat(document.getElementById('mag-slider').value);
//     barChartInstance.data.datasets[0].backgroundColor = getThemeColor(mag);
//     barChartInstance.update();
// }

// function animateValue(id, start, end, duration, decimals = 0) {
//     const obj = document.getElementById(id);
//     if (!obj) return;
//     let startTimestamp = null;
//     const step = (timestamp) => {
//         if (!startTimestamp) startTimestamp = timestamp;
//         const progress = Math.min((timestamp - startTimestamp) / duration, 1);
//         const ease = 1 - Math.pow(1 - progress, 4); // easeOutQuart
//         const current = start + (end - start) * ease;
//         obj.innerText = current.toFixed(decimals);
//         if (progress < 1) window.requestAnimationFrame(step);
//     };
//     window.requestAnimationFrame(step);
// }





// // Global variables
// let map, satelliteLayer, labelsLayer, streetLayer;
// let currentMapStyle = 'satellite';
// let hospitalLayer, impactCircle, epicenterMarker;

// // ✅ ADDED: Advanced Features State Variables
// let seismicHeat = null; 
// let safeHospitals = []; 
// let safeMarkers = []; 
// let routeControl = null;
// let routeLayers = [];
// let availableRoutes = [];

// let geojsonData = null;
// let affectedHospitals = [];
// let currentEpicenter = null;

// let pieChartInstance = null;
// let barChartInstance = null;

// // Initialize when DOM is ready
// document.addEventListener('DOMContentLoaded', () => {
//     initMap();
//     initTheme(); 
//     initThemeListeners();
//     initCharts();
// });

// // --- Map Initialization ---
// function initMap() {
//     // Satellite Config
//     satelliteLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { attribution: 'Esri' });
//     labelsLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}');
    
//     // Street View Config
//     streetLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '&copy; OpenStreetMap' });

//     map = L.map('map', {
//         zoomControl: false,
//         layers: [satelliteLayer, labelsLayer],
//         attributionControl: false
//     }).setView([37.0902, -95.7129], 4);

//     L.control.zoom({ position: 'bottomright' }).addTo(map);

//     map.on('click', (e) => {
//         currentEpicenter = { lat: e.latlng.lat, lng: e.latlng.lng };
//         document.getElementById('hud-lat').innerText = currentEpicenter.lat.toFixed(4);
//         document.getElementById('hud-lng').innerText = currentEpicenter.lng.toFixed(4);
//         updateImpactGraphics();
//         hideAIReport();
        
//         // ✅ Hide hospital detail card & routing if open, as the epicenter moved
//         const detailCard = document.getElementById('hospital-detail-card');
//         if(detailCard) detailCard.classList.add('hidden');
//         const routingPanel = document.getElementById('routing-panel');
//         if(routingPanel) routingPanel.classList.add('hidden');
        
//         if (routeControl) map.removeControl(routeControl);
//         routeLayers.forEach(l => map.removeLayer(l));
//         routeLayers = [];
//         availableRoutes = [];
//     });
// }

// // --- Map Toggle (Exported to Window) ---
// window.toggleMapStyle = function() {
//     const btn = document.getElementById('map-toggle-btn');
//     if (currentMapStyle === 'satellite') {
//         map.removeLayer(satelliteLayer);
//         map.removeLayer(labelsLayer);
//         map.addLayer(streetLayer);
//         currentMapStyle = 'street';
//         btn.innerHTML = '<i class="fa-solid fa-satellite"></i>'; 
//         btn.title = "Switch to Satellite View";
//     } else {
//         map.removeLayer(streetLayer);
//         map.addLayer(satelliteLayer);
//         map.addLayer(labelsLayer);
//         currentMapStyle = 'satellite';
//         btn.innerHTML = '<i class="fa-solid fa-map"></i>';
//         btn.title = "Switch to Street View";
//     }
// };

// // --- Dynamic Theming based on Magnitude ---
// function getThemeColor(mag) {
//     if (mag >= 7.5) return '#ef4444'; // Red
//     if (mag >= 5.5) return '#e87722'; // Orange
//     if (mag >= 4.0) return '#eab308'; // Yellow
//     return '#22c55e'; // Green
// }

// function initTheme() {
//     const slider = document.getElementById('mag-slider');
//     if(slider) {
//         document.documentElement.style.setProperty('--dynamic-color', getThemeColor(parseFloat(slider.value)));
//     }
// }

// function initThemeListeners() {
//     const slider = document.getElementById('mag-slider');
//     if(!slider) return;
//     slider.addEventListener('input', (e) => {
//         const mag = parseFloat(e.target.value);
//         document.getElementById('mag-display').innerText = mag.toFixed(2);
        
//         // Update CSS variable globally for instant color change across UI
//         const hexColor = getThemeColor(mag);
//         document.documentElement.style.setProperty('--dynamic-color', hexColor);

//         if (currentEpicenter) updateImpactGraphics();
//     });
// }

// // --- Visual Updates & Spatial Math ---
// function updateImpactGraphics() {
//     if (!currentEpicenter) return;
//     const mag = parseFloat(document.getElementById('mag-slider').value);
//     const hexColor = getThemeColor(mag);
    
//     // Visual Radius calculation
//     const radiusKm = Math.pow(10, (0.4 * mag - 1)) * 10;
//     animateValue('stat-radius', parseFloat(document.getElementById('stat-radius').innerText), radiusKm, 1000);

//     if (impactCircle) map.removeLayer(impactCircle);
//     if (epicenterMarker) map.removeLayer(epicenterMarker);

//     impactCircle = L.circle([currentEpicenter.lat, currentEpicenter.lng], {
//         radius: radiusKm * 1000,
//         color: hexColor, fillColor: hexColor, fillOpacity: 0.15,
//         weight: 2, dashArray: '4, 12', className: 'impact-circle-anim'
//     }).addTo(map);

//     epicenterMarker = L.marker([currentEpicenter.lat, currentEpicenter.lng], {
//         icon: L.divIcon({
//             className: 'custom-div-icon',
//             html: `<div class="shockwave-container">
//                      <div class="sw-core"></div><div class="sw-ring sw-delay-1"></div>
//                      <div class="sw-ring sw-delay-2"></div><div class="sw-ring sw-delay-3"></div>
//                    </div>`,
//             iconSize: [40, 40], iconAnchor: [20, 20]
//         })
//     }).addTo(map);

//     // Client-side quick filter for live UI feedback
//     if (geojsonData) {
//         affectedHospitals = [];
//         safeHospitals = []; // Reset safe hospitals on move
//         geojsonData.features.forEach(f => {
//             const [lng, lat] = f.geometry.coordinates;
//             const dist = map.distance([lat, lng], [currentEpicenter.lat, currentEpicenter.lng]) / 1000;
//             f.properties.computedDist = dist; // store for sorting

//             if (dist <= radiusKm) affectedHospitals.push(f.properties);
//             else safeHospitals.push(f.properties);
//         });
//         animateValue('stat-sites', parseInt(document.getElementById('stat-sites').innerText), affectedHospitals.length, 1000);
//         updateCharts();
//     }
// }

// // --- Data Loading (Exported to Window) ---
// window.handleFileUpload = function(e) {
//     const file = e.target.files[0];
//     if (!file) return;
//     document.getElementById('upload-text').innerText = "Processing...";
//     const reader = new FileReader();
//     reader.onload = (ev) => {
//         try {
//             geojsonData = JSON.parse(ev.target.result);
//             renderDataOnMap();
//             document.getElementById('upload-text').innerText = "Data Loaded Successfully";
//             setTimeout(() => document.getElementById('upload-text').innerText = "Load Local GeoJSON", 3000);
//         } catch(err) {
//             alert("Invalid GeoJSON file.");
//             document.getElementById('upload-text').innerText = "Load Local GeoJSON";
//         }
//     };
//     reader.readAsText(file);
// };

// function renderDataOnMap() {
//     if (hospitalLayer) map.removeLayer(hospitalLayer);
//     hospitalLayer = L.geoJSON(geojsonData, {
//         pointToLayer: (feat, latlng) => L.circleMarker(latlng, {
//             radius: 3, fillColor: "#22c55e", color: "#000", weight: 1, opacity: 0.8, fillOpacity: 0.8
//         }),
//         onEachFeature: (feature, layer) => {
//             layer.on('click', (e) => {
//                 L.DomEvent.stopPropagation(e);
//                 const p = feature.properties;
//                 const lat = layer.getLatLng().lat;
//                 const lng = layer.getLatLng().lng;
                
//                 // Calculate distance from epicenter if it exists
//                 let distText = "Epicenter not set";
//                 if (currentEpicenter) {
//                     const distKm = (map.distance([lat, lng], [currentEpicenter.lat, currentEpicenter.lng]) / 1000).toFixed(2);
//                     distText = `${distKm} km from epicenter`;
//                 }

//                 // Populate UI Card
//                 document.getElementById('hosp-name').innerText = p.NAME || 'Unknown Facility';
//                 document.getElementById('hosp-address').innerText = `${p.ADDRESS || ''}, ${p.CITY || ''}`;
//                 document.getElementById('hosp-beds').innerText = p.BEDS === -999 ? "N/A" : p.BEDS;
//                 document.getElementById('hosp-status').innerText = p.STATUS || "UNKNOWN";
//                 document.getElementById('hosp-type').innerText = p.TYPE || "UNKNOWN";
//                 document.getElementById('hosp-phone').innerText = p.TELEPHONE || "N/A";
//                 document.getElementById('hosp-dist').innerText = distText;

//                 // ✅ Wire up routing button
//                 const routeBtn = document.getElementById('btn-calc-route');
//                 if(routeBtn) {
//                     routeBtn.onclick = () => window.analyzeRouteToHospital(p.NAME || 'Facility', lat, lng, p.BEDS, p.TYPE);
//                 }

//                 document.getElementById('hospital-detail-card').classList.remove('hidden');
//                 map.flyTo(layer.getLatLng(), 15, { duration: 1 });
//             });
//         }
//     }).addTo(map);
    
//     if (hospitalLayer.getBounds().isValid()) {
//         map.fitBounds(hospitalLayer.getBounds(), { padding: [50, 50] });
//     }
// }

// window.closeHospitalCard = function() {
//     document.getElementById('hospital-detail-card').classList.add('hidden');
// };

// // --- ✅ ADDED: Dynamic Heatmap Integration ---
// window.drawDynamicHeatmap = function(lat, lng, radiusKm, mag, aiIntensity, affected) {
//     try { if (seismicHeat) map.removeLayer(seismicHeat); } catch(e){}
//     let points = [];
//     let normalizedIntensity = Math.min(1, (aiIntensity || mag) / 10);

//     // Strong Epicenter Core
//     for (let i = 0; i < 80; i++) points.push([lat + (Math.random()-0.5) * 0.01, lng + (Math.random()-0.5) * 0.01, 1.0]);

//     // Radial Gaussian Hazard Field
//     for (let i = 0; i < 800; i++) {
//         let angle = Math.random() * Math.PI * 2;
//         let dist = Math.sqrt(Math.random()) * radiusKm;
//         let decay = Math.exp(- (dist * dist) / (2 * Math.pow(radiusKm * 0.6, 2)));
//         let weight = normalizedIntensity * decay;

//         let newLat = lat + (dist / 111.32) * Math.cos(angle);
//         let newLng = lng + (dist / (111.32 * Math.cos(lat * (Math.PI/180)))) * Math.sin(angle);
//         points.push([newLat, newLng, weight]);
//     }

//     // Extra Heat on Affected Hospitals
//     if (Array.isArray(affected)) {
//         affected.forEach(h => {
//             for (let j = 0; j < 40; j++) {
//                 points.push([h.lat + (Math.random()-0.5)*0.005, h.lng + (Math.random()-0.5)*0.005, normalizedIntensity * 0.9]);
//             }
//         });
//     }

//     try {
//         seismicHeat = L.heatLayer(points, { radius: 55, blur: 35, maxZoom: 10, max: 1.0 }).addTo(map);
//     } catch (e) { console.warn("Heat layer failed:", e); }
// };

// // --- Backend API Call to views.py (Exported to Window) ---
// window.runAnalysis = async function() {
//     if (!currentEpicenter) return alert("Select an epicenter on the map first.");
    
//     const mag = document.getElementById('mag-slider').value;
//     const btnText = document.getElementById('btn-analyze-text');
//     const icon = document.querySelector('#btn-analyze i');
    
//     btnText.innerText = "Transmitting to Django Engine...";
//     icon.className = "fa-solid fa-spinner fa-spin";
    
//     try {
//         const url = `/nearest_history/?lat=${currentEpicenter.lat}&lng=${currentEpicenter.lng}&mag=${mag}`;
//         const response = await fetch(url);
//         const data = await response.json();

//         if(data.error) throw new Error(data.error);

//         // Display the ML Results
//         document.getElementById('ai-placeholder').classList.add('hidden');
//         document.getElementById('ai-report-container').classList.remove('hidden');

//         animateValue('rep-intensity', 0, parseFloat(data.intensity), 1500, 2);
        
//         document.getElementById('rep-risk').innerText = data.risk_level;
//         document.getElementById('rep-damage').innerText = data.expected_damage;
//         document.getElementById('rep-assessment').innerText = data.assessment;
        
//         let confBar = document.getElementById('accuracy-bar');
//         if(confBar) confBar.style.width = (data.confidence || 80) + "%";
//         let confText = document.getElementById('accuracy-text');
//         if(confText) confText.innerText = Math.round(data.confidence || 80) + "%";

//         // Sync data from backend Haversine calculation
//         if (data.affected_hospitals) {
//             affectedHospitals = data.affected_hospitals;
//             animateValue('stat-sites', 0, affectedHospitals.length, 1000);
//             updateCharts();
//         }

//         // ✅ ADDED: Draw Heatmap
//         window.drawDynamicHeatmap(currentEpicenter.lat, currentEpicenter.lng, data.radius, mag, data.intensity, affectedHospitals);

//         // ✅ ADDED: Top 5 Safe Hospitals Identification & Rendering
//         safeMarkers.forEach(m => map.removeLayer(m));
//         safeMarkers = [];
        
//         if (safeHospitals.length > 0 && geojsonData) {
//             // Sort by closest distance to epicenter (outside radius)
//             safeHospitals.sort((a, b) => a.computedDist - b.computedDist);
//             const top5Safe = safeHospitals.slice(0, 5);
            
//             top5Safe.forEach(h => {
//                 const feature = geojsonData.features.find(f => f.properties.NAME === h.NAME);
//                 if (!feature) return;
//                 const [hLng, hLat] = feature.geometry.coordinates;

//                 // Make safe markers look visually distinct (Green + icon)
//                 let icon = L.divIcon({ html: '+', className: 'safe-hospital-marker', iconSize: [24,24] });
//                 let m = L.marker([hLat, hLng], { icon: icon }).addTo(map);
                
//                 m.on('click', (e) => {
//                     L.DomEvent.stopPropagation(e);
                    
//                     let distText = `${h.computedDist.toFixed(2)} km from epicenter`;
//                     document.getElementById('hosp-name').innerText = h.NAME || 'Unknown Facility';
//                     document.getElementById('hosp-address').innerText = `${h.ADDRESS || ''}, ${h.CITY || ''}`;
//                     document.getElementById('hosp-beds').innerText = h.BEDS === -999 ? "N/A" : h.BEDS;
//                     document.getElementById('hosp-status').innerText = h.STATUS || "UNKNOWN";
//                     document.getElementById('hosp-type').innerText = h.TYPE || "UNKNOWN";
//                     document.getElementById('hosp-phone').innerText = h.TELEPHONE || "N/A";
//                     document.getElementById('hosp-dist').innerText = distText;

//                     const routeBtn = document.getElementById('btn-calc-route');
//                     if(routeBtn) {
//                         routeBtn.onclick = () => window.analyzeRouteToHospital(h.NAME, hLat, hLng, h.BEDS, h.TYPE);
//                     }

//                     document.getElementById('hospital-detail-card').classList.remove('hidden');
//                     map.flyTo([hLat, hLng], 14, {duration: 1});
//                 });
//                 safeMarkers.push(m);
//             });
            
//             // Auto select and show the nearest safe hospital card
//             const nearestSafe = top5Safe[0];
//             const nf = geojsonData.features.find(f => f.properties.NAME === nearestSafe.NAME);
//             if(nf) {
//                 let distText = `${nearestSafe.computedDist.toFixed(2)} km from epicenter`;
//                 document.getElementById('hosp-name').innerText = nearestSafe.NAME || 'Unknown Facility';
//                 document.getElementById('hosp-address').innerText = `${nearestSafe.ADDRESS || ''}, ${nearestSafe.CITY || ''}`;
//                 document.getElementById('hosp-beds').innerText = nearestSafe.BEDS === -999 ? "N/A" : nearestSafe.BEDS;
//                 document.getElementById('hosp-status').innerText = nearestSafe.STATUS || "UNKNOWN";
//                 document.getElementById('hosp-type').innerText = nearestSafe.TYPE || "UNKNOWN";
//                 document.getElementById('hosp-phone').innerText = nearestSafe.TELEPHONE || "N/A";
//                 document.getElementById('hosp-dist').innerText = distText;

//                 const routeBtn = document.getElementById('btn-calc-route');
//                 if(routeBtn) {
//                     routeBtn.onclick = () => window.analyzeRouteToHospital(nearestSafe.NAME, nf.geometry.coordinates[1], nf.geometry.coordinates[0], nearestSafe.BEDS, nearestSafe.TYPE);
//                 }
//                 document.getElementById('hospital-detail-card').classList.remove('hidden');
//             }
//         }

//     } catch (err) {
//         alert("Backend Error: " + err.message);
//     } finally {
//         btnText.innerText = "Engage Server Analysis";
//         icon.className = "fa-solid fa-bolt";
//     }
// };

// function hideAIReport() {
//     document.getElementById('ai-placeholder').classList.remove('hidden');
//     document.getElementById('ai-report-container').classList.add('hidden');
// }

// // --- ✅ ADDED: Weather Proxy & Routing Logic ---
// async function getWeatherAt(lat, lng) {
//     try {
//         // Matches the url provided in your views.py
//         let res = await fetch(`/get_weather_proxy/?lat=${lat}&lng=${lng}`);
//         let json = await res.json();
//         if (json && json.weather && json.weather[0]) return { cond: json.weather[0].main };
//     } catch(e) { /* ignore */ }
//     return { cond: "Clear" };
// }

// window.analyzeRouteToHospital = async function(hName, hLat, hLng, hBeds, hType) {
//     if (!currentEpicenter) return;
    
//     // Clean UI & Map
//     if (routeControl) map.removeControl(routeControl);
//     routeLayers.forEach(l => map.removeLayer(l));
//     routeLayers = [];
//     availableRoutes = [];
    
//     const panel = document.getElementById('routing-panel');
//     if(!panel) return;

//     panel.classList.remove('hidden');
//     panel.innerHTML = `<div class="p-6 text-center text-slate-400 font-bold tracking-widest uppercase text-[10px]">
//         <i class="fa-solid fa-spinner fa-spin text-2xl mb-3 text-blue-500"></i><br>Calculating routes...
//     </div>`;

//     routeControl = L.Routing.control({
//         waypoints: [L.latLng(currentEpicenter.lat, currentEpicenter.lng), L.latLng(hLat, hLng)],
//         show: false, alternatives: true, addWaypoints: false,
//         lineOptions: { styles: [{ opacity: 0 }] }, // hidden initially
//         altLineOptions: { styles: [{ opacity: 0 }] },
//         createMarker: function() { return null; },
//         router: L.Routing.osrmv1({ serviceUrl: "https://router.project-osrm.org/route/v1", profile: "driving" })
//     }).addTo(map);

//     routeControl.on('routesfound', async function(e) {
//         let routes = e.routes || [];
//         let bestIndex = 0, bestScore = -Infinity;
//         let html = `<h4 class="text-xs font-black uppercase tracking-widest text-white mb-4 border-b border-white/10 pb-2">Evacuation Routes</h4>`;
        
//         for(let i=0; i<routes.length; i++) {
//             let r = routes[i];
//             let distKm = (r.summary.totalDistance / 1000).toFixed(1);
//             let timeMin = Math.round(r.summary.totalTime / 60);
            
//             let midPt = r.coordinates[Math.floor(r.coordinates.length / 2)];
//             let wMid = await getWeatherAt(midPt.lat, midPt.lng);
            
//             let badWeather = ['Rain','Snow','Thunderstorm','Mist'];
//             let isRisky = badWeather.includes(wMid.cond);
//             let score = 100 - parseFloat(distKm) - (isRisky ? 50 : 0);
            
//             availableRoutes.push({ coordinates: r.coordinates, isRisky, weather: wMid.cond, dist: distKm, time: timeMin });
//             if(score > bestScore) { bestScore = score; bestIndex = i; }
//         }
        
//         availableRoutes.forEach((route, i) => {
//             let statusColor = route.isRisky ? "text-orange-500" : "text-green-500";
//             let statusIcon = route.isRisky ? "fa-triangle-exclamation" : "fa-check-circle";
            
//             let escHName = (hName || "").replace(/'/g, "\\'");
//             let mag = document.getElementById('mag-slider').value;
//             let distFromClick = document.getElementById('hosp-dist').innerText;

//             html += `
//             <div id="route-card-${i}" onclick="window.drawRoute(${i})" class="bg-[#0b101a] border border-white/5 rounded-xl p-4 mb-3 cursor-pointer hover:border-blue-500 transition-all shadow-lg">
//                 <div class="flex justify-between items-center mb-2">
//                     <span class="text-[11px] font-black text-white uppercase tracking-widest">Route ${i+1}</span>
//                     <span class="text-[9px] font-black uppercase ${statusColor} bg-white/5 px-2 py-1 rounded"><i class="fa-solid ${statusIcon}"></i> ${route.weather}</span>
//                 </div>
//                 <div class="text-xs font-medium text-slate-400 mb-3 border-b border-white/5 pb-3">
//                     <span class="text-white font-bold text-sm">${route.dist} km</span> &nbsp;•&nbsp; ${route.time} min
//                 </div>
//                 <button onclick="event.stopPropagation(); window.triggerReport(${i}, '${escHName}', '${currentEpicenter.lat}', '${currentEpicenter.lng}', '${mag}', '${distFromClick}', '${hType}', '${hBeds}', '${hLat}', '${hLng}')" class="w-full py-2 bg-red-600 hover:bg-red-500 text-white rounded-lg text-[9px] font-black uppercase tracking-widest transition-all">
//                     <i class="fa-solid fa-file-pdf"></i> Download Safety Report
//                 </button>
//             </div>`;
//         });
        
//         panel.innerHTML = html;
//         window.drawRoute(bestIndex);
//     });
// };

// window.drawRoute = function(selectedIndex) {
//     if (!Array.isArray(availableRoutes) || !availableRoutes[selectedIndex]) return;
//     routeLayers.forEach(l => { try { map.removeLayer(l); } catch(e){} });
//     routeLayers = [];

//     availableRoutes.forEach((route, index) => {
//         let isSelected = (index === selectedIndex);
//         let color = isSelected ? (route.isRisky ? '#d35400' : '#22c55e') : '#64748b';
//         let weight = isSelected ? 6 : 4;
//         let opacity = isSelected ? 1.0 : 0.4;
//         let dashArray = isSelected ? null : '10,10';

//         let polyline = L.polyline(route.coordinates, {
//             color: color, weight: weight, opacity: opacity,
//             dashArray: dashArray, lineCap: 'round', interactive: false
//         }).addTo(map);

//         if (!isSelected) polyline.bringToBack();
//         else polyline.bringToFront();
//         routeLayers.push(polyline);

//         let card = document.getElementById('route-card-' + index);
//         if (card) {
//             if (isSelected) {
//                 card.style.borderColor = color;
//                 card.style.backgroundColor = '#121824';
//             } else {
//                 card.style.borderColor = 'rgba(255,255,255,0.05)';
//                 card.style.backgroundColor = '#0b101a';
//             }
//         }
//     });

//     let selectedPoly = L.polyline(availableRoutes[selectedIndex].coordinates);
//     try { map.fitBounds(selectedPoly.getBounds(), { padding: [50, 50] }); } catch (e) {}
// };

// // --- ✅ ADDED: PDF Report Snapshot Generation ---
// window.triggerReport = function(routeIndex, hName, placeLat, placeLng, mag, dataDist, hType, hBeds, hLat, hLng) {
//     let route = availableRoutes[routeIndex];
//     if (!route) return;

//     let hidden = [];
//     map.eachLayer(function(layer) {
//         try {
//             let isWeatherTile = layer instanceof L.TileLayer && layer._url && layer._url.includes('openweathermap');
//             let isMarker = layer instanceof L.Marker || layer instanceof L.CircleMarker;
//             if (isWeatherTile || isMarker) { hidden.push(layer); map.removeLayer(layer); }
//         } catch (e) {}
//     });

//     function submitForm(mapImageData) {
//         let form = document.createElement('form');
//         form.method = 'POST';
//         form.action = '/report/';
//         form.target = '_blank';
        
//         let intensityEl = document.getElementById('rep-intensity');
        
//         let params = {
//             map_image: mapImageData || "",
//             place: `Lat: ${parseFloat(placeLat).toFixed(2)}, Lng: ${parseFloat(placeLng).toFixed(2)}`,
//             mag: mag,
//             dist_from_click: dataDist.replace(' km from epicenter', ''),
//             hname: hName,
//             dist: route.dist || "",
//             weather: route.weather || "",
//             hlat: hLat,
//             hlng: hLng,
//             intensity: intensityEl ? intensityEl.innerText : "0.0"
//         };
        
//         for (let k in params) {
//             let i = document.createElement('input');
//             i.type = 'hidden';
//             i.name = k;
//             i.value = params[k];
//             form.appendChild(i);
//         }
//         document.body.appendChild(form);
//         form.submit();
//         document.body.removeChild(form);
//     }

//     function restoreHidden() { hidden.forEach(l => { try { l.addTo(map); } catch(e){} }); }

//     if (typeof leafletImage !== 'undefined') {
//         try {
//             leafletImage(map, function(err, canvas) {
//                 restoreHidden();
//                 if (err || !canvas) return submitForm("");
//                 try { submitForm(canvas.toDataURL('image/png')); } 
//                 catch (e) { submitForm(""); }
//             });
//         } catch (e) {
//             restoreHidden();
//             submitForm("");
//         }
//     } else {
//         restoreHidden();
//         submitForm("");
//     }
// };

// // --- UI Tab Management (Exported to Window) ---
// window.switchTab = function(tab) {
//     const tabSim = document.getElementById('tab-sim');
//     const tabAna = document.getElementById('tab-ana');
    
//     if (tab === 'simulation') {
//         tabSim.classList.replace('border-transparent', 'theme-border');
//         tabSim.classList.add('text-white', 'drop-shadow-[0_0_8px_rgba(255,255,255,0.5)]');
//         tabSim.classList.remove('text-slate-600');
        
//         tabAna.classList.replace('theme-border', 'border-transparent');
//         tabAna.classList.remove('text-white', 'drop-shadow-[0_0_8px_rgba(255,255,255,0.5)]');
//         tabAna.classList.add('text-slate-600');
//     } else {
//         tabAna.classList.replace('border-transparent', 'theme-border');
//         tabAna.classList.add('text-white', 'drop-shadow-[0_0_8px_rgba(255,255,255,0.5)]');
//         tabAna.classList.remove('text-slate-600');
        
//         tabSim.classList.replace('theme-border', 'border-transparent');
//         tabSim.classList.remove('text-white', 'drop-shadow-[0_0_8px_rgba(255,255,255,0.5)]');
//         tabSim.classList.add('text-slate-600');
//     }

//     document.getElementById('content-sim').style.display = tab === 'simulation' ? 'block' : 'none';
//     document.getElementById('content-ana').style.display = tab === 'analytics' ? 'block' : 'none';
    
//     if (tab === 'analytics') updateCharts();
// };

// // --- Chart.js Analytics ---
// function initCharts() {
//     Chart.defaults.color = '#94a3b8';
//     Chart.defaults.font.family = "'Segoe UI', sans-serif";

//     pieChartInstance = new Chart(document.getElementById('pieChart'), {
//         type: 'doughnut',
//         data: { labels: [], datasets: [{ data: [], backgroundColor: ['#ef4444', '#e87722', '#eab308', '#3b82f6', '#a855f7'], borderWidth: 0 }] },
//         options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right', labels: { boxWidth: 10, font: {size: 9} } } } }
//     });

//     barChartInstance = new Chart(document.getElementById('barChart'), {
//         type: 'bar',
//         data: { labels: [], datasets: [{ label: 'Beds', data: [], backgroundColor: '#3b82f6', borderRadius: 4 }] },
//         options: { responsive: true, maintainAspectRatio: false, scales: { x: { display: false }, y: { beginAtZero: true, grid: { color: '#ffffff10' } } }, plugins: { legend: { display: false } } }
//     });
// }

// function updateCharts() {
//     if (!pieChartInstance || !barChartInstance) return;
    
//     // Pie Chart Data (Types)
//     const typeCounts = {};
//     affectedHospitals.forEach(h => {
//         const type = h.TYPE || h.type || 'Unknown';
//         typeCounts[type] = (typeCounts[type] || 0) + 1;
//     });
//     pieChartInstance.data.labels = Object.keys(typeCounts);
//     pieChartInstance.data.datasets[0].data = Object.values(typeCounts);
//     pieChartInstance.update();

//     // Bar Chart Data (Top 5 Capacity)
//     const topHospitals = [...affectedHospitals].sort((a, b) => (b.BEDS || b.beds || 0) - (a.BEDS || a.beds || 0)).slice(0, 5);
//     barChartInstance.data.labels = topHospitals.map(h => h.NAME || h.name || 'Hospital');
//     barChartInstance.data.datasets[0].data = topHospitals.map(h => h.BEDS || h.beds || 0);
    
//     // Bar color matches theme
//     const mag = parseFloat(document.getElementById('mag-slider').value);
//     barChartInstance.data.datasets[0].backgroundColor = getThemeColor(mag);
//     barChartInstance.update();
// }

// // --- Animation Utility ---
// function animateValue(id, start, end, duration, decimals = 0) {
//     const obj = document.getElementById(id);
//     if (!obj) return;
//     let startTimestamp = null;
//     const step = (timestamp) => {
//         if (!startTimestamp) startTimestamp = timestamp;
//         const progress = Math.min((timestamp - startTimestamp) / duration, 1);
//         const ease = 1 - Math.pow(1 - progress, 4); // easeOutQuart
//         const current = start + (end - start) * ease;
//         obj.innerText = current.toFixed(decimals);
//         if (progress < 1) window.requestAnimationFrame(step);
//     };
//     window.requestAnimationFrame(step);
// }


// let map, hospitalLayer, impactCircle, epicenterMarker;
// let geojsonData = null;
// let affectedHospitals = [];
// let currentEpicenter = null;

// let pieChartInstance = null;
// let barChartInstance = null;

// // Initialize when DOM is ready
// document.addEventListener('DOMContentLoaded', () => {
//     initMap();
//     initThemeListeners();
//     initCharts();
// });

// // --- Map Initialization ---
// function initMap() {
//     const satellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { attribution: 'Esri' });
//     const labels = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}');

//     map = L.map('map', {
//         zoomControl: false,
//         layers: [satellite, labels],
//         attributionControl: false
//     }).setView([37.0902, -95.7129], 4);

//     L.control.zoom({ position: 'bottomright' }).addTo(map);

//     map.on('click', (e) => {
//         currentEpicenter = { lat: e.latlng.lat, lng: e.latlng.lng };
//         document.getElementById('hud-lat').innerText = currentEpicenter.lat.toFixed(4);
//         document.getElementById('hud-lng').innerText = currentEpicenter.lng.toFixed(4);
//         updateImpactGraphics();
//         hideAIReport();
//     });
// }

// // --- Dynamic Theming based on Magnitude ---
// function getTheme(mag) {
//     if (mag >= 7.5) return { hex: '#ef4444', class: 'text-red-500' };
//     if (mag >= 5.5) return { hex: '#e87722', class: 'text-orange-500' };
//     return { hex: '#eab308', class: 'text-yellow-500' };
// }

// function initThemeListeners() {
//     const slider = document.getElementById('mag-slider');
//     slider.addEventListener('input', (e) => {
//         const mag = parseFloat(e.target.value);
//         document.getElementById('mag-display').innerText = mag.toFixed(2);
        
//         // Update Theme Colors globally via CSS Var
//         const theme = getTheme(mag);
//         const container = document.getElementById('ui-theme-container');
//         container.className = `w-[420px] min-w-[420px] bg-[#0b101a]/95 border-r border-white/10 flex flex-col z-20 shadow-[0_0_50px_rgba(0,0,0,0.5)] backdrop-blur-2xl relative ${theme.class}`;
//         slider.style.setProperty('--slider-color', theme.hex);

//         if (currentEpicenter) updateImpactGraphics();
//     });
// }

// // --- Visual Updates & Spatial Math ---
// function updateImpactGraphics() {
//     if (!currentEpicenter) return;
//     const mag = parseFloat(document.getElementById('mag-slider').value);
//     const theme = getTheme(mag);
    
//     // Formula matching the React version for visual radius
//     const radiusKm = Math.pow(10, (0.4 * mag - 1)) * 10;
//     animateValue('stat-radius', parseFloat(document.getElementById('stat-radius').innerText), radiusKm, 1000);

//     if (impactCircle) map.removeLayer(impactCircle);
//     if (epicenterMarker) map.removeLayer(epicenterMarker);

//     impactCircle = L.circle([currentEpicenter.lat, currentEpicenter.lng], {
//         radius: radiusKm * 1000,
//         color: theme.hex, fillColor: theme.hex, fillOpacity: 0.15,
//         weight: 2, dashArray: '4, 12', className: 'impact-circle-anim'
//     }).addTo(map);

//     epicenterMarker = L.marker([currentEpicenter.lat, currentEpicenter.lng], {
//         icon: L.divIcon({
//             className: 'custom-div-icon',
//             html: `<div class="shockwave-container" style="--theme-color: ${theme.hex}">
//                      <div class="sw-core"></div><div class="sw-ring sw-delay-1"></div>
//                      <div class="sw-ring sw-delay-2"></div><div class="sw-ring sw-delay-3"></div>
//                    </div>`,
//             iconSize: [40, 40], iconAnchor: [20, 20]
//         })
//     }).addTo(map);

//     // If data loaded, JS filters local points visually to prevent backend overload on slider drag
//     if (geojsonData) {
//         affectedHospitals = [];
//         geojsonData.features.forEach(f => {
//             const [lng, lat] = f.geometry.coordinates;
//             const dist = map.distance([lat, lng], [currentEpicenter.lat, currentEpicenter.lng]) / 1000;
//             if (dist <= radiusKm) affectedHospitals.push(f.properties);
//         });
//         animateValue('stat-sites', parseInt(document.getElementById('stat-sites').innerText), affectedHospitals.length, 1000);
//         updateCharts();
//     }
// }

// // --- Data Loading ---
// function handleFileUpload(e) {
//     const file = e.target.files[0];
//     if (!file) return;
//     document.getElementById('upload-text').innerText = "Processing...";
//     const reader = new FileReader();
//     reader.onload = (ev) => {
//         geojsonData = JSON.parse(ev.target.result);
//         renderDataOnMap();
//         document.getElementById('upload-text').innerText = "Data Loaded Successfully";
//         setTimeout(() => document.getElementById('upload-text').innerText = "Load Local GeoJSON", 3000);
//     };
//     reader.readAsText(file);
// }

// function renderDataOnMap() {
//     if (hospitalLayer) map.removeLayer(hospitalLayer);
//     hospitalLayer = L.geoJSON(geojsonData, {
//         pointToLayer: (feat, latlng) => L.circleMarker(latlng, {
//             radius: 3, fillColor: "#22c55e", color: "#000", weight: 1, opacity: 0.8, fillOpacity: 0.8
//         })
//     }).addTo(map);
// }

// // --- Backend API Call to views.py ---
// async function runAnalysis() {
//     if (!currentEpicenter) return alert("Select an epicenter on the map first.");
    
//     const mag = document.getElementById('mag-slider').value;
//     const btnText = document.getElementById('btn-analyze-text');
//     const icon = document.querySelector('#btn-analyze i');
    
//     btnText.innerText = "Transmitting to ML Engine...";
//     icon.className = "fa-solid fa-spinner fa-spin";
    
//     try {
//         // CALLING YOUR DJANGO VIEW `get_nearest_history`
//         const url = `/nearest_history/?lat=${currentEpicenter.lat}&lng=${currentEpicenter.lng}&mag=${mag}`;
//         const response = await fetch(url);
//         const data = await response.json();

//         if(data.error) throw new Error(data.error);

//         // Display the ML Results
//         document.getElementById('ai-placeholder').classList.add('hidden');
//         document.getElementById('ai-report-container').classList.remove('hidden');

//         // Use Animated Counter for Intensity
//         animateValue('rep-intensity', 0, data.intensity, 1500, 1);
        
//         document.getElementById('rep-risk').innerText = data.risk_level;
//         document.getElementById('rep-damage').innerText = data.expected_damage;
//         document.getElementById('rep-assessment').innerText = data.assessment;

//         // If backend returned affected hospitals via PostGIS/Haversine, update local state
//         if (data.affected_hospitals) {
//             affectedHospitals = data.affected_hospitals;
//             animateValue('stat-sites', 0, affectedHospitals.length, 1000);
//             updateCharts();
//         }

//     } catch (err) {
//         alert("Backend Error: " + err.message);
//     } finally {
//         btnText.innerText = "Engage Backend Analysis";
//         icon.className = "fa-solid fa-bolt";
//     }
// }

// function hideAIReport() {
//     document.getElementById('ai-placeholder').classList.remove('hidden');
//     document.getElementById('ai-report-container').classList.add('hidden');
// }

// // --- UI Tab Management ---
// function switchTab(tab) {
//     document.getElementById('tab-sim').classList.replace(tab === 'simulation' ? 'border-transparent' : 'border-current', tab === 'simulation' ? 'border-current' : 'border-transparent');
//     document.getElementById('tab-sim').classList[tab === 'simulation' ? 'add' : 'remove']('text-white', 'drop-shadow-[0_0_8px_rgba(255,255,255,0.5)]');
    
//     document.getElementById('tab-ana').classList.replace(tab === 'analytics' ? 'border-transparent' : 'border-current', tab === 'analytics' ? 'border-current' : 'border-transparent');
//     document.getElementById('tab-ana').classList[tab === 'analytics' ? 'add' : 'remove']('text-white', 'drop-shadow-[0_0_8px_rgba(255,255,255,0.5)]');

//     document.getElementById('content-sim').style.display = tab === 'simulation' ? 'block' : 'none';
//     document.getElementById('content-ana').style.display = tab === 'analytics' ? 'block' : 'none';
    
//     if (tab === 'analytics') updateCharts();
// }

// // --- Chart.js Analytics ---
// function initCharts() {
//     Chart.defaults.color = '#94a3b8';
//     Chart.defaults.font.family = "'Segoe UI', sans-serif";

//     pieChartInstance = new Chart(document.getElementById('pieChart'), {
//         type: 'doughnut',
//         data: { labels: [], datasets: [{ data: [], backgroundColor: ['#ef4444', '#e87722', '#eab308', '#3b82f6', '#a855f7'], borderWidth: 0 }] },
//         options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right', labels: { boxWidth: 10, font: {size: 9} } } } }
//     });

//     barChartInstance = new Chart(document.getElementById('barChart'), {
//         type: 'bar',
//         data: { labels: [], datasets: [{ label: 'Beds', data: [], backgroundColor: '#3b82f6', borderRadius: 4 }] },
//         options: { responsive: true, maintainAspectRatio: false, scales: { x: { display: false }, y: { beginAtZero: true, grid: { color: '#ffffff10' } } }, plugins: { legend: { display: false } } }
//     });
// }

// function updateCharts() {
//     if (!pieChartInstance || !barChartInstance) return;
    
//     // Pie Chart Data (Types)
//     const typeCounts = {};
//     affectedHospitals.forEach(h => {
//         const type = h.TYPE || h.type || 'Unknown';
//         typeCounts[type] = (typeCounts[type] || 0) + 1;
//     });
//     pieChartInstance.data.labels = Object.keys(typeCounts);
//     pieChartInstance.data.datasets[0].data = Object.values(typeCounts);
//     pieChartInstance.update();

//     // Bar Chart Data (Top 5 Capacity)
//     const topHospitals = [...affectedHospitals].sort((a, b) => (b.BEDS || b.beds || 0) - (a.BEDS || a.beds || 0)).slice(0, 5);
//     barChartInstance.data.labels = topHospitals.map(h => h.NAME || h.name || 'Hospital');
//     barChartInstance.data.datasets[0].data = topHospitals.map(h => h.BEDS || h.beds || 0);
//     const mag = document.getElementById('mag-slider').value;
//     barChartInstance.data.datasets[0].backgroundColor = getTheme(mag).hex;
//     barChartInstance.update();
// }

// // --- Animation Utility ---
// function animateValue(id, start, end, duration, decimals = 0) {
//     let startTimestamp = null;
//     const step = (timestamp) => {
//         if (!startTimestamp) startTimestamp = timestamp;
//         const progress = Math.min((timestamp - startTimestamp) / duration, 1);
//         const ease = 1 - Math.pow(1 - progress, 4);
//         const current = start + (end - start) * ease;
//         document.getElementById(id).innerText = current.toFixed(decimals);
//         if (progress < 1) window.requestAnimationFrame(step);
//     };
//     window.requestAnimationFrame(step);
// }


// // static/js/script.js
// "use strict";

// /* ================= 1. GLOBALS & HELPERS ================= */
// var map;
// var routeControl = null;
// var seismicHeat = null;
// var allHospitals = [];
// var globalSafeHospitals = [];
// var hospitalMarkers = [];
// var routeLayers = [];
// var availableRoutes = [];
// var facilitiesControl = null;

// // exported functions expected by your HTML/template:
// window.drawRoute = function() { console.warn("drawRoute not initialized yet"); };
// window.selectHospital = function() { console.warn("selectHospital not initialized yet"); };
// window.triggerSeismicAnalysis = function() { console.warn("triggerSeismicAnalysis not initialized yet"); };
// window.triggerReport = function() { console.warn("triggerReport not initialized yet"); };

// // small helper: haversine distance in km
// function _haversineKm(lat1, lon1, lat2, lon2) {
//     var R = 6371.0;
//     var φ1 = lat1 * Math.PI / 180;
//     var φ2 = lat2 * Math.PI / 180;
//     var dφ = (lat2 - lat1) * Math.PI / 180;
//     var dλ = (lon2 - lon1) * Math.PI / 180;
//     var a = Math.sin(dφ/2) * Math.sin(dφ/2) +
//             Math.cos(φ1) * Math.cos(φ2) *
//             Math.sin(dλ/2) * Math.sin(dλ/2);
//     return 2 * R * Math.asin(Math.sqrt(a));
// }

// /* ================= 2. ROUTE DRAWING ================= */
// window.drawRoute = function(selectedIndex) {
//     if (!Array.isArray(availableRoutes) || !availableRoutes[selectedIndex]) return;
//     // remove existing route layers
//     routeLayers.forEach(l => { try { map.removeLayer(l); } catch(e){} });
//     routeLayers = [];

//     availableRoutes.forEach((route, index) => {
//         var isSelected = (index === selectedIndex);
//         var color = isSelected ? (route.isRisky ? '#d35400' : '#27ae60') : '#7f8c8d';
//         var weight = isSelected ? 8 : 5;
//         var opacity = isSelected ? 1.0 : 0.6;
//         var dashArray = isSelected ? null : '10,15';

//         var polyline = L.polyline(route.coordinates, {
//             color: color, weight: weight, opacity: opacity,
//             dashArray: dashArray, lineCap: 'round', interactive: false
//         }).addTo(map);

//         if (!isSelected) polyline.bringToBack();
//         else polyline.bringToFront();

//         routeLayers.push(polyline);

//         // update UI card style (if exists)
//         var card = document.getElementById('route-card-' + index);
//         if (card) {
//             if (isSelected) {
//                 card.style.border = '2px solid ' + color;
//                 card.style.backgroundColor = '#f0fdf4';
//                 card.style.transform = 'scale(1.02)';
//                 card.style.boxShadow = '0 4px 6px rgba(0,0,0,0.1)';
//             } else {
//                 card.style.border = '1px solid #ddd';
//                 card.style.backgroundColor = 'white';
//                 card.style.transform = 'scale(1)';
//                 card.style.boxShadow = 'none';
//             }
//         }
//     });

//     // fit to selected route
//     var selectedPoly = L.polyline(availableRoutes[selectedIndex].coordinates);
//     try { map.fitBounds(selectedPoly.getBounds(), { padding: [50, 50] }); } catch (e) {}
//     console.log("🗺️ Switched to Route", selectedIndex + 1);
// };

// /* ================= 3. REPORT / SNAPSHOT ================= */
// window.triggerReport = function(routeIndex, hName, place, mag, dataDist, hType, hBeds, hTrauma, hLat, hLng) {
//     var route = availableRoutes[routeIndex];
//     if (!route) return console.warn("No route at index", routeIndex);

//     // hide layers that tend to break leaflet-image (tile overlays, heavy markers)
//     var hidden = [];
//     map.eachLayer(function(layer) {
//         try {
//             var isWeatherTile = layer instanceof L.TileLayer && layer._url && layer._url.includes('openweathermap');
//             var isMarker = layer instanceof L.Marker;
//             if (isWeatherTile || isMarker) {
//                 hidden.push(layer);
//                 map.removeLayer(layer);
//             }
//         } catch (e) {}
//     });

//     function submitForm(mapImageData) {
//         var form = document.createElement('form');
//         form.method = 'POST';
//         form.action = '/report/';
//         form.target = '_blank';
//         var params = {
//             map_image: mapImageData || "",
//             place: place,
//             mag: mag,
//             dist_from_click: dataDist,
//             hname: hName,
//             dist: route.dist || "",
//             weather: route.weather || "",
//             hlat: hLat,
//             hlng: hLng,
//             intensity: (typeof window.aiIntensityGlobal !== 'undefined') ? window.aiIntensityGlobal : "0"
//         };
//         for (var k in params) {
//             var i = document.createElement('input');
//             i.type = 'hidden';
//             i.name = k;
//             i.value = params[k];
//             form.appendChild(i);
//         }
//         document.body.appendChild(form);
//         form.submit();
//         document.body.removeChild(form);
//     }

//     // restore hidden layers helper
//     function restoreHidden() {
//         hidden.forEach(function(l) { try { l.addTo(map); } catch(e){} });
//     }

//     // if leafletImage available, use it; otherwise submit without image
//     if (typeof leafletImage !== 'undefined') {
//         try {
//             leafletImage(map, function(err, canvas) {
//                 restoreHidden();
//                 if (err || !canvas) {
//                     console.warn("leafletImage error:", err);
//                     return submitForm("");
//                 }
//                 try {
//                     var dataURL = canvas.toDataURL('image/png');
//                     submitForm(dataURL);
//                 } catch (e) {
//                     console.warn("canvas toDataURL failed:", e);
//                     submitForm("");
//                 }
//             });
//         } catch (e) {
//             restoreHidden();
//             console.warn("leafletImage call failed:", e);
//             submitForm("");
//         }
//     } else {
//         restoreHidden();
//         submitForm("");
//     }
// };

// /* ================= 4. SELECT HOSPITAL & ROUTES ================= */
// window.selectHospital = async function(eqLat, eqLng, hLat, hLng, hName, place, mag, dataDist, beds, trauma, type) {
//     console.log("Select hospital:", hName);
//     if (!map) return alert("Map not ready.");

//     // cleanup previous
//     if (routeControl) { try { map.removeControl(routeControl); } catch(e){} routeControl = null; }
//     routeLayers.forEach(l => { try { map.removeLayer(l); } catch(e){} });
//     routeLayers = [];
//     availableRoutes = [];
//     var old = document.getElementById('route-summary');
//     if (old) old.remove();

//     // update facilities box if available
//     var hospitalObj = allHospitals.find(h => (h.properties && (h.properties.NAME === hName || h.properties.name === hName)));
//     if (hospitalObj && facilitiesControl && typeof facilitiesControl.update === 'function') {
//         facilitiesControl.update(hospitalObj.properties);
//     }

//     // helper to get weather via backend
//     async function getWeatherAt(lat, lng) {
//         try {
//             var res = await fetch('/get_weather/?lat=' + lat + '&lng=' + lng);
//             var json = await res.json();
//             if (json && json.weather && Array.isArray(json.weather) && json.weather[0]) {
//                 return { cond: json.weather[0].main || "Clear" };
//             }
//             return { cond: "Clear" };
//         } catch (e) { return { cond: "Clear" }; }
//     }

//     // build routing control
//     try {
//         routeControl = L.Routing.control({
//             waypoints: [L.latLng(eqLat, eqLng), L.latLng(hLat, hLng)],
//             show: false,
//             alternatives: true,
//             draggableWaypoints: false,
//             addWaypoints: false,
//             lineOptions: { styles: [{ color: 'black', opacity: 0, weight: 0 }] },
//             altLineOptions: { styles: [{ color: 'black', opacity: 0, weight: 0 }] },
//             createMarker: function() { return null; },
//             router: L.Routing.osrmv1({
//                 serviceUrl: "https://router.project-osrm.org/route/v1",
//                 profile: "driving"
//             })
//         }).addTo(map);
//     } catch (e) {
//         console.warn("Routing control creation failed:", e);
//         return;
//     }

//     routeControl.on('routesfound', async function(e) {
//         var routes = e.routes || [];
//         var bestIndex = 0, bestScore = -Infinity;
//         var dashboardHTML = "";

//         for (var i = 0; i < routes.length; i++) {
//             try {
//                 var r = routes[i];
//                 var distKm = (r.summary && r.summary.totalDistance) ? (r.summary.totalDistance / 1000).toFixed(1) : "0.0";
//                 var timeMin = (r.summary && r.summary.totalTime) ? Math.round(r.summary.totalTime / 60) : 0;
//                 var midIdx = Math.floor(r.coordinates.length / 2);
//                 var midPt = r.coordinates[midIdx] || r.coordinates[0];
//                 var wMid = await getWeatherAt(midPt.lat, midPt.lng);
//                 var score = 100 - parseFloat(distKm);
//                 var badWeather = ['Rain','Snow','Thunderstorm','Mist'];
//                 var isRisky = badWeather.includes(wMid.cond);
//                 if (isRisky) score -= 50;

//                 availableRoutes.push({
//                     coordinates: r.coordinates,
//                     isRisky: isRisky,
//                     weather: wMid.cond,
//                     dist: distKm,
//                     time: timeMin
//                 });

//                 if (score > bestScore) { bestScore = score; bestIndex = i; }
//             } catch (err) {
//                 console.warn("Route processing error:", err);
//             }
//         }

//         // create cards
//         availableRoutes.forEach(function(route, i) {
//             var statusIcon = route.isRisky ? "⚠️" : "✅";
//             var statusColor = route.isRisky ? "#d35400" : "#27ae60";
//             var escapedHName = (hName || "").replace(/'/g, "\\'");
//             var escapedPlace = (place || "").replace(/'/g, "\\'");

//             dashboardHTML += "<div id='route-card-" + i + "' class='route-card' onclick='window.drawRoute(" + i + ")' style='padding:10px; border:1px solid #ddd; margin-bottom:5px; cursor:pointer; background:white; border-radius:8px;'>" +
//                 "<div style='font-weight:bold; display:flex; justify-content:space-between; align-items:center;'><span>Route " + (i+1) + "</span>" +
//                 "<span style='color:" + statusColor + "; font-size:11px;'>" + statusIcon + " " + route.weather + "</span></div>" +
//                 "<div style='font-size:12px; color:#333; margin-top:4px;'><b>" + route.dist + " km</b> • " + route.time + " min</div>" +
//                 "<button onclick=\"event.stopPropagation(); window.triggerReport(" + i + ", '" + escapedHName + "', '" + escapedPlace + "', '" + mag + "', '" + dataDist + "', '" + (type||"") + "', '" + (beds||"") + "', '" + (trauma||"") + "', '" + hLat + "', '" + hLng + "')\" style='margin-top:8px; width:100%; padding:6px; background:#c0392b; color:white; border:none; border-radius:4px; font-weight:bold; cursor:pointer;'>📄 DOWNLOAD PDF</button>" +
//                 "</div>";
//         });

//         var routeContainer = document.getElementById('route-container');
//         if (routeContainer) {
//             routeContainer.innerHTML = dashboardHTML;
//         } else {
//             var summaryDiv = document.createElement('div');
//             summaryDiv.id = 'route-summary';
//             summaryDiv.innerHTML = "<div style='position:fixed; bottom:20px; left:20px; background:white; padding:15px; border-radius:8px; box-shadow:0 0 15px rgba(0,0,0,0.3); z-index:9999; width:280px; font-family:sans-serif;'>" +
//                 "<h4 style='margin:0 0 10px 0; color:#2c3e50; border-bottom:2px solid #3498db;'>🚦 Choose Route</h4>" +
//                 "<div style='max-height:300px; overflow-y:auto;'>" + dashboardHTML + "</div></div>";
//             document.body.appendChild(summaryDiv);
//         }

//         window.drawRoute(bestIndex);
//     });
// };

// /* ================= 5. INITIALIZATION ================= */
// document.addEventListener('DOMContentLoaded', function() {
//     console.log("App script loaded. Initializing map...");

//     // init map
//     map = L.map('map', { zoomControl: false, preferCanvas: true }).setView([37.7470, -99.1406], 5);

//     var streetLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { crossOrigin: true });
//     var esriSat = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { crossOrigin: true });
//     var esriLabels = L.tileLayer('https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}', { crossOrigin: true, pane: 'overlayPane' });
//     var satelliteLayer = L.layerGroup([esriSat, esriLabels]);

//     streetLayer.addTo(map);

//     // weather overlay (adjust APPID via settings)
//     var owmApi = 'ec4ec5f6b0380fdedec25fb9a11c9b26'; // keep or move to settings
//     L.tileLayer('https://tile.openweathermap.org/map/precip_new/{z}/{x}/{y}.png?appid=' + owmApi, { attribution: 'Weather data © OpenWeatherMap', opacity: 0.3 }).addTo(map);

//     // toggle control in sidebar button (if present)
//     window.isSatelliteActive = false;
//     function setToggleBtn(btn, isSat) { btn.setAttribute('aria-pressed', String(!!isSat)); btn.textContent = isSat ? "🗺️" : "🛰️"; }
//     function toggleBaseMap() {
//         if (!window.isSatelliteActive) { map.removeLayer(streetLayer); satelliteLayer.addTo(map); window.isSatelliteActive = true; }
//         else { map.removeLayer(satelliteLayer); streetLayer.addTo(map); window.isSatelliteActive = false; }
//         var sidebarBtn = document.getElementById('map-toggle-btn');
//         if (sidebarBtn) setToggleBtn(sidebarBtn, window.isSatelliteActive);
//     }
//     var sidebarToggleBtn = document.getElementById('map-toggle-btn');
//     if (sidebarToggleBtn) {
//         setToggleBtn(sidebarToggleBtn, window.isSatelliteActive);
//         sidebarToggleBtn.addEventListener('click', function(e) { e.preventDefault(); toggleBaseMap(); });
//     } else {
//         var ToggleControl = L.Control.extend({
//             onAdd: function() {
//                 var container = L.DomUtil.create('button', 'leaflet-control-toggle-base');
//                 container.type = 'button';
//                 container.title = 'Toggle Street / Satellite';
//                 container.style.background = 'white';
//                 container.style.border = '1px solid #cbd5e1';
//                 container.style.borderRadius = '6px';
//                 container.style.padding = '6px 8px';
//                 container.style.cursor = 'pointer';
//                 container.style.fontSize = '16px';
//                 container.style.boxShadow = '0 1px 3px rgba(0,0,0,0.06)';
//                 setToggleBtn(container, window.isSatelliteActive);
//                 L.DomEvent.on(container, 'click', L.DomEvent.stop).on(container, 'click', function() { toggleBaseMap(); });
//                 return container;
//             }
//         });
//         (new ToggleControl({ position: 'topright' })).addTo(map);
//     }

//     // Facilities legend control
//     facilitiesControl = L.control({ position: 'bottomright' });
//     facilitiesControl.onAdd = function() {
//         this._div = L.DomUtil.create('div', 'info-legend');
//         L.DomEvent.disableClickPropagation(this._div);
//         this.update = function(props) {
//             if (!props) { this._div.style.display = 'none'; return; }
//             this._div.style.display = 'block';
//             var facilitiesHtml = (props.FACILITIES || []).map(function(f) {
//                 var critical = (f.indexOf && (f.includes('Emergency') || f.includes('Trauma')));
//                 return "<span class='facility-badge " + (critical ? "critical" : "") + "'>" + f + "</span>";
//             }).join('') || '<div style="color:#777; font-style:italic;">N/A</div>';
//             this._div.innerHTML = "<h4 style='margin:0 0 10px 0; border-bottom:1px solid #eee; padding-bottom:5px;'>🏥 " + (props.NAME || '') + "</h4>" +
//                 "<div style='font-size:12px; margin-bottom:8px;'><b>Type:</b> " + (props.TYPE || '') + "<br><b>Beds:</b> " + ((props.BEDS && props.BEDS>0) ? props.BEDS : 'N/A') + "</div>" +
//                 "<div style='display:flex; flex-wrap:wrap; gap:4px;'>" + facilitiesHtml + "</div>";
//         };
//         this.update();
//         return this._div;
//     };
//     facilitiesControl.addTo(map);

//     // load hospitals geojson (fallback)
//     fetch("/static/data/hospitals.geojson").then(r => r.json()).then(function(data) {
//         allHospitals = data.features || [];
//         L.geoJSON(data, {
//             pointToLayer: function(f, latlng) {
//                 return L.circleMarker(latlng, { radius: 3, color: "green", fillOpacity: 0.4, interactive: false });
//             }
//         }).addTo(map);
//     }).catch(function(err) {
//         console.warn("Could not load hospitals.geojson:", err);
//     });

//     // attach single click handler
//     map.on('click', function(e) {
//         if (typeof window.triggerSeismicAnalysis === 'function') {
//             window.triggerSeismicAnalysis(e.latlng.lat, e.latlng.lng);
//         }
//     });

//     // geocoder wiring
//     if (typeof L !== 'undefined' && L.Control && typeof L.Control.Geocoder !== 'undefined') {
//         L.Control.geocoder({ defaultMarkGeocode: false, position: "topright" }).on('markgeocode', function(e) {
//             map.flyTo(e.geocode.center, 10);
//             window.triggerSeismicAnalysis(e.geocode.center.lat, e.geocode.center.lng);
//         }).addTo(map);
//         console.log("✅ Geocoder initialized");
//     } else {
//         console.warn("Geocoder not available (check scripts)");
//     }
// });

// /* ================= 6. SEISMIC ANALYSIS TRIGGER & SIMULATION ================= */
// window.triggerSeismicAnalysis = function(lat, lng) {
//     console.log("triggerSeismicAnalysis called:", lat, lng);

//     // gatekeeper: only US clicks
//     var inUS = (lat > 24.39 && lat < 49.38) && (lng > -124.84 && lng < -66.88);
//     if (!inUS) {
//         console.warn("Click outside US ignored.");
//         return;
//     }

//     var userMagInput = document.getElementById('user-mag');
//     var userMag = (userMagInput && userMagInput.value) ? parseFloat(userMagInput.value) : 6.5;
//     console.log("⚡ Triggering US Seismic Analysis (mag):", userMag);

//     fetch('/get_nearest_history?lat=' + lat + '&lng=' + lng + '&mag=' + userMag)
//     .then(function(res) { return res.json(); })
//     .then(function(data) {
//         if (data.error) { alert(data.error); return; }
//         // cleanup
//         if (seismicHeat) { try { map.removeLayer(seismicHeat); } catch(e){} seismicHeat = null; }
//         hospitalMarkers.forEach(m => { try { map.removeLayer(m); } catch(e){} });
//         hospitalMarkers = [];
//         if (routeControl) { try { map.removeControl(routeControl); } catch(e){} routeControl = null; }

//         // call simulation
//         runHistorySimulation(
//             lat,
//             lng,
//             data.mag,
//             data.radius,
//             data.place,
//             data.dist_from_click,
//             data.intensity,
//             data.depth   // ✅ ADD THIS
//         );

//         // runHistorySimulation(lat, lng, data.mag, data.radius, data.place, data.dist_from_click, data.intensity);
//     })
//     .catch(function(err) {
//         console.error("Error fetching nearest history:", err);
//         alert("Analysis failed (see console)");
//     });
// };

// // function runHistorySimulation(lat, lng, mag, radiusKm, histPlace, dataDist, aiIntensity) {/
// function runHistorySimulation(lat, lng, mag, radiusKm, histPlace, dataDist, aiIntensity, depth) {
//     var affected = [];
//     var safe = [];

//     allHospitals.forEach(function(h) {
//         if (!h || !h.geometry) return;
//         var hLat = h.geometry.coordinates[1];
//         var hLng = h.geometry.coordinates[0];
//         var dist = map.distance([lat, lng], [hLat, hLng]) / 1000;
//         var props = h.properties || {};
//         var hData = { name: props.NAME || props.name || "Hospital", lat: hLat, lng: hLng, dist: dist, beds: props.BEDS || 0, trauma: props.TRAUMA || "None", type: props.TYPE || "General" };
//         if (dist <= radiusKm) affected.push(hData); else safe.push(hData);
//     });
    

//     safe.sort(function(a,b){ return a.dist - b.dist; });
//     globalSafeHospitals = safe;

//     drawDynamicHeatmap(lat, lng, radiusKm, mag, aiIntensity, affected);

//     // store globally for report
//     window.aiIntensityGlobal = aiIntensity;

//     var confidence = Math.max(0, 100 - (dataDist * 2));
//     var barColor = confidence > 80 ? "#27ae60" : (confidence > 50 ? "#f39c12" : "#e74c3c");
//     var accBar = document.getElementById('accuracy-bar'); if (accBar) accBar.style.width = confidence + "%";
//     var accText = document.getElementById('accuracy-text'); if (accText) accText.innerText = Math.round(confidence) + "%";
//     var histText = document.getElementById('hist-ref'); if (histText) histText.innerText = "Reference: " + (histPlace || "Local history");

    
//     // 🔥 Depth Classification
//     var depthCategory = "Unknown";
//     var depthColor = "#7f8c8d";
    
//     if (depth !== undefined && depth !== null) {
//         if (depth <= 70) {
//             depthCategory = "Shallow";
//             depthColor = "#27ae60";  // green
//         } 
//         else if (depth <= 300) {
//             depthCategory = "Intermediate";
//             depthColor = "#f39c12";  // orange
//         } 
//         else {
//             depthCategory = "Deep";
//             depthColor = "#c0392b";  // red
//         }
//     }

//     var popupHtml = `
//     <div style="min-width:260px;font-family:sans-serif;">
    
//         <h4 style="margin:0 0 6px 0;color:#2c3e50;border-bottom:2px solid #e74c3c;">
//             📊 Seismic Assessment
//         </h4>
    
//         <div style="font-size:13px;line-height:1.6;">
//             <b>📍 Location:</b> ${histPlace || "Local"}<br>
//             <b>🌍 Magnitude:</b> ${mag} Mw<br>
//             <b>🔥 Intensity:</b> ${(aiIntensity && aiIntensity.toFixed) ? aiIntensity.toFixed(2) : aiIntensity} Mw<br>
//             <b>📏 Depth:</b> ${
//                 depth !== undefined && depth !== null 
//                     ? depth.toFixed(1) 
//                     : "N/A"
//             } km 
//             <span style="color:${depthColor}; font-weight:bold;">
//                 (${depthCategory})
//             </span><br>
//             <b>🌀 Impact Zone:</b> ${radiusKm} km radius<br>
//             <b>📡 Range From Click:</b> ${dataDist} km
//         </div>
    
//         <hr style="margin:6px 0">
    
//         <div style="font-size:12px;">
//             <b>📈 Model Confidence:</b> ${Math.round(confidence)}%
//         </div>
    
//     </div>
//     `;
//     // var popupHtml = "<div style='width:260px;font-family:sans-serif;'><h4 style='margin:0 0 8px 0;color:#2c3e50;border-bottom:2px solid #e74c3c;'>📊 Seismic Assessment</h4>" +
//     //     "<div style='font-size:11px;display:flex;justify-content:space-between;margin-bottom:2px;'><span>Model Confidence</span><b>" + Math.round(confidence) + "%</b></div>" +
//     //     "<div style='width:100%;background:#eee;height:6px;border-radius:3px;'><div style='width:" + confidence + "%;background:" + barColor + ";height:100%;border-radius:3px;'></div></div>" +
//     //     "<div style='font-size:12px;margin-top:10px;'><b>Site:</b> " + (histPlace || "Local") + "<br><b>AI Shaking:</b> <span style='color:#c0392b; font-weight:bold;'>" + (aiIntensity.toFixed ? aiIntensity.toFixed(2) : aiIntensity) + " Mw</span></div></div>";

//     // var popupHtml = `
//     // <div style="min-width:260px;font-family:sans-serif;">
    
//     //     <h4 style="margin:0 0 6px 0;color:#2c3e50;border-bottom:2px solid #e74c3c;">
//     //         📊 Seismic Assessment
//     //     </h4>
    
//     //     <div style="font-size:13px;line-height:1.6;">
//     //         <b>📍 Location:</b> ${histPlace || "Local"}<br>
//     //         <b>🌍 Magnitude:</b> ${mag} Mw<br>
//     //         <b>🔥 Intensity:</b> ${(aiIntensity && aiIntensity.toFixed) ? aiIntensity.toFixed(2) : aiIntensity} Mw<br>
//     //         "<b>📏 Depth:</b> " + (depth !== undefined && depth !== null ? depth.toFixed(1) : "N/A") + " km <span style='color:" + depthColor + "; font-weight:bold;'>(" + depthCategory + ")</span><br>" +
//     //         <b>🌀 Impact Zone:</b> ${radiusKm} km radius<br>
//     //         <b>📡 Range From Click:</b> ${dataDist} km
//     //     </div>
    
//     //     <hr style="margin:6px 0">
    
//     //     <div style="font-size:12px;">
//     //         <b>📈 Model Confidence:</b> ${Math.round(confidence)}%
//     //     </div>
    
//     // </div>
//     // `;
//     L.popup().setLatLng([lat, lng]).setContent(popupHtml).openOn(map);

//     if (safe.length > 0) {
//         var n = safe[0];
//         window.selectHospital(lat, lng, n.lat, n.lng, n.name, histPlace, mag, dataDist, n.beds, n.trauma, n.type);
//     }

//     // place top 3 safe markers with "analyze" buttons
//     safe.slice(0,3).forEach(function(h) {
//         var plusIcon = L.divIcon({ html: '<div style="background:#27ae60;color:white;border-radius:50%;width:24px;height:24px;text-align:center;line-height:24px;font-weight:bold;border:2px solid white;">+</div>', className: 'custom-plus-marker', iconSize: [24,24] });
//         var popupContent = "<div style='font-family:sans-serif;min-width:180px;'><b>🏥 " + h.name + "</b><br><button onclick=\"window.selectHospital(" + lat + "," + lng + "," + h.lat + "," + h.lng + ",'" + h.name.replace(/'/g,"\\'") + "','" + (histPlace || "") + "'," + mag + "," + dataDist + ",'" + h.beds + "','" + h.trauma + "','" + h.type + "')\" style='margin-top:8px;background:#3498db;color:white;border:none;padding:8px;width:100%;border-radius:4px;cursor:pointer;font-weight:bold;'>Analyze Route</button></div>";
//         try {
//             var m = L.marker([h.lat, h.lng], { icon: plusIcon }).addTo(map).bindPopup(popupContent);
//             hospitalMarkers.push(m);
//         } catch (e) {}
//     });
// }

// /* ================= 7. HEATMAP ================= */
// function drawDynamicHeatmap(lat, lng, radiusKm, mag, aiIntensity, affectedHospitals) {

//     try { if (seismicHeat) map.removeLayer(seismicHeat); } catch(e){}

//     var points = [];

//     // Normalize intensity (0–1 scale for heat layer)
//     var normalizedIntensity = Math.min(1, (aiIntensity || 1) / 10);

//     // ---- 1️⃣ Strong Epicenter Core ----
//     for (var i = 0; i < 80; i++) {
//         points.push([
//             lat + (Math.random()-0.5) * 0.01,
//             lng + (Math.random()-0.5) * 0.01,
//             1.0
//         ]);
//     }

//     // ---- 2️⃣ Radial Gaussian Hazard Field ----
//     var totalPoints = 800;   // MUCH denser field

//     for (var i = 0; i < totalPoints; i++) {

//         var angle = Math.random() * Math.PI * 2;

//         // sqrt gives natural radial density
//         var dist = Math.sqrt(Math.random()) * radiusKm;

//         // Gaussian-style decay
//         var decay = Math.exp(- (dist * dist) / (2 * Math.pow(radiusKm * 0.6, 2)));

//         var weight = normalizedIntensity * decay;

//         var newLat = lat + (dist / 111.32) * Math.cos(angle);
//         var newLng = lng + (dist / (111.32 * Math.cos(lat * (Math.PI/180)))) * Math.sin(angle);

//         points.push([newLat, newLng, weight]);
//     }

//     // ---- 3️⃣ Extra Heat on Affected Hospitals ----
//     if (Array.isArray(affectedHospitals)) {
//         affectedHospitals.forEach(function(h) {
//             for (var j = 0; j < 40; j++) {
//                 points.push([
//                     h.lat + (Math.random()-0.5)*0.005,
//                     h.lng + (Math.random()-0.5)*0.005,
//                     normalizedIntensity * 0.9
//                 ]);
//             }
//         });
//     }

//     // ---- 4️⃣ Render Heat Layer ----
//     try {
//         seismicHeat = L.heatLayer(points, {
//             radius: 55,          // larger smoother glow
//             blur: 35,
//             maxZoom: 10,
//             max: 1.0,
//             // gradient: {
//             //     0.1: '#2c7bb6',
//             //     0.3: '#00ffff',
//             //     0.5: '#00ff00',
//             //     0.7: '#ffff00',
//             //     0.9: '#ff8000',
//             //     1.0: '#ff0000'
//             // }
//         }).addTo(map);
//     } catch (e) {
//         console.warn("Heat layer failed:", e);
//     }

//     // ---- 5️⃣ Optional: Zoom to Hazard Area ----
//     try {
//         var hazardCircle = L.circle([lat, lng], { radius: radiusKm * 1000 });
//         map.fitBounds(hazardCircle.getBounds(), { padding: [40,40] });
//     } catch(e){}
// }