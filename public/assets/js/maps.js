/**
 * Maps & Emergency JavaScript
 * Handles Leaflet map, OSM data fetching, and Emergency logic.
 */

let map;
let userMarker;
let markers = [];
let currentLat = 28.6139; // Default: New Delhi
let currentLon = 77.2090;
let userLocationFound = false;

// Custom Icons
const icons = {
    user: L.divIcon({
        className: 'custom-div-icon',
        html: `<div style="background-color: #3b82f6; width: 15px; height: 15px; border-radius: 50%; border: 2px solid white; box-shadow: 0 0 10px rgba(59, 130, 246, 0.5);"></div>`,
        iconSize: [15, 15],
        iconAnchor: [7, 7]
    }),
    doctor: L.divIcon({
        className: 'custom-div-icon',
        html: `<div style="background-color: #10b981; width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; border: 2px solid white;"><i class="fa-solid fa-user-doctor text-white text-[10px]"></i></div>`,
        iconSize: [24, 24],
        iconAnchor: [12, 12]
    }),
    hospital: L.divIcon({
        className: 'custom-div-icon',
        html: `<div style="background-color: #ef4444; width: 30px; height: 30px; border-radius: 50%; display: flex; align-items: center; justify-content: center; border: 2px solid white;"><i class="fa-solid fa-hospital text-white text-xs"></i></div>`,
        iconSize: [30, 30],
        iconAnchor: [15, 15]
    }),
    pharmacy: L.divIcon({
        className: 'custom-div-icon',
        html: `<div style="background-color: #a855f7; width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; border: 2px solid white;"><i class="fa-solid fa-pills text-white text-[10px]"></i></div>`,
        iconSize: [24, 24],
        iconAnchor: [12, 12]
    })
};

document.addEventListener('DOMContentLoaded', () => {
    initMap();
    setupEventListeners();

    // Check URL params for mode
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('mode') === 'emergency') {
        openEmergencyOverlay();
    }
});

async function initMap() {
    // Initialize Leaflet
    map = L.map('map', {
        zoomControl: false,
        attributionControl: false
    }).setView([currentLat, currentLon], 13);

    // Add Dark Mode Tile Layer (CartoDB Dark Matter)
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 19
    }).addTo(map);

    // Try to get user location immediately
    locateUser();
}

function setupEventListeners() {
    // Sidebar Toggle
    const btnToggleSidebar = document.getElementById('toggleSidebar');
    if (btnToggleSidebar) {
        btnToggleSidebar.addEventListener('click', () => {
            document.getElementById('sidebar').classList.toggle('-translate-x-full');
        });
    }

    // Locate Me
    document.getElementById('btnLocateMe').addEventListener('click', locateUser);

    // Sliders & Dropdowns
    const radiusInput = document.getElementById('radiusInput');
    const radiusValue = document.getElementById('radiusValue');
    radiusInput.addEventListener('input', (e) => {
        radiusValue.textContent = `${e.target.value} km`;
    });

    // Custom Dropdown Logic
    const typeSelectBtn = document.querySelector('#typeSelect button');
    const typeDropdown = document.querySelector('#typeSelect div');
    const typeOptions = typeDropdown.querySelectorAll('button');
    const serviceTypeInput = document.getElementById('serviceType');
    const serviceLabel = document.getElementById('serviceLabel');

    typeSelectBtn.addEventListener('click', () => {
        typeDropdown.classList.toggle('hidden');
    });

    typeOptions.forEach(opt => {
        opt.addEventListener('click', () => {
            const val = opt.getAttribute('data-value');
            const label = opt.getAttribute('data-label');
            const iconClass = opt.querySelector('i').className;

            serviceTypeInput.value = val;
            serviceLabel.innerHTML = `<i class="${iconClass}"></i> ${label}`;
            typeDropdown.classList.add('hidden');
        });
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (!typeSelectBtn.contains(e.target) && !typeDropdown.contains(e.target)) {
            typeDropdown.classList.add('hidden');
        }
    });

    // Search Button
    document.getElementById('btnSearch').addEventListener('click', () => {
        const radius = parseInt(radiusInput.value) * 1000; // meters
        const type = serviceTypeInput.value;
        fetchNearby(type, radius);
    });

    // Emergency Buttons
    document.getElementById('btnEmergency').addEventListener('click', openEmergencyOverlay);
    document.getElementById('btnEmergencyHeader')?.addEventListener('click', openEmergencyOverlay); // Mobile header button
    document.getElementById('btnCloseEmergency').addEventListener('click', closeEmergencyOverlay);

    // Emergency Interactions
    document.querySelectorAll('.quick-emergency-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const condition = btn.getAttribute('data-condition');
            triggerEmergency(condition);
        });
    });

    document.getElementById('btnSubmitEmergency').addEventListener('click', () => {
        const val = document.getElementById('emergencyInput').value.trim();
        if (val) triggerEmergency(val);
    });
}

function locateUser() {
    if (!navigator.geolocation) {
        alert("Geolocation is not supported by your browser.");
        return;
    }

    // Show loading indicator on map or button?
    map.flyTo([currentLat, currentLon], 13); // Reset while waiting

    navigator.geolocation.getCurrentPosition(
        (position) => {
            currentLat = position.coords.latitude;
            currentLon = position.coords.longitude;
            userLocationFound = true;

            // Update Map View
            map.flyTo([currentLat, currentLon], 14);

            // Update/Create User Marker
            if (userMarker) {
                userMarker.setLatLng([currentLat, currentLon]);
            } else {
                userMarker = L.marker([currentLat, currentLon], { icon: icons.user }).addTo(map)
                    .bindPopup("You are here");
            }

            // Auto search nearby on first load? Maybe not to save API calls.
        },
        () => {
            console.log("Unable to retrieve your location");
        }
    );
}

async function fetchNearby(type, radius) {
    if (!userLocationFound) {
        locateUser(); // Try again
        // Wait a bit or assume default?
        // Let's just proceed with currentLat (default Delhi) if user denies auth
    }

    // Show Loader
    document.getElementById('resultsLoader').classList.remove('hidden');
    document.getElementById('resultsEmpty').classList.add('hidden');
    document.getElementById('resultsContainer').innerHTML = ''; // Clear list

    try {
        const response = await fetch(`/api/v1/maps/nearby?lat=${currentLat}&lon=${currentLon}&radius=${radius}&type_filter=${type}`);
        const data = await response.json();

        // Clear existing markers
        markers.forEach(m => map.removeLayer(m));
        markers = [];
        markersGroup = L.featureGroup();

        const resultsContainer = document.getElementById('resultsContainer');
        resultsContainer.innerHTML = '';

        if (data.length === 0) {
            document.getElementById('resultsEmpty').innerHTML = '<p class="text-gray-400">No results found nearby.</p>';
            document.getElementById('resultsEmpty').classList.remove('hidden');
        } else {
            data.forEach(place => {
                // Add Marker to Map
                let icon = icons.doctor;
                if (place.amenity_type === 'hospitals' || place.amenity_type === 'hospital') icon = icons.hospital;
                if (place.amenity_type === 'pharmacies' || place.amenity_type === 'pharmacy') icon = icons.pharmacy;

                const marker = L.marker([place.latitude, place.longitude], { icon: icon })
                    .bindPopup(`<b>${place.name}</b><br>${place.amenity_type}<br>${Math.round(place.distance)}m away`);

                marker.addTo(map);
                markers.push(marker);
                markersGroup.addLayer(marker);

                // Add Card to List
                const div = document.createElement('div');
                div.className = 'bg-white/5 border border-white/10 p-3 rounded-lg hover:bg-white/10 transition group cursor-pointer';
                div.innerHTML = `
                    <div class="flex justify-between items-start">
                        <h4 class="font-semibold text-sm group-hover:text-blue-400 transition">${place.name}</h4>
                        <span class="text-xs text-blue-300 font-mono bg-blue-500/10 px-1.5 py-0.5 rounded">${Math.round(place.distance)}m</span>
                    </div>
                    <p class="text-xs text-gray-400 capitalize mt-1">${place.amenity_type} ${place.speciality ? '• ' + place.speciality : ''}</p>
                    ${place.phone ? `<p class="text-xs text-gray-500 mt-1"><i class="fa-solid fa-phone text-[10px] mr-1"></i> ${place.phone}</p>` : ''}
                    <div class="mt-2 flex gap-2">
                        <a href="https://www.google.com/maps/dir/?api=1&destination=${place.latitude},${place.longitude}" target="_blank" class="text-[10px] bg-white/10 hover:bg-white/20 px-2 py-1 rounded text-white block text-center w-full">
                            Navigate
                        </a>
                    </div>
                `;
                div.addEventListener('click', () => {
                    map.flyTo([place.latitude, place.longitude], 16);
                    marker.openPopup();
                });
                resultsContainer.appendChild(div);
            });

            // Fit bounds to show all markers
            if (markers.length > 0) map.fitBounds(markersGroup.getBounds().pad(0.1));
        }

    } catch (error) {
        console.error("Error fetching nearby places:", error);
        alert("Failed to fetch nearby places.");
    } finally {
        document.getElementById('resultsLoader').classList.add('hidden');
    }
}

// --- Emergency Logic ---

function openEmergencyOverlay() {
    document.getElementById('emergencyOverlay').classList.remove('hidden');
    document.getElementById('emergencyOverlay').classList.add('flex');

    // Reset state
    document.getElementById('emergencyStep1').classList.remove('hidden');
    document.getElementById('emergencyLoader').classList.add('hidden');
    document.getElementById('emergencyResults').classList.add('hidden');

    // Ensure we have location
    if (!userLocationFound) locateUser();
}

function closeEmergencyOverlay() {
    document.getElementById('emergencyOverlay').classList.add('hidden');
    document.getElementById('emergencyOverlay').classList.remove('flex');
}

async function triggerEmergency(condition) {
    // UI Updates
    document.getElementById('emergencyStep1').classList.add('hidden');
    document.getElementById('emergencyLoader').classList.remove('hidden');
    document.getElementById('emergencyLoader').classList.add('flex');

    const radius = document.getElementById('radiusInput').value * 1000;

    try {
        const response = await fetch('/api/v1/maps/emergency', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                latitude: currentLat,
                longitude: currentLon,
                condition_text: condition,
                radius: radius
            })
        });

        const data = await response.json();

        // Show Results
        document.getElementById('emergencyLoader').classList.add('hidden');
        document.getElementById('emergencyLoader').classList.remove('flex');
        document.getElementById('emergencyResults').classList.remove('hidden');

        // Render Hospital
        const hospDiv = document.getElementById('emergencyHospitalDetails');
        if (data.hospital) {
            hospDiv.innerHTML = `
                <h4 class="text-xl font-bold mb-1">${data.hospital.name}</h4>
                <div class="flex items-center gap-2 mb-4 text-gray-300">
                    <span class="bg-red-500/20 text-red-400 px-2 py-0.5 rounded text-sm">${Math.round(data.hospital.distance)}m away</span>
                    ${data.hospital.phone ? `<span><i class="fa-solid fa-phone"></i> ${data.hospital.phone}</span>` : ''}
                </div>
                <div class="grid grid-cols-2 gap-3">
                    <a href="tel:${data.hospital.phone || '102'}" class="bg-green-600 hover:bg-green-700 text-white font-bold py-3 rounded-xl flex items-center justify-center gap-2 transition">
                        <i class="fa-solid fa-phone"></i> Call
                    </a>
                    <a href="https://www.google.com/maps/dir/?api=1&destination=${data.hospital.latitude},${data.hospital.longitude}" target="_blank" class="bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 rounded-xl flex items-center justify-center gap-2 transition">
                        <i class="fa-solid fa-location-arrow"></i> Navigate
                    </a>
                </div>
            `;

            // Show route on map roughly (fly to midpoint or something, but map is covered by overlay)
            // Ideally we'd show a mini map here or close overlay to see map route.
            // For now, the 'Navigate' button is best.
        } else {
            hospDiv.innerHTML = `<p class="text-gray-400">No hospital found within specific radius. Calling 102 recommended.</p>
            <a href="tel:102" class="mt-4 bg-green-600 w-full py-3 rounded-xl flex items-center justify-center gap-2 font-bold"><i class="fa-solid fa-phone"></i> Call Ambulance (102)</a>`;
        }

        // Render First Aid
        const aidDiv = document.getElementById('emergencyFirstAidDetails');
        if (data.first_aid) {
            aidDiv.innerHTML = `
                <h4 class="font-bold text-white mb-2">${data.first_aid.title || 'Instructions'}</h4>
                <div class="prose prose-invert prose-sm">
                    ${data.first_aid.content}
                </div>
                ${data.first_aid.steps ? `
                    <div class="mt-4 space-y-2">
                        ${data.first_aid.steps.map((step, i) => `
                            <div class="flex gap-3">
                                <span class="flex-none bg-blue-500/20 text-blue-400 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold">${i + 1}</span>
                                <p class="text-sm text-gray-300">${step}</p>
                            </div>
                        `).join('')}
                    </div>
                ` : ''}
            `;
        }

    } catch (error) {
        console.error("Emergency API Error:", error);
        alert("Error connecting to emergency services. Please delete this and call 102.");
        document.getElementById('emergencyLoader').classList.add('hidden');
        document.getElementById('emergencyStep1').classList.remove('hidden');
    }
}
