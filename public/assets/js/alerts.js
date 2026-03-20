/**
 * Disease Trends Page JavaScript
 * Displays disease outbreak data across India with color-coded regions
 */

// Disease color mapping - will be populated dynamically
const diseaseColors = {
  // Default colors for common diseases
  dengue: '#ef4444',      // Red
  malaria: '#eab308',     // Yellow
  covid: '#a855f7',       // Purple
  influenza: '#3b82f6',   // Blue
  typhoid: '#f97316',     // Orange
  cholera: '#22c55e'      // Green
};

// Color palette for generating colors for new diseases
const colorPalette = [
  '#ef4444', '#eab308', '#a855f7', '#3b82f6', '#f97316', '#22c55e',
  '#ec4899', '#14b8a6', '#f59e0b', '#8b5cf6', '#06b6d4', '#84cc16',
  '#f43f5e', '#10b981', '#6366f1', '#f97316', '#14b8a6', '#a855f7'
];

// Generate a color for a disease name
function getDiseaseColor(diseaseName) {
  const normalized = normalizeDiseaseName(diseaseName);
  if (diseaseColors[normalized]) {
    return diseaseColors[normalized];
  }
  // Generate color based on hash of disease name
  let hash = 0;
  for (let i = 0; i < diseaseName.length; i++) {
    hash = diseaseName.charCodeAt(i) + ((hash << 5) - hash);
  }
  const index = Math.abs(hash) % colorPalette.length;
  const color = colorPalette[index];
  diseaseColors[normalized] = color; // Cache it
  return color;
}

// Map database disease names to frontend keys
function normalizeDiseaseName(name) {
  if (!name) return 'other';
  const lower = name.toLowerCase().trim();
  // Handle common variations
  if (lower.includes('covid') || lower.includes('coronavirus')) return 'covid';
  if (lower.includes('dengue')) return 'dengue';
  if (lower.includes('malaria')) return 'malaria';
  if (lower.includes('influenza') || lower.includes('flu')) return 'influenza';
  if (lower.includes('typhoid')) return 'typhoid';
  if (lower.includes('cholera')) return 'cholera';
  // Return normalized version (lowercase, spaces to underscores)
  return lower.replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '');
}

// Disease outbreak data from database
const diseaseOutbreaks = [];

// Health bulletins from database
const healthBulletins = [];

// Historical trends data - will be populated from database
const trendsData = {
  labels: [],
  datasets: {}
};

// Store growth rates for each disease
const diseaseGrowthRates = {};

// Prevention steps data for each disease
const preventionData = {
  dengue: {
    icon: 'fa-mosquito',
    title: 'Dengue',
    steps: [
      'Eliminate stagnant water around your home where mosquitoes breed',
      'Use mosquito repellent and wear long sleeves, especially during dawn and dusk',
      'Install or repair window and door screens to keep mosquitoes out',
      'Use mosquito nets while sleeping, especially for children and elderly',
      'Support community fogging and clean-up drives in your area'
    ]
  },
  malaria: {
    icon: 'fa-bugs',
    title: 'Malaria',
    steps: [
      'Sleep under insecticide-treated bed nets (ITNs) every night',
      'Take prescribed antimalarial prophylaxis if traveling to high-risk regions',
      'Wear protective clothing and use DEET-based repellents',
      'Clear stagnant water, puddles, and blocked drains near your home',
      'Seek immediate medical attention if you experience cyclic fever and chills'
    ]
  },
  covid: {
    icon: 'fa-virus-covid',
    title: 'COVID-19',
    steps: [
      'Stay up-to-date with recommended booster vaccinations',
      'Wear a well-fitted mask in crowded or poorly ventilated indoor spaces',
      'Wash hands frequently with soap for at least 20 seconds',
      'Maintain physical distancing in high-risk environments',
      'Isolate immediately and get tested if you develop respiratory symptoms'
    ]
  },
  influenza: {
    icon: 'fa-head-side-virus',
    title: 'Influenza',
    steps: [
      'Get an annual flu vaccination before the start of each season',
      'Cover your mouth and nose when coughing or sneezing; use a tissue or elbow',
      'Avoid close contact with people who are visibly sick',
      'Disinfect frequently touched surfaces like doorknobs, phones, and keyboards',
      'Stay home from work or school when experiencing flu symptoms'
    ]
  },
  typhoid: {
    icon: 'fa-glass-water-droplet',
    title: 'Typhoid',
    steps: [
      'Drink only boiled or purified water; avoid untreated tap water or ice',
      'Eat freshly cooked food; avoid raw salads, peeled fruits from street stalls',
      'Wash hands thoroughly with soap before eating and after using the washroom',
      'Get a typhoid vaccination, especially before traveling to endemic regions',
      'Ensure proper sanitation and sewage disposal in your community'
    ]
  },
  cholera: {
    icon: 'fa-droplet',
    title: 'Cholera',
    steps: [
      'Drink only safe, treated, or boiled water; avoid street-served beverages',
      'Wash fruits, vegetables, and hands with clean water before eating',
      'Ensure food is cooked thoroughly and served hot',
      'Dispose of human waste safely and avoid open defecation',
      'Seek oral rehydration treatment immediately if severe diarrhea develops'
    ]
  }
};

// State
let map, markersLayer, trendsChart;
let diseaseDropdown;
let availableDiseases = []; // Store diseases from database
let diseaseKeyToDiseaseId = new Map();

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  try {
    initializePage();
    setupEventListeners();
    setupDropdowns();

    // Fetch diseases first, then fetch data
    fetchDiseases().then(() => {
      fetchData();
      // Periodically refresh from live sources, then re-render from DB.
      // Keeps trends/outbreaks dynamic without blocking the UI.
      setInterval(() => {
        triggerLiveRefresh().finally(() => fetchData());
      }, 5 * 60 * 1000);
    }).catch(err => {
      console.error('Error fetching diseases:', err);
      // Still try to fetch data
      fetchData();
    });
  } catch (error) {
    console.error('Error initializing page:', error);
    // Try to at least show the map
    try {
      initializePage();
    } catch (e) {
      console.error('Failed to initialize map:', e);
    }
  }
});

let _refreshingLive = false;
let _lastLiveRefreshAt = null;
function updateLiveRefreshStatus(text, tone = 'muted') {
  const el = document.getElementById('liveRefreshStatus');
  if (!el) return;
  el.classList.remove('hidden', 'text-gray-400', 'text-green-400', 'text-red-400');
  if (tone === 'ok') el.classList.add('text-green-400');
  else if (tone === 'error') el.classList.add('text-red-400');
  else el.classList.add('text-gray-400');
  el.textContent = text;
}

function formatRefreshTime(d) {
  try {
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
}

async function triggerLiveRefresh() {
  if (_refreshingLive) return;
  _refreshingLive = true;
  updateLiveRefreshStatus('Refreshing live sources…', 'muted');
  try {
    const res = await fetch('/api/v1/refresh?mode=who', { method: 'POST' });
    if (!res.ok) {
      throw new Error(`refresh failed (${res.status})`);
    }
    _lastLiveRefreshAt = new Date();
    updateLiveRefreshStatus(`Live refreshed at ${formatRefreshTime(_lastLiveRefreshAt)}`, 'ok');
  } catch (e) {
    // Keep app usable with DB-only data while surfacing the refresh issue.
    updateLiveRefreshStatus('Live refresh failed. Showing latest database data.', 'error');
  } finally {
    _refreshingLive = false;
  }
}

async function fetchDiseases() {
  try {
    const res = await fetch('/api/v1/diseases');
    const diseases = await res.json();
    if (Array.isArray(diseases)) {
      availableDiseases = diseases;
      populateDiseaseDropdown();
    }
  } catch (e) {
    console.error("Error fetching diseases:", e);
  }
}

function populateDiseaseDropdown() {
  const dropdownPanel = document.querySelector('#diseaseSelect div.absolute');
  if (!dropdownPanel || !diseaseDropdown) return;

  diseaseKeyToDiseaseId = new Map();

  // Clear existing options
  dropdownPanel.innerHTML = '';

  // Add "All Diseases" option
  const allBtn = document.createElement('button');
  allBtn.type = 'button';
  allBtn.setAttribute('data-value', 'all');
  allBtn.setAttribute('data-label', 'All Diseases');
  allBtn.className = 'w-full text-left px-3 py-2 hover:bg-gray-800 text-sm';
  allBtn.textContent = 'All Diseases';
  dropdownPanel.appendChild(allBtn);

  // Add diseases from database
  availableDiseases.forEach(disease => {
    const diseaseKey = normalizeDiseaseName(disease.name);
    const color = getDiseaseColor(disease.name);
    diseaseKeyToDiseaseId.set(diseaseKey, disease.id);

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.setAttribute('data-value', diseaseKey);
    btn.setAttribute('data-label', disease.name);
    btn.className = 'w-full text-left px-3 py-2 hover:bg-gray-800 text-sm flex items-center gap-2';

    const colorDot = document.createElement('span');
    colorDot.className = 'w-3 h-3 rounded-full flex-shrink-0';
    colorDot.style.background = color;

    btn.appendChild(colorDot);
    btn.appendChild(document.createTextNode(disease.name));
    dropdownPanel.appendChild(btn);
  });

  // Attach event listeners to new buttons
  dropdownPanel.querySelectorAll('button[data-value]').forEach(btn => {
    // Remove existing listeners by cloning
    const newBtn = btn.cloneNode(true);
    btn.parentNode.replaceChild(newBtn, btn);

    // Attach click listener
    newBtn.addEventListener('click', () => {
      diseaseDropdown.select(
        newBtn.getAttribute('data-value'),
        newBtn.getAttribute('data-label') || newBtn.textContent.trim()
      );
    });
  });
}

async function fetchData() {
  try {
    const selectedDisease = document.getElementById('disease')?.value || 'all';
    const diseaseId = selectedDisease !== 'all' ? diseaseKeyToDiseaseId.get(selectedDisease) : null;

    // Build query params
    const params = diseaseId && selectedDisease !== 'all' ? `?disease_id=${diseaseId}` : '';

    // Fetch Outbreaks
    const outRes = await fetch(`/api/v1/outbreaks${params}`);
    if (!outRes.ok) {
      throw new Error(`HTTP error! status: ${outRes.status}`);
    }
    const outbreaks = await outRes.json();

    if (Array.isArray(outbreaks)) {
      // Clear existing and push new
      diseaseOutbreaks.length = 0;
      outbreaks.forEach(o => {
        const diseaseKey = normalizeDiseaseName(o.disease);
        // Ensure color exists for this disease
        getDiseaseColor(o.disease);

        // Add outbreak - backend now handles geocoding, so coordinates should be valid
        if (o.center && o.center.lat && o.center.lon &&
          o.center.lat !== 0 && o.center.lon !== 0 &&
          !isNaN(o.center.lat) && !isNaN(o.center.lon)) {
          diseaseOutbreaks.push({
            disease: diseaseKey,
            originalName: o.disease,
            region: o.region,
            center: o.center,
            cases: o.cases || 0,
            date: o.date,
            radius: Math.min(Math.max((o.cases || 1) * 50, 20000), 100000)
          });
        }
      });
      render();
      renderDiseaseList();
    }

    // Fetch Bulletins
    console.log('Fetching bulletins from:', `/api/v1/bulletins${params}`);
    const bullRes = await fetch(`/api/v1/bulletins${params}`);
    const bulletins = await bullRes.json();
    if (Array.isArray(bulletins)) {
      healthBulletins.length = 0;
      // We only want 3, backend should handle it but let's be safe
      bulletins.slice(0, 3).forEach(b => healthBulletins.push(b));
      renderBulletins();
    }

    // Fetch Trends
    const trendsRes = await fetch(`/api/v1/trends${params}`);
    const trends = await trendsRes.json();

    if (Array.isArray(trends) && trends.length > 0) {
      // Get unique dates and sort them
      const dateSet = new Set();
      trends.forEach(t => {
        if (t.date) dateSet.add(t.date);
      });
      const uniqueDates = Array.from(dateSet).sort((a, b) => new Date(a) - new Date(b));

      if (uniqueDates.length > 0) {
        // Format dates for display
        trendsData.labels = uniqueDates.map(d => {
          const date = new Date(d);
          return date.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
        });

        // Reset all datasets
        trendsData.datasets = {};
        // Clear growth rates
        Object.keys(diseaseGrowthRates).forEach(key => delete diseaseGrowthRates[key]);

        // Group trends by disease
        const diseaseTrendMap = {};
        trends.forEach(t => {
          const disease = normalizeDiseaseName(t.disease);
          if (!diseaseTrendMap[disease]) {
            diseaseTrendMap[disease] = {
              name: t.disease,
              data: new Array(uniqueDates.length).fill(0),
              growthRates: []
            };
          }

          const dateIdx = uniqueDates.indexOf(t.date);
          if (dateIdx !== -1 && dateIdx >= 0) {
            diseaseTrendMap[disease].data[dateIdx] += (t.cases || 0);
            if (t.growth_rate !== null && t.growth_rate !== undefined) {
              diseaseTrendMap[disease].growthRates.push(t.growth_rate);
            }
          }
        });

        // Calculate average growth rate for each disease
        Object.keys(diseaseTrendMap).forEach(disease => {
          const trendInfo = diseaseTrendMap[disease];
          trendsData.datasets[disease] = trendInfo.data;

          // Calculate growth rate: average of all growth rates, or calculate from data
          if (trendInfo.growthRates.length > 0) {
            const avgGrowth = trendInfo.growthRates.reduce((a, b) => a + b, 0) / trendInfo.growthRates.length;
            diseaseGrowthRates[disease] = avgGrowth;
          } else {
            // Calculate growth rate from data points
            const data = trendInfo.data;
            const validData = data.filter(v => v > 0);
            if (validData.length >= 2) {
              const recent = validData.slice(-2);
              const growth = recent[0] > 0 ? ((recent[1] - recent[0]) / recent[0]) * 100 : 0;
              diseaseGrowthRates[disease] = growth;
            } else {
              diseaseGrowthRates[disease] = 0;
            }
          }
        });

        updateTrendsChart();
        renderPreventionSteps();
        renderDiseaseList(); // Update disease list with growth rates
      } else {
        // no-op
      }
    } else {
      // If no trends data, still update chart
      trendsData.labels = [];
      trendsData.datasets = {};
      updateTrendsChart();
    }

  } catch (e) {
    console.error("Error fetching alerts data:", e);
    // Show error message to user
    const diseaseListDiv = document.getElementById('diseaseList');
    if (diseaseListDiv) {
      diseaseListDiv.innerHTML = '<p class="text-xs text-red-400">Error loading data. Please try refreshing.</p>';
    }
    // Ensure map still renders even if data fails
    if (map && markersLayer) {
      render();
    }
  }
}

function initializePage() {
  try {
    // Center on India
    const indiaCenter = { lat: 22.5, lon: 79.0 };
    initMap(indiaCenter, 5);
    // Initialize chart with empty data
    setTimeout(() => {
      initTrendsChart();
    }, 100);
    render();
    console.log('Page initialized');
  } catch (error) {
    console.error('Error in initializePage:', error);
  }
}

function setupEventListeners() {
  document.getElementById('btnRefresh')?.addEventListener('click', refresh);
}

function setupDropdowns() {
  diseaseDropdown = new CustomDropdown('diseaseSelect');
  document.getElementById('disease')?.addEventListener('change', () => {
    // Refetch data with filter when disease changes
    fetchData();
    render();
    renderPreventionSteps();
  });
}

// Map Functions
function initMap(center, zoom) {
  const mapElement = document.getElementById('map');
  if (!mapElement) {
    console.error('Map element not found!');
    return;
  }

  // Hide loading indicator
  const loadingDiv = document.getElementById('mapLoading');
  if (loadingDiv) {
    loadingDiv.style.display = 'none';
  }

  try {
    map = L.map('map', { zoomControl: true }).setView([center.lat, center.lon], zoom);

    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
      subdomains: 'abcd',
      maxZoom: 19
    }).addTo(map);

    markersLayer = L.layerGroup().addTo(map);
    console.log('Map initialized successfully');
  } catch (error) {
    console.error('Error initializing map:', error);
    // Show error message on map
    if (loadingDiv) {
      loadingDiv.innerHTML = '<div class="p-4 text-center text-red-400">Error loading map. Please refresh the page.</div>';
      loadingDiv.style.display = 'flex';
    }
  }
}

function refresh() {
  triggerLiveRefresh().finally(() => {
    fetchDiseases().then(() => {
      fetchData();
    });
  });
}

// Filtering and Rendering
function filteredOutbreaks() {
  const diseaseInput = document.getElementById('disease');
  const disease = diseaseInput ? diseaseInput.value : 'all';

  console.log('Filtering outbreaks by disease:', disease, 'Total outbreaks:', diseaseOutbreaks.length);

  if (disease === 'all' || !disease) {
    return diseaseOutbreaks;
  }

  const filtered = diseaseOutbreaks.filter(outbreak => outbreak.disease === disease);
  console.log('Filtered outbreaks:', filtered.length);
  return filtered;
}

// Group outbreaks by disease
function groupOutbreaksByDisease(outbreaks) {
  const grouped = {};

  outbreaks.forEach(outbreak => {
    if (!grouped[outbreak.disease]) {
      grouped[outbreak.disease] = [];
    }
    grouped[outbreak.disease].push(outbreak);
  });

  return grouped;
}

function clearLayers() {
  markersLayer.clearLayers();
}

function render() {
  if (!map || !markersLayer) {
    console.warn('Map not initialized, skipping render');
    return;
  }

  try {
    clearLayers();
    const outbreaks = filteredOutbreaks();

    console.log('Rendering outbreaks:', outbreaks.length, 'Filtered from:', diseaseOutbreaks.length);

    // Show all outbreaks on map
    const grouped = groupOutbreaksByDisease(outbreaks);

    console.log('Grouped diseases:', Object.keys(grouped));

    if (Object.keys(grouped).length === 0) {
      console.log('No outbreaks to display on map');
    }

    // Render each disease group
    Object.keys(grouped).forEach(disease => {
      const diseaseOutbreaks = grouped[disease];
      // Get the original disease name for color lookup
      const originalName = diseaseOutbreaks[0]?.originalName || disease;
      const color = getDiseaseColor(originalName);

      diseaseOutbreaks.forEach(outbreak => {
        // Only plot on map if center and coordinates are valid
        if (!outbreak.center ||
          !outbreak.center.lat ||
          !outbreak.center.lon ||
          outbreak.center.lat === 0 ||
          outbreak.center.lon === 0 ||
          isNaN(outbreak.center.lat) ||
          isNaN(outbreak.center.lon)) {
          console.warn('Skipping outbreak with invalid coordinates:', outbreak);
          return;
        }

        // Ensure radius is valid
        const radius = outbreak.radius || Math.min(Math.max((outbreak.cases || 1) * 50, 20000), 100000);

        // Add colored region (lighter, more transparent)
        L.circle([outbreak.center.lat, outbreak.center.lon], {
          radius: radius,
          color: color,
          weight: 1,
          fillColor: color,
          fillOpacity: 0.08,
          opacity: 0.4
        }).addTo(markersLayer)
          .bindPopup(`
          <div class='text-sm'>
            <div class='font-semibold mb-1 uppercase'>${outbreak.originalName || outbreak.disease}</div>
            <div class='text-gray-300'>${outbreak.region}</div>
            <div class='text-gray-400 mt-1'>Cases: ${outbreak.cases.toLocaleString()}</div>
            ${outbreak.date ? `<div class='text-gray-500 mt-1 text-xs'>Date: ${new Date(outbreak.date).toLocaleDateString()}</div>` : ''}
          </div>
        `);

        // Add small center dot
        L.circleMarker([outbreak.center.lat, outbreak.center.lon], {
          radius: 4,
          color: color,
          weight: 2,
          fillColor: color,
          fillOpacity: 1
        }).addTo(markersLayer);
      });
    });

    updateTrendsChart();
  } catch (error) {
    console.error('Error in render:', error);
  }
}

// Render disease summary list in sidebar
function renderDiseaseList() {
  const diseaseListDiv = document.getElementById('diseaseList');
  diseaseListDiv.innerHTML = '';

  // Group all outbreaks by disease
  const grouped = groupOutbreaksByDisease(diseaseOutbreaks);

  // Create one entry per disease
  Object.keys(grouped).forEach(disease => {
    const diseaseOutbreaksData = grouped[disease];
    const originalName = diseaseOutbreaksData[0]?.originalName || disease;
    const color = getDiseaseColor(originalName);
    const totalCases = diseaseOutbreaksData.reduce((sum, o) => sum + o.cases, 0);

    // Get growth rate from database or calculate from trends
    let trendPercent = 0;
    let isRising = false;

    if (diseaseGrowthRates[disease] !== undefined) {
      // Use growth rate from database
      trendPercent = Math.abs(diseaseGrowthRates[disease]).toFixed(1);
      isRising = diseaseGrowthRates[disease] > 0;
    } else if (trendsData.datasets[disease]) {
      // Calculate from trends data if available
      const data = trendsData.datasets[disease];
      const validData = data.filter(v => v > 0);
      if (validData.length >= 2) {
        const recent = validData.slice(-2);
        trendPercent = recent[0] > 0 ? Math.abs(((recent[1] - recent[0]) / recent[0]) * 100).toFixed(1) : '0';
        isRising = recent[1] > recent[0];
      }
    }

    const item = document.createElement('div');
    item.className = 'py-2 hover:bg-white/5 rounded-lg px-2 -mx-2 transition cursor-pointer';
    item.innerHTML = `
      <div class='flex items-center justify-between mb-1'>
        <div class='flex items-center gap-2'>
          <div class='w-2 h-2 rounded-full flex-shrink-0' style='background:${color}'></div>
          <span class='font-medium uppercase text-xs' title='${originalName}'>${originalName.length > 15 ? originalName.substring(0, 15) + '...' : originalName}</span>
        </div>
        ${trendPercent > 0 ? `
        <div class='flex items-center gap-1 text-xs ${isRising ? 'text-red-400' : 'text-green-400'}'>
          <i class='fas fa-arrow-${isRising ? 'up' : 'down'} text-xs'></i>
          <span>${trendPercent}%</span>
        </div>
        ` : ''}
      </div>
      <div class='text-xs text-gray-400 ml-4'>
        ${diseaseOutbreaksData.length} region${diseaseOutbreaksData.length !== 1 ? 's' : ''} · ${totalCases.toLocaleString()} case${totalCases !== 1 ? 's' : ''}
      </div>
    `;

    diseaseListDiv.appendChild(item);
  });

  if (Object.keys(grouped).length === 0) {
    diseaseListDiv.innerHTML = '<p class="text-xs text-gray-500">No active outbreaks</p>';
  }
}

// Render prevention steps for diseases with rising trends
function renderPreventionSteps() {
  const section = document.getElementById('preventionSection');
  const listDiv = document.getElementById('preventionList');
  if (!section || !listDiv) return;

  listDiv.innerHTML = '';

  const selectedDisease = document.getElementById('disease').value;

  // Find diseases that are rising (using growth rates from database)
  const risingDiseases = [];
  Object.keys(trendsData.datasets).forEach(disease => {
    // If a specific disease is selected and it's not this one, skip
    if (selectedDisease !== 'all' && selectedDisease !== disease) return;

    const data = trendsData.datasets[disease];
    if (!data || data.length === 0) return;

    // Use growth rate from database if available
    if (diseaseGrowthRates[disease] !== undefined && diseaseGrowthRates[disease] > 0) {
      risingDiseases.push({
        disease,
        pct: Math.abs(diseaseGrowthRates[disease]).toFixed(1)
      });
    } else {
      // Fallback: calculate from data
      const validData = data.filter(v => v > 0);
      if (validData.length >= 2) {
        const recent = validData.slice(-2);
        if (recent[1] > recent[0] && recent[0] > 0) {
          const pct = ((recent[1] - recent[0]) / recent[0] * 100).toFixed(1);
          risingDiseases.push({ disease, pct });
        }
      }
    }
  });

  if (risingDiseases.length === 0) {
    section.classList.add('hidden');
    return;
  }

  section.classList.remove('hidden');

  risingDiseases.forEach(({ disease, pct }) => {
    const info = preventionData[disease];
    if (!info) return;
    const outbreak = diseaseOutbreaks.find(o => normalizeDiseaseName(o.originalName) === disease);
    const diseaseName = outbreak?.originalName || disease;
    const color = getDiseaseColor(diseaseName);

    const card = document.createElement('div');
    card.className = 'prevention-card rounded-xl bg-white/5 border border-gray-800 overflow-hidden';
    card.innerHTML = `
      <button type="button" class="prevention-header w-full flex items-center justify-between px-4 py-3 text-left hover:bg-white/5 transition" aria-expanded="false">
        <div class="flex items-center gap-2">
          <i class="fa-solid ${info.icon} text-sm" style="color:${color}"></i>
          <span class="text-sm font-medium">${info.title}</span>
          <span class="text-xs px-2 py-0.5 rounded-full bg-red-500/20 text-red-400 border border-red-500/30 flex items-center gap-1">
            <i class="fa-solid fa-arrow-up text-[10px]"></i>${pct}%
          </span>
        </div>
        <i class="fa-solid fa-chevron-down text-gray-500 text-xs transition-transform prevention-chevron"></i>
      </button>
      <div class="prevention-body hidden px-4 pb-3">
        <ol class="space-y-2 mt-1">
          ${info.steps.map((step, i) => `
            <li class="flex items-start gap-2 text-xs text-gray-300">
              <span class="flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold mt-0.5" style="background:${color}20;color:${color};border:1px solid ${color}40">${i + 1}</span>
              <span>${step}</span>
            </li>
          `).join('')}
        </ol>
      </div>
    `;

    // Toggle expand/collapse
    const header = card.querySelector('.prevention-header');
    const body = card.querySelector('.prevention-body');
    const chevron = card.querySelector('.prevention-chevron');
    header.addEventListener('click', () => {
      const expanded = body.classList.toggle('hidden');
      chevron.style.transform = expanded ? '' : 'rotate(180deg)';
      header.setAttribute('aria-expanded', !expanded);
    });

    listDiv.appendChild(card);
  });
}

// Initialize trends chart
function initTrendsChart() {
  const ctx = document.getElementById('trendsChart');
  if (!ctx) return;

  const selectedDisease = document.getElementById('disease')?.value || 'all';

  // Prepare datasets based on filter
  let datasets = [];

  if (selectedDisease === 'all') {
    // Show all diseases that have data
    Object.keys(trendsData.datasets).forEach(disease => {
      const data = trendsData.datasets[disease];
      if (data && data.length > 0 && data.some(v => v > 0)) {
        // Get disease name from outbreaks or use normalized name
        const outbreak = diseaseOutbreaks.find(o => normalizeDiseaseName(o.originalName) === disease);
        const diseaseName = outbreak?.originalName || disease;
        const color = getDiseaseColor(diseaseName);

        datasets.push({
          label: diseaseName,
          data: data,
          borderColor: color,
          backgroundColor: color + '20',
          borderWidth: 2,
          tension: 0.4,
          fill: true
        });
      }
    });
  } else {
    // Show only selected disease
    const data = trendsData.datasets[selectedDisease];
    if (data && data.length > 0) {
      const outbreak = diseaseOutbreaks.find(o => normalizeDiseaseName(o.originalName) === selectedDisease);
      const diseaseName = outbreak?.originalName || selectedDisease;
      const color = getDiseaseColor(diseaseName);

      datasets.push({
        label: diseaseName,
        data: data,
        borderColor: color,
        backgroundColor: color + '20',
        borderWidth: 3,
        tension: 0.4,
        fill: true
      });
    }
  }

  trendsChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: trendsData.labels,
      datasets: datasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          position: 'top',
          labels: {
            color: '#9ca3af',
            font: {
              size: 11
            },
            usePointStyle: true,
            padding: 15
          }
        },
        tooltip: {
          backgroundColor: '#1f2937',
          titleColor: '#f3f4f6',
          bodyColor: '#d1d5db',
          borderColor: '#374151',
          borderWidth: 1,
          padding: 10,
          displayColors: true
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          grid: {
            color: '#374151',
            drawBorder: false
          },
          ticks: {
            color: '#9ca3af',
            font: {
              size: 10
            }
          },
          title: {
            display: true,
            text: 'Total Cases',
            color: '#9ca3af',
            font: {
              size: 11
            }
          }
        },
        x: {
          grid: {
            color: '#374151',
            drawBorder: false
          },
          ticks: {
            color: '#9ca3af',
            font: {
              size: 10
            }
          }
        }
      }
    }
  });
}

// Update trends chart based on filter
function updateTrendsChart() {
  const ctx = document.getElementById('trendsChart');
  if (!ctx) return;

  const selectedDisease = document.getElementById('disease')?.value || 'all';
  let datasets = [];

  if (selectedDisease === 'all') {
    // Show all diseases that have data
    Object.keys(trendsData.datasets).forEach(disease => {
      const data = trendsData.datasets[disease];
      if (data && data.length > 0 && data.some(v => v > 0)) {
        const outbreak = diseaseOutbreaks.find(o => normalizeDiseaseName(o.originalName) === disease);
        const diseaseName = outbreak?.originalName || disease;
        const color = getDiseaseColor(diseaseName);

        datasets.push({
          label: diseaseName,
          data: data,
          borderColor: color,
          backgroundColor: color + '20',
          borderWidth: 2,
          tension: 0.4,
          fill: true
        });
      }
    });
  } else {
    // Show only selected disease
    const data = trendsData.datasets[selectedDisease];
    if (data && data.length > 0) {
      const outbreak = diseaseOutbreaks.find(o => normalizeDiseaseName(o.originalName) === selectedDisease);
      const diseaseName = outbreak?.originalName || selectedDisease;
      const color = getDiseaseColor(diseaseName);

      datasets.push({
        label: diseaseName,
        data: data,
        borderColor: color,
        backgroundColor: color + '20',
        borderWidth: 3,
        tension: 0.4,
        fill: true
      });
    }
  }

  // If chart doesn't exist, create it
  if (!trendsChart) {
    trendsChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: trendsData.labels,
        datasets: datasets
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: true,
            position: 'top',
            labels: {
              color: '#9ca3af',
              font: {
                size: 11
              },
              usePointStyle: true,
              padding: 15
            }
          },
          tooltip: {
            backgroundColor: '#1f2937',
            titleColor: '#f3f4f6',
            bodyColor: '#d1d5db',
            borderColor: '#374151',
            borderWidth: 1,
            padding: 10,
            displayColors: true
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            grid: {
              color: '#374151',
              drawBorder: false
            },
            ticks: {
              color: '#9ca3af',
              font: {
                size: 10
              }
            },
            title: {
              display: true,
              text: 'Total Cases',
              color: '#9ca3af',
              font: {
                size: 11
              }
            }
          },
          x: {
            grid: {
              color: '#374151',
              drawBorder: false
            },
            ticks: {
              color: '#9ca3af',
              font: {
                size: 10
              }
            }
          }
        }
      }
    });
  } else {
    // Update existing chart
    trendsChart.data.labels = trendsData.labels;
    trendsChart.data.datasets = datasets;
    trendsChart.update();
  }

  console.log('Chart updated with', datasets.length, 'datasets');
}

function renderBulletins() {
  const bulletinsDiv = document.getElementById('bulletins');
  bulletinsDiv.innerHTML = '';

  if (healthBulletins.length === 0) {
    bulletinsDiv.innerHTML = '<p class="text-xs text-gray-500">No bulletins available.</p>';
    return;
  }

  healthBulletins.forEach(bulletin => {
    const hasUrl = bulletin.url && bulletin.url.trim() && bulletin.url !== '#';
    // If URL exists, use it; otherwise build a Google search fallback
    const linkUrl = hasUrl
      ? bulletin.url
      : `https://www.google.com/search?q=${encodeURIComponent(bulletin.title + ' health bulletin India')}`;

    const bulletinEl = document.createElement('a');
    bulletinEl.href = linkUrl;
    bulletinEl.target = '_blank';
    bulletinEl.rel = 'noopener noreferrer';
    bulletinEl.className = 'block p-3 rounded-lg bg-white/5 border border-gray-700 hover:bg-white/10 transition cursor-pointer';
    bulletinEl.innerHTML = `
      <div class='flex items-start justify-between gap-2 mb-1'>
        <h4 class='font-medium text-sm text-blue-300'>${bulletin.title}</h4>
        <i class='fa-solid ${hasUrl ? 'fa-arrow-up-right-from-square' : 'fa-magnifying-glass'} text-gray-500 text-xs flex-shrink-0 mt-1' title='${hasUrl ? 'Open source' : 'Search online'}'></i>
      </div>
      <p class='text-xs text-gray-400 mb-2 line-clamp-2'>${bulletin.summary || 'No additional details available.'}</p>
      <div class='flex items-center gap-3 text-xs text-gray-500'>
        ${bulletin.date ? `<span><i class='fa-solid fa-calendar mr-1'></i>${formatDate(bulletin.date)}</span>` : ''}
        <span><i class='fa-solid fa-building mr-1'></i>${bulletin.source || 'Health Authority'}</span>
        ${!hasUrl ? `<span class='text-blue-400/60'><i class='fa-solid fa-magnifying-glass mr-1'></i>Search</span>` : ''}
      </div>
    `;
    bulletinsDiv.appendChild(bulletinEl);
  });
}

function formatDate(dateStr) {
  const date = new Date(dateStr);
  const options = { month: 'short', day: 'numeric', year: 'numeric' };
  return date.toLocaleDateString('en-US', options);
}
