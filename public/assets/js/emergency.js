/**
 * Emergency JavaScript
 * Handles Leaflet map, Emergency API calls, and UI updates.
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
  hospital: L.divIcon({
    className: 'custom-div-icon',
    html: `<div style="background-color: #ef4444; width: 30px; height: 30px; border-radius: 50%; display: flex; align-items: center; justify-content: center; border: 2px solid white; animation: pulse-red 2s infinite;"><i class="fa-solid fa-hospital text-white text-xs"></i></div>`,
    iconSize: [30, 30],
    iconAnchor: [15, 15]
  })
};

document.addEventListener('DOMContentLoaded', () => {
  initMap();
  setupEventListeners();
});

async function initMap() {
  // Initialize Leaflet
  map = L.map('map', {
    zoomControl: false,
    attributionControl: false
  }).setView([currentLat, currentLon], 13);

  // Add Dark Mode Tile Layer
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    subdomains: 'abcd',
    maxZoom: 19
  }).addTo(map);

  // Try to get user location immediately
  locateUser();
}

function setupEventListeners() {
  // Locate Me
  document.getElementById('btnLocate').addEventListener('click', locateUser);

  // Radius Slider removed


  // Severity Dropdown
  const sevBtn = document.querySelector('#sevSelect button');
  const sevDropdown = document.querySelector('#sevSelect .dropdown-panel');
  const sevOptions = sevDropdown.querySelectorAll('button');
  const severityInput = document.getElementById('severity');
  const sevLabel = document.getElementById('sevLabel');

  sevBtn.addEventListener('click', () => {
    sevDropdown.classList.toggle('hidden');
  });

  sevOptions.forEach(opt => {
    opt.addEventListener('click', () => {
      const val = opt.getAttribute('data-value');
      const label = opt.getAttribute('data-label');
      severityInput.value = val;
      sevLabel.textContent = label;
      sevDropdown.classList.add('hidden');
    });
  });

  // Close dropdown when clicking outside
  document.addEventListener('click', (e) => {
    if (!sevBtn.contains(e.target) && !sevDropdown.contains(e.target)) {
      sevDropdown.classList.add('hidden');
    }
  });

  // Search Button
  document.getElementById('btnSearch').addEventListener('click', handleEmergencySearch);
}

function locateUser() {
  const statusDiv = document.getElementById('status');
  statusDiv.textContent = "Locating...";

  if (!navigator.geolocation) {
    statusDiv.textContent = "Geolocation not supported.";
    return;
  }

  navigator.geolocation.getCurrentPosition(
    (position) => {
      currentLat = position.coords.latitude;
      currentLon = position.coords.longitude;
      userLocationFound = true;
      statusDiv.textContent = "Location found.";

      // Update Map View
      map.setView([currentLat, currentLon], 14);

      // Update/Create User Marker
      if (userMarker) {
        userMarker.setLatLng([currentLat, currentLon]);
      } else {
        userMarker = L.marker([currentLat, currentLon], { icon: icons.user }).addTo(map)
          .bindPopup("You are here");
      }
    },
    () => {
      statusDiv.textContent = "Location access denied.";
      console.log("Unable to retrieve your location");
    }
  );
}

async function handleEmergencySearch() {
  const condition = document.getElementById('emergencyCondition').value.trim();
  if (!condition) {
    alert("Please describe the emergency condition.");
    return;
  }

  const radius = 10 * 1000; // Fixed 10km radius as slider removed
  const btnSearch = document.getElementById('btnSearch');
  const originalText = btnSearch.innerHTML;

  // Loading state
  btnSearch.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Finding help...`;
  btnSearch.disabled = true;

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

    // Update UI with Hospital Info
    updateHospitalUI(data.hospital);

    // Update UI with First Aid
    updateFirstAidUI(data.first_aid);

  } catch (error) {
    console.error("Emergency API Error:", error);
    alert("Error connecting to emergency services. call 102/108 immediately.");
  } finally {
    btnSearch.innerHTML = originalText;
    btnSearch.disabled = false;
  }
}

function updateHospitalUI(hospital) {
  // Clear existing markers
  markers.forEach(m => map.removeLayer(m));
  markers = [];

  const nearInfo = document.getElementById('nearInfo');
  const listDiv = document.getElementById('list');
  const callBtn = document.getElementById('callNearest');

  if (hospital) {
    nearInfo.textContent = `${Math.round(hospital.distance)}m away`;

    // Add Marker
    const marker = L.marker([hospital.latitude, hospital.longitude], { icon: icons.hospital })
      .addTo(map)
      .bindPopup(`<b>${hospital.name}</b><br>${Math.round(hospital.distance)}m away`)
      .openPopup();

    markers.push(marker);

    // Fit bounds
    const group = new L.featureGroup([userMarker, marker]);
    map.fitBounds(group.getBounds().pad(0.2));

    // Update List Card
    listDiv.innerHTML = `
            <div class="py-2">
                <div class="font-bold text-lg">${hospital.name}</div>
                <div class="text-sm text-gray-400 mt-1">${hospital.amenity_type}</div>
                <div class="mt-3 flex gap-2">
                    <a href="https://www.google.com/maps/dir/?api=1&destination=${hospital.latitude},${hospital.longitude}" target="_blank" 
                       class="bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold px-3 py-2 rounded-lg flex items-center gap-2">
                        <i class="fa-solid fa-location-arrow"></i> Navigate
                    </a>
                    ${hospital.phone ? `
                    <a href="tel:${hospital.phone}" 
                       class="bg-green-600 hover:bg-green-700 text-white text-xs font-bold px-3 py-2 rounded-lg flex items-center gap-2">
                        <i class="fa-solid fa-phone"></i> Call
                    </a>` : ''}
                </div>
            </div>
        `;

    // Update Main Call Button
    if (hospital.phone) {
      callBtn.href = `tel:${hospital.phone}`;
      callBtn.classList.remove('disabled:opacity-50');
      callBtn.innerHTML = `<i class="fa-solid fa-phone-volume"></i> Call ${hospital.name}`;
    }

  } else {
    nearInfo.textContent = "Not found";
    listDiv.innerHTML = `<p class="text-gray-400 text-sm py-2">No hospitals found within search radius.</p>`;
  }
}

function updateFirstAidUI(firstAid) {
  const section = document.getElementById('firstAidSection');
  const content = document.getElementById('firstAidContent');

  if (firstAid) {
    section.classList.remove('hidden');

    let stepsHtml = '';
    if (firstAid.steps && firstAid.steps.length > 0) {
      stepsHtml = `<div class="mt-3 space-y-2">
                ${firstAid.steps.map((step, i) => `
                    <div class="flex gap-3">
                        <span class="flex-none bg-blue-500/20 text-blue-400 w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold">${i + 1}</span>
                        <p class="text-sm text-gray-300">${step}</p>
                    </div>
                `).join('')}
            </div>`;
    }

    content.innerHTML = `
            <div class="border-l-2 border-blue-500 pl-3">
                <h4 class="font-bold text-white mb-1">${firstAid.title || 'Instructions'}</h4>
                <div class="prose prose-invert prose-sm text-gray-300">
                    ${firstAid.content}
                </div>
            </div>
            ${stepsHtml}
        `;
  }
}
