/**
 * Connect Page JavaScript
 * Uses backend `/api/v1/maps/nearby` (Overpass + cache)
 */

// ── State ──────────────────────────────────────────
let map, userMarker, radiusCircle, markersLayer;
const defaultCenter = { lat: 20.5937, lon: 78.9629 };
let currentResults = [];
let isSearching = false;

const API_BASE = '/api/v1/maps';

const AMENITY_ICONS = {
  doctors: '<i class="fa-solid fa-user-doctor text-green-400"></i>',
  hospitals: '<i class="fa-solid fa-hospital text-red-400"></i>',
  pharmacies: '<i class="fa-solid fa-prescription-bottle-medical text-purple-400"></i>'
};

const AMENITY_LABELS = {
  doctors: 'Doctor / Clinic',
  hospitals: 'Hospital',
  pharmacies: 'Pharmacy'
};

// ── Initialisation ─────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  await initializePage();
  setupEventListeners();
  setupTypeDropdown();
  updateRadiusLabel();
});

async function initializePage() {
  let center = defaultCenter;

  if (typeof GeolocationService !== 'undefined') {
    const location = await GeolocationService.getCurrentPosition();
    if (location) center = location;
  }

  initMap(center, 14);
  search();
}

// ── Event Wiring ───────────────────────────────────
function setupEventListeners() {
  document.getElementById('radius')?.addEventListener('input', handleRadiusChange);
  document.getElementById('btnLocate')?.addEventListener('click', handleLocate);
  document.getElementById('btnSearch')?.addEventListener('click', search);

  const qInput = document.getElementById('q');
  if (qInput && typeof Utils !== 'undefined') {
    qInput.addEventListener('input', Utils.debounce(search, 500));
  }
}

// ── Type Dropdown (multi-select checkboxes) ────────
function setupTypeDropdown() {
  const dropdownBtn = document.getElementById('typeDropdownBtn');
  const dropdown = document.getElementById('typeDropdown');
  const checkboxes = document.querySelectorAll('.type-checkbox');

  if (!dropdownBtn || !dropdown) return;

  dropdownBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    dropdown.classList.toggle('hidden');
    dropdownBtn.querySelector('i.fa-chevron-down')?.classList.toggle('rotate-180');
  });

  document.addEventListener('click', (e) => {
    if (!dropdown.contains(e.target) && e.target !== dropdownBtn) {
      dropdown.classList.add('hidden');
      dropdownBtn.querySelector('i.fa-chevron-down')?.classList.remove('rotate-180');
    }
  });

  checkboxes.forEach(cb => {
    cb.addEventListener('change', () => {
      updateTypeLabel();
      search();
    });
  });

  updateTypeLabel();
}

function updateTypeLabel() {
  const checked = document.querySelectorAll('.type-checkbox:checked');
  const label = document.getElementById('typeLabel');
  const total = document.querySelectorAll('.type-checkbox').length;

  if (checked.length === 0) {
    label.textContent = 'None selected';
  } else if (checked.length === total) {
    label.textContent = 'All';
  } else {
    label.textContent = Array.from(checked)
      .map(cb => cb.parentElement.querySelector('span').textContent)
      .join(', ');
  }
}

/** Returns array of checkbox values, e.g. ['doctors', 'hospital'] */
function getSelectedTypes() {
  return Array.from(document.querySelectorAll('.type-checkbox:checked')).map(cb => cb.value);
}

// ── Map Helpers ────────────────────────────────────
function initMap(center, zoom) {
  if (map) return;

  map = L.map('map', { zoomControl: true, attributionControl: true })
    .setView([center.lat, center.lon], zoom);

  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
    subdomains: 'abcd',
    maxZoom: 19
  }).addTo(map);

  markersLayer = L.layerGroup().addTo(map);
  setUserLocation(center);
}

function setUserLocation(center) {
  if (userMarker) userMarker.remove();
  if (radiusCircle) radiusCircle.remove();

  // Custom blue pulsing icon for user position
  const userIcon = L.divIcon({
    className: 'user-location-icon',
    html: '<div class="user-dot"></div>',
    iconSize: [18, 18],
    iconAnchor: [9, 9]
  });

  userMarker = L.marker([center.lat, center.lon], { icon: userIcon, title: 'You are here', zIndexOffset: 1000 }).addTo(map);
  radiusCircle = L.circle([center.lat, center.lon], {
    radius: getRadiusMeters(),
    color: '#3b82f6',
    weight: 1.5,
    fillOpacity: 0.06,
    dashArray: '6 4'
  }).addTo(map);

  map.flyTo([center.lat, center.lon], map.getZoom());
}

function getRadiusMeters() {
  return Number(document.getElementById('radius').value) * 1000;
}

function updateRadiusLabel() {
  const val = document.getElementById('radius').value;
  document.getElementById('radiusLabel').textContent = val + ' km';
}

function handleRadiusChange() {
  updateRadiusLabel();
  if (radiusCircle) {
    radiusCircle.setRadius(getRadiusMeters());
    search();
  }
}

async function handleLocate() {
  const statusEl = document.getElementById('status');
  statusEl.textContent = 'Locating…';

  if (typeof GeolocationService !== 'undefined') {
    const location = await GeolocationService.getCurrentPosition();
    if (location) {
      setUserLocation(location);
      statusEl.textContent = '';
      search();
    } else {
      statusEl.textContent = 'Location unavailable. Please allow location access.';
    }
  } else {
    statusEl.textContent = 'Geolocation not supported.';
  }
}

// ── Haversine Distance ─────────────────────────────
function haversine(lat1, lon1, lat2, lon2) {
  const R = 6371000;
  const toRad = d => d * Math.PI / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) *
    Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function mapUiTypesToBackendSet(types) {
  // UI values: doctors | hospital | pharmacy
  // Backend values: doctors | hospitals | pharmacies
  const wanted = new Set();
  for (const t of types) {
    if (t === 'doctors') wanted.add('doctors');
    if (t === 'hospital') wanted.add('hospitals');
    if (t === 'pharmacy') wanted.add('pharmacies');
  }
  return wanted;
}

// ── Search (Main) ──────────────────────────────────
async function search() {
  if (isSearching) return;

  const statusEl = document.getElementById('status');
  const countEl = document.getElementById('count');
  const listEl = document.getElementById('list');

  const types = getSelectedTypes();
  if (types.length === 0) {
    clearResults();
    statusEl.textContent = 'Please select at least one facility type.';
    return;
  }

  if (!userMarker) {
    statusEl.textContent = 'Location not set. Click "Use my location".';
    return;
  }

  isSearching = true;
  statusEl.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1"></i> Searching nearby…';
  clearResults();

  // Show shimmer placeholders
  listEl.innerHTML = Array(3).fill(0).map(() => `
    <div class="shimmer-card rounded-lg p-4 mb-2">
      <div class="shimmer-line w-3/4 h-4 mb-2 rounded"></div>
      <div class="shimmer-line w-1/2 h-3 rounded"></div>
    </div>
  `).join('');

  const center = {
    lat: userMarker.getLatLng().lat,
    lon: userMarker.getLatLng().lng
  };
  const radiusM = getRadiusMeters();

  try {
    const wantedAmenityTypes = mapUiTypesToBackendSet(types);
    const url = `${API_BASE}/nearby?lat=${encodeURIComponent(center.lat)}&lon=${encodeURIComponent(center.lon)}&radius=${encodeURIComponent(radiusM)}&type_filter=all`;
    const response = await fetch(url);
    if (!response.ok) throw new Error(`Nearby lookup failed (${response.status})`);
    const data = await response.json();

    let results = (Array.isArray(data) ? data : []).map(item => {
      const lat = item.latitude;
      const lon = item.longitude;
      const dist = item.distance ?? haversine(center.lat, center.lon, lat, lon);
      return {
        osm_id: item.osm_id,
        name: item.name || 'Unnamed',
        amenity_type: item.amenity_type,
        phone: item.phone || null,
        email: item.email || null,
        website: item.website || null,
        address: item.address || null,
        opening_hours: item.opening_hours || null,
        speciality: item.speciality || null,
        lat,
        lon,
        distance: dist,
        source: item.source
      };
    }).filter(r => r.lat != null && r.lon != null);

    results = results.filter(r => wantedAmenityTypes.has(r.amenity_type));

    // Client-side text filter
    const q = (document.getElementById('q').value || '').trim().toLowerCase();
    if (q) {
      results = results.filter(r => {
        const haystack = `${r.name} ${r.amenity_type} ${r.speciality || ''}`.toLowerCase();
        return haystack.includes(q);
      });
    }

    // Sort by distance
    results.sort((a, b) => a.distance - b.distance);
    currentResults = results;

    renderResults(results, center);
    countEl.textContent = String(results.length);
    statusEl.textContent = results.length ? '' : 'No results found within radius.';

    // Fit bounds
    if (results.length > 0) {
      const bounds = L.latLngBounds(results.map(r => [r.lat, r.lon]));
      bounds.extend([center.lat, center.lon]);
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 15 });
    }
  } catch (err) {
    console.error('Nearby search error:', err);
    statusEl.textContent = 'Search failed. Please try again in a moment.';
    listEl.innerHTML = '';
  } finally {
    isSearching = false;
  }
}

// ── Clear ──────────────────────────────────────────
function clearResults() {
  if (markersLayer) markersLayer.clearLayers();
  document.getElementById('list').innerHTML = '';
  document.getElementById('count').textContent = '0';
}

// ── Format distance nicely ─────────────────────────
function fmtDist(m) {
  return m < 1000 ? Math.round(m) + ' m' : (m / 1000).toFixed(1) + ' km';
}

// ── Render Results ─────────────────────────────────
function renderResults(results, center) {
  const listEl = document.getElementById('list');
  listEl.innerHTML = '';

  // Colour palette for numbered markers
  const markerColors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'];

  results.forEach((r, i) => {
    // ── Map marker for EVERY result ───────────
    const colour = markerColors[i % markerColors.length];
    const iconHtml = `<div style="
      background:${colour};color:#fff;width:26px;height:26px;border-radius:50%;
      display:flex;align-items:center;justify-content:center;font-size:11px;
      font-weight:700;border:2px solid rgba(255,255,255,.3);
      box-shadow:0 2px 8px ${colour}88;">${i + 1}</div>`;

    const divIcon = L.divIcon({
      className: 'custom-num-marker',
      html: iconHtml,
      iconSize: [26, 26],
      iconAnchor: [13, 13]
    });

    const marker = L.marker([r.lat, r.lon], { icon: divIcon }).addTo(markersLayer);

    // Popup
    marker.bindPopup(`
      <div style="min-width:140px">
        <strong>${r.name}</strong><br>
        <span style="opacity:.7;font-size:12px">${AMENITY_LABELS[r.amenity_type] || r.amenity_type}</span><br>
        <span style="font-size:11px;opacity:.5">${fmtDist(r.distance)} away</span>
        ${r.phone ? `<br><a href="tel:${r.phone}" style="color:#3b82f6;font-size:12px">${r.phone}</a>` : ''}
      </div>
    `);

    // Link marker click to list card (if it's in top 5)
    marker.on('click', () => {
      const card = document.getElementById(`result-${i}`);
      if (card) {
        card.scrollIntoView({ behavior: 'smooth', block: 'center' });
        card.classList.add('ring-1', 'ring-blue-500/50');
        setTimeout(() => card.classList.remove('ring-1', 'ring-blue-500/50'), 2000);
      }
    });

    // ── Detail card for TOP 5 only ───────────
    if (i < 5) {
      const amenityIcon = AMENITY_ICONS[r.amenity_type] || '<i class="fa-solid fa-location-dot text-gray-400"></i>';
      const card = document.createElement('div');
      card.className = 'result-card py-3 px-3 rounded-xl transition cursor-pointer hover:bg-white/5';
      card.id = `result-${i}`;

      card.innerHTML = `
        <div class="flex items-start gap-3">
          <!-- number badge -->
          <div class="flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold"
               style="background:${colour}22;color:${colour};border:1px solid ${colour}44">${i + 1}</div>

          <!-- info -->
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 flex-wrap">
              <h4 class="font-medium text-sm truncate">${r.name}</h4>
              <span class="text-[11px] font-mono px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400">${fmtDist(r.distance)}</span>
            </div>
            <div class="text-xs text-gray-400 mt-0.5 flex items-center gap-2">
              ${amenityIcon}
              <span class="capitalize">${AMENITY_LABELS[r.amenity_type] || r.amenity_type}</span>
              ${r.speciality ? `<span class="text-gray-500">· ${r.speciality}</span>` : ''}
            </div>

            <!-- expandable details -->
            <div id="details-${i}" class="hidden mt-3 space-y-2 text-xs text-gray-300 border-t border-gray-800 pt-3 animate-slideDown">
              ${r.phone ? `
                <div class="flex items-center gap-2">
                  <i class="fa-solid fa-phone text-green-400 w-4"></i>
                  <a href="tel:${r.phone}" class="text-blue-400 hover:underline">${r.phone}</a>
                </div>` : '<div class="flex items-center gap-2 text-gray-500"><i class="fa-solid fa-phone w-4"></i> Not available</div>'}

              ${r.address ? `
                <div class="flex items-start gap-2">
                  <i class="fa-solid fa-map-location-dot text-gray-500 w-4 mt-0.5"></i>
                  <span>${r.address}</span>
                </div>` : ''}

              ${r.opening_hours ? `
                <div class="flex items-start gap-2">
                  <i class="fa-solid fa-clock text-gray-500 w-4 mt-0.5"></i>
                  <span>${r.opening_hours}</span>
                </div>` : ''}

              <!-- Action buttons -->
              <div class="flex gap-2 mt-2">
                <a href="https://www.google.com/maps/dir/?api=1&destination=${r.lat},${r.lon}"
                   target="_blank" rel="noopener"
                   class="flex-1 flex items-center justify-center gap-1.5 bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 border border-blue-600/30 py-2 rounded-lg text-xs font-medium transition">
                  <i class="fa-solid fa-diamond-turn-right"></i> Navigate
                </a>
                ${r.phone ? `
                <a href="tel:${r.phone}"
                   class="flex-1 flex items-center justify-center gap-1.5 bg-green-600/20 hover:bg-green-600/30 text-green-400 border border-green-600/30 py-2 rounded-lg text-xs font-medium transition">
                  <i class="fa-solid fa-phone"></i> Call
                </a>` : ''}
              </div>
            </div>
          </div>

          <!-- expand chevron -->
          <button class="expand-btn w-8 h-8 rounded-lg hover:bg-white/10 flex items-center justify-center text-gray-400 transition flex-shrink-0">
            <i class="fa-solid fa-chevron-down text-xs transition-transform"></i>
          </button>
        </div>
      `;

      // Toggle expand
      card.addEventListener('click', (e) => {
        if (e.target.closest('a')) return; // don't intercept links

        const details = card.querySelector(`#details-${i}`);
        const chevron = card.querySelector('.expand-btn i');
        const wasHidden = details.classList.contains('hidden');

        // Collapse all others
        document.querySelectorAll('[id^="details-"]').forEach(d => d.classList.add('hidden'));
        document.querySelectorAll('.expand-btn i').forEach(ic => ic.classList.remove('rotate-180'));

        if (wasHidden) {
          details.classList.remove('hidden');
          chevron.classList.add('rotate-180');
          map.flyTo([r.lat, r.lon], 16);
          marker.openPopup();
        }
      });

      listEl.appendChild(card);
    }
  });

  // If more results than shown
  if (results.length > 5) {
    const moreEl = document.createElement('div');
    moreEl.className = 'text-center text-xs text-gray-500 py-3';
    moreEl.textContent = `+ ${results.length - 5} more shown on the map`;
    listEl.appendChild(moreEl);
  }
}
