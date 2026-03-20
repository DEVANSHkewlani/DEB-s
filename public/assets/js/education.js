/**
 * Education Page JavaScript
 * Handles video library, blogs, schemes, AI summaries, and resource reporting
 */

// Sample data
// State
let videosData = [];
let blogsData = [];
let schemesData = [];
let selectedResource = null;
let currentFilter = 'all';

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  fetchResources();
  setupEventListeners();
  setupDropdowns();
});

async function fetchResources() {
  try {
    // Get current filter from global state or UI (UI dropdown usually sets global state 'currentFilter')
    // But here currentFilter is updated by setupDropdowns likely.
    // The previous implementation fetched ALL then filtered client side.
    // Requirement: "in education make the filter by content type working"
    // The current code fetches all and filters in renderAllContent.
    // However, if we want to use backend filtering or just fix client filtering:
    // alerts.js has logic, let's look at education.js
    // modify fetchResources to take an arg or use currentFilter?
    // Let's stick to client side filtering if the backend returns all, OR pass param.
    // The backend endpoint `get_resources` DOES accept `type`.
    // Let's update fetchResources to use the backend filter for efficiency or just ensuring it works.

    // Map frontend filter keys to backend filter values
    // 'blog' filter should fetch both blog and article types
    let backendType = currentFilter;
    if (currentFilter === 'blog') backendType = null; // fetch all, filter client-side for blog+article
    const typeParam = (backendType && backendType !== 'all') ? `?type=${backendType}` : '';
    const response = await fetch(`/api/v1/education${typeParam}`);
    if (!response.ok) throw new Error('Failed to fetch resources');

    const resources = await response.json();

    // Categorize resources
    videosData = resources.filter(r => r.type === 'video');
    blogsData = resources.filter(r => r.type === 'blog' || r.type === 'article');
    schemesData = resources.filter(r => r.type === 'scheme');

    // Note: If DB is empty, you might want to keep the dummy data as fallback or just show empty state
    // For this implementation, I'm assuming we rely on the API. 
    // If API returns empty, UI checks length.

    renderAllContent();

  } catch (error) {
    console.error('Error loading resources:', error);
    // Fallback to sample data if API fails (optional, good for dev)
    // For now, let's show an alert or handle error gracefully in UI
    document.getElementById('videos').innerHTML = '<div class="col-span-full text-center text-gray-500 py-10">Failed to load resources. Is backend running?</div>';
  }
}

// Setup filter buttons
function setupDropdowns() {
  const buttons = {
    'filterAll': 'all',
    'filterVideos': 'video',
    'filterBlogs': 'blog',
    'filterSchemes': 'scheme'
  };

  Object.entries(buttons).forEach(([id, type]) => {
    const btn = document.getElementById(id);
    if (!btn) return;

    btn.addEventListener('click', () => {
      // Update state
      currentFilter = type;

      // Update UI
      document.querySelectorAll('.filter-btn').forEach(b => {
        b.classList.remove('active', 'bg-blue-600', 'border-blue-500');
        b.classList.add('bg-white/10', 'border-gray-700');
      });
      btn.classList.remove('bg-white/10', 'border-gray-700');
      btn.classList.add('active', 'bg-blue-600', 'border-blue-500');

      // Update result status
      const statusEl = document.getElementById('resultStatus');
      if (statusEl) statusEl.textContent = `Showing: ${type === 'all' ? 'All content' : btn.textContent.trim()}`;

      // Re-fetch resources with new filter
      fetchResources();
    });
  });
}

// Setup event listeners for report panel, language dropdown, etc.
function setupEventListeners() {
  // Report Missing Resource panel
  document.getElementById('reportMissingTop')?.addEventListener('click', openReportPanel);
  document.getElementById('rmClose')?.addEventListener('click', closeReportPanel);
  document.getElementById('rmCancel')?.addEventListener('click', closeReportPanel);
  document.getElementById('rmOverlay')?.addEventListener('click', closeReportPanel);
  document.getElementById('rmForm')?.addEventListener('submit', handleReportSubmit);

  // Copy summary button
  document.getElementById('copySummary')?.addEventListener('click', () => copyToClipboard('summary'));

  // Language dropdown
  const langContainer = document.getElementById('langSelect');
  if (langContainer) {
    const langBtn = langContainer.querySelector('button');
    const langPanel = langContainer.querySelector('div.absolute, div.hidden');
    const langInput = document.getElementById('lang');
    const langLabel = document.getElementById('langLabel');

    if (langBtn && langPanel) {
      langBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        langPanel.classList.toggle('hidden');
        const chevron = langBtn.querySelector('i');
        if (chevron) chevron.style.transform = langPanel.classList.contains('hidden') ? '' : 'rotate(180deg)';
      });

      langPanel.querySelectorAll('button[data-value]').forEach(opt => {
        opt.addEventListener('click', () => {
          if (langInput) langInput.value = opt.getAttribute('data-value');
          if (langLabel) langLabel.textContent = opt.getAttribute('data-label') || opt.textContent.trim();
          langPanel.classList.add('hidden');
          const chevron = langBtn.querySelector('i');
          if (chevron) chevron.style.transform = '';
        });
      });

      // Close on outside click
      document.addEventListener('click', (e) => {
        if (!langContainer.contains(e.target)) {
          langPanel.classList.add('hidden');
          const chevron = langBtn.querySelector('i');
          if (chevron) chevron.style.transform = '';
        }
      });
    }
  }

  // Report type dropdown (inside report panel)
  const rmTypeContainer = document.getElementById('rmTypeSelect');
  if (rmTypeContainer) {
    const rmTypeBtn = rmTypeContainer.querySelector('button');
    const rmTypePanel = rmTypeContainer.querySelector('div.absolute, div.hidden');
    const rmTypeInput = document.getElementById('rmType');
    const rmTypeLabel = document.getElementById('rmTypeLabel');

    if (rmTypeBtn && rmTypePanel) {
      rmTypeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        rmTypePanel.classList.toggle('hidden');
      });

      rmTypePanel.querySelectorAll('button[data-value]').forEach(opt => {
        opt.addEventListener('click', () => {
          if (rmTypeInput) rmTypeInput.value = opt.getAttribute('data-value');
          if (rmTypeLabel) rmTypeLabel.textContent = opt.getAttribute('data-label') || opt.textContent.trim();
          rmTypePanel.classList.add('hidden');
        });
      });

      document.addEventListener('click', (e) => {
        if (!rmTypeContainer.contains(e.target)) {
          rmTypePanel.classList.add('hidden');
        }
      });
    }
  }
}

// AI Summary Generation
async function generateSummary() {
  if (!selectedResource) return;

  const lang = document.getElementById('lang').value;
  const summaryEl = document.getElementById('summary');
  const btn = document.getElementById('btnGenerate');

  summaryEl.value = 'Generating summary with AI...';
  btn.disabled = true;

  try {
    // Check if summary for this language is already cached/stored in selectedResource (if configured backend to return it)
    // For now we always request fresh or utilize retrieval logic backend side

    const response = await fetch('http://localhost:8000/api/v1/education/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        resourceId: String(selectedResource.id),
        type: selectedResource.type,
        language: lang,
        content: selectedResource.summary || selectedResource.excerpt // context hint
      })
    });

    if (!response.ok) throw new Error('Generation failed');

    const data = await response.json();
    summaryEl.value = data.summary;

  } catch (error) {
    console.error(error);
    summaryEl.value = 'Error generating summary. Please try again.';
  } finally {
    btn.disabled = false;
  }
}

function copyToClipboard(elementId) {
  const element = document.getElementById(elementId);
  if (element && element.value) {
    navigator.clipboard.writeText(element.value).then(() => {
      const btn = document.getElementById(`copy${elementId.charAt(0).toUpperCase() + elementId.slice(1)}`);
      const originalText = btn.innerHTML;
      btn.innerHTML = '<i class="fa-solid fa-check mr-1"></i>Copied!';
      setTimeout(() => {
        btn.innerHTML = originalText;
      }, 2000);
    });
  }
}

// Report Panel
function openReportPanel() {
  const searchValue = document.getElementById('search').value.trim();
  document.getElementById('rmTopic').value = searchValue;
  document.getElementById('rmOverlay').classList.remove('hidden');
  document.getElementById('rmPanel').classList.remove('translate-x-full');
}

function closeReportPanel() {
  document.getElementById('rmOverlay').classList.add('hidden');
  document.getElementById('rmPanel').classList.add('translate-x-full');
}

async function handleReportSubmit(e) {
  e.preventDefault();

  const required = ['rmTopic', 'rmDetails', 'rmConsent'];
  for (const id of required) {
    const el = document.getElementById(id);
    if ((el.type === 'checkbox' && !el.checked) || (!el.value || el.value.trim() === '')) {
      el.focus();
      el.classList.add('border-red-600');
      setTimeout(() => el.classList.remove('border-red-600'), 1200);
      return;
    }
  }

  const payload = {
    topic: document.getElementById('rmTopic').value,
    rtype: document.getElementById('rmType').value,
    details: document.getElementById('rmDetails').value,
    contact: document.getElementById('rmContact').value || null,
    consent: document.getElementById('rmConsent').checked
  };

  try {
    const response = await fetch('/api/v1/education/report_missing', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (response.ok) {
      document.getElementById('rmSuccess').classList.remove('hidden');
      setTimeout(() => {
        document.getElementById('rmSuccess').classList.add('hidden');
        closeReportPanel();
        document.getElementById('rmForm').reset();
      }, 1200);
    } else {
      alert("Failed to submit report. Please try again.");
    }
  } catch (error) {
    console.error("Error submitting report:", error);
    alert("Error submitting report.");
  }
}
// Render all content types
function renderAllContent() {
  const filter = currentFilter;

  // Videos
  const vSection = document.getElementById('videosSection');
  const videosContainer = document.getElementById('videos');
  const vCount = document.getElementById('vcount');

  if (filter === 'all' || filter === 'video') {
    vSection.classList.remove('hidden');
    // Filter by search AND valid YouTube URL
    const videos = filterResources(videosData).filter(v => getYouTubeID(v.url));
    vCount.textContent = videos.length;

    videosContainer.innerHTML = videos.map(v => `
      <div class="video-card glass rounded-xl overflow-hidden cursor-pointer hover:bg-white/5 transition group" onclick="selectResource(${v.id}, 'video')">
        <div class="relative aspect-video bg-gray-900">
          <img src="${v.thumb || `https://img.youtube.com/vi/${getYouTubeID(v.url)}/hqdefault.jpg`}" alt="${v.title}" class="w-full h-full object-cover opacity-80 group-hover:opacity-100 transition">
          <div class="absolute inset-0 flex items-center justify-center">
            <div class="w-12 h-12 rounded-full bg-blue-600/80 flex items-center justify-center backdrop-blur group-hover:scale-110 transition">
              <i class="fa-solid fa-play text-white ml-1"></i>
            </div>
          </div>
          <div class="absolute bottom-2 right-2 px-2 py-1 rounded bg-black/80 text-xs font-medium">
            ${v.duration || 'Video'}
          </div>
        </div>
        <div class="p-3">
          <h3 class="font-medium text-sm line-clamp-2 leading-tight mb-1">${v.title}</h3>
          <p class="text-xs text-gray-400 line-clamp-1">${v.excerpt || 'No description available'}</p>
        </div>
      </div>
    `).join('');

    if (videos.length === 0) videosContainer.innerHTML = '<div class="col-span-full text-center text-gray-500 py-4">No videos found</div>';
  } else {
    vSection.classList.add('hidden');
  }

  // Blogs
  const bSection = document.getElementById('blogsSection');
  const blogsContainer = document.getElementById('blogs');

  if (filter === 'all' || filter === 'blog') {
    bSection.classList.remove('hidden');
    const blogs = filterResources(blogsData);

    blogsContainer.innerHTML = blogs.map(b => `
      <div class="p-4 rounded-xl bg-white/5 border border-gray-700 hover:bg-white/10 transition cursor-pointer flex gap-4" onclick="selectResource(${b.id}, 'blog')">
        <div class="w-16 h-16 rounded-lg bg-gray-800 flex-shrink-0 flex items-center justify-center text-2xl text-gray-600">
          <i class="fa-solid fa-file-lines"></i>
        </div>
        <div>
          <h3 class="font-medium text-sm mb-1 text-blue-300">${b.title}</h3>
          <p class="text-xs text-gray-400 line-clamp-2">${b.excerpt || b.summary || 'Click to read more...'}</p>
        </div>
      </div>
    `).join('');

    if (blogs.length === 0) blogsContainer.innerHTML = '<div class="text-center text-gray-500 py-4">No blogs found</div>';
  } else {
    bSection.classList.add('hidden');
  }

  // Schemes
  const sSection = document.getElementById('schemesSection');
  const schemesContainer = document.getElementById('schemes');

  if (filter === 'all' || filter === 'scheme') {
    sSection.classList.remove('hidden');
    const schemes = filterResources(schemesData);

    schemesContainer.innerHTML = schemes.map(s => `
      <div class="p-4 rounded-xl bg-white/5 border border-gray-700 hover:bg-white/10 transition cursor-pointer flex gap-4" onclick="selectResource(${s.id}, 'scheme')">
        <div class="w-16 h-16 rounded-lg bg-gray-800 flex-shrink-0 flex items-center justify-center text-2xl text-gray-600">
          <i class="fa-solid fa-landmark"></i>
        </div>
        <div>
          <h3 class="font-medium text-sm mb-1 text-green-400">${s.title}</h3>
          <p class="text-xs text-gray-400 line-clamp-2">${s.excerpt || 'Government health scheme details'}</p>
        </div>
      </div>
    `).join('');

    if (schemes.length === 0) schemesContainer.innerHTML = '<div class="text-center text-gray-500 py-4">No schemes found</div>';
  } else {
    sSection.classList.add('hidden');
  }
}

// Select a resource to preview
window.selectResource = function (id, type) {
  let resource;
  if (type === 'video') resource = videosData.find(r => r.id === id);
  else if (type === 'blog') resource = blogsData.find(r => r.id === id);
  else if (type === 'scheme') resource = schemesData.find(r => r.id === id);

  if (!resource) return;

  selectedResource = resource;

  // Update Preview Pane
  const playerBox = document.getElementById('playerBox');

  if (type === 'video') {
    const videoId = getYouTubeID(resource.url);
    if (videoId) {
      playerBox.innerHTML = `<iframe width="100%" height="100%" src="https://www.youtube.com/embed/${videoId}?autoplay=1" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>`;
    } else {
      playerBox.innerHTML = `<div class="p-4 text-center"><i class="fa-solid fa-play-circle text-4xl mb-2 text-gray-500"></i><p>Video not playable in preview</p></div>`;
    }
  } else {
    // For blogs/schemes show icon or thumb
    playerBox.innerHTML = `
      <div class="flex flex-col items-center justify-center h-full p-6 text-center">
        <i class="fa-solid ${type === 'scheme' ? 'fa-landmark' : 'fa-file-alt'} text-5xl mb-4 text-gray-600"></i>
        <h3 class="text-lg font-semibold">${resource.title}</h3>
        <p class="text-xs text-gray-400 mt-2">Click 'Visit Source' to view full content</p>
      </div>
    `;
  }

  // Show source link
  const sourceLink = document.getElementById('sourceLink');
  const sourceBtn = document.getElementById('sourceLinkBtn');
  sourceLink.classList.remove('hidden');
  sourceBtn.href = resource.url;

  // Enable generate button
  document.getElementById('btnGenerate').disabled = false;
  document.getElementById('summary').value = resource.summary || '';

  // Scroll to preview on mobile
  if (window.innerWidth < 1024) {
    playerBox.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
};

function filterResources(list) {
  const search = document.getElementById('search').value.toLowerCase();

  return list.filter(item => {
    const matchesSearch = !search ||
      item.title.toLowerCase().includes(search) ||
      (item.excerpt && item.excerpt.toLowerCase().includes(search)) ||
      (item.tags && item.tags.some(t => t.toLowerCase().includes(search))) ||
      (item.disease_tags && item.disease_tags.some(t => t.toLowerCase().includes(search)));

    return matchesSearch;
  });
}

function getYouTubeID(url) {
  if (!url) return null;
  const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|&v=)([^#&?]*).*/;
  const match = url.match(regExp);
  return (match && match[2].length === 11) ? match[2] : null;
}

// Add event listener for search
document.getElementById('search')?.addEventListener('input', () => {
  renderAllContent();
});

// Add event listener for generate button
document.getElementById('btnGenerate')?.addEventListener('click', generateSummary);
