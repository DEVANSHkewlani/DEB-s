/**
 * Common JavaScript Utilities
 * Shared functions across all pages
 */

// Geolocation Service
const GeolocationService = {
  async getCurrentPosition() {
    return new Promise((resolve) => {
      if (!('geolocation' in navigator)) {
        resolve(null);
        return;
      }
      
      navigator.geolocation.getCurrentPosition(
        (position) => resolve({
          lat: position.coords.latitude,
          lon: position.coords.longitude
        }),
        () => resolve(null),
        {
          enableHighAccuracy: true,
          timeout: 8000,
          maximumAge: 60000
        }
      );
    });
  }
};

// Local Storage Service
const StorageService = {
  set(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
      return true;
    } catch (error) {
      console.error('Storage error:', error);
      return false;
    }
  },
  
  get(key, defaultValue = null) {
    try {
      const item = localStorage.getItem(key);
      return item ? JSON.parse(item) : defaultValue;
    } catch (error) {
      console.error('Storage error:', error);
      return defaultValue;
    }
  },
  
  remove(key) {
    try {
      localStorage.removeItem(key);
      return true;
    } catch (error) {
      console.error('Storage error:', error);
      return false;
    }
  },
  
  clear() {
    try {
      localStorage.clear();
      return true;
    } catch (error) {
      console.error('Storage error:', error);
      return false;
    }
  }
};

// Utility Functions
const Utils = {
  // Distance calculation (Haversine formula)
  calculateDistance(point1, point2) {
    const R = 6371e3; // Earth radius in meters
    const toRad = (deg) => deg * Math.PI / 180;
    
    const dLat = toRad(point2.lat - point1.lat);
    const dLon = toRad(point2.lon - point1.lon);
    const lat1 = toRad(point1.lat);
    const lat2 = toRad(point2.lat);
    
    const a = Math.sin(dLat / 2) ** 2 +
              Math.cos(lat1) * Math.cos(lat2) *
              Math.sin(dLon / 2) ** 2;
    
    return 2 * R * Math.asin(Math.sqrt(a));
  },
  
  // Format distance
  formatDistance(meters) {
    const km = meters / 1000;
    return km < 1 ? `${Math.round(meters)} m` : `${km.toFixed(1)} km`;
  },
  
  // Format time
  formatTime(minutes) {
    if (minutes < 60) {
      return `${Math.max(1, Math.round(minutes))} min`;
    }
    const hours = minutes / 60;
    return `${hours.toFixed(hours < 2 ? 1 : 0)} hr`;
  },
  
  // Debounce function
  debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  },
  
  // Show loading spinner
  showLoading(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
      element.innerHTML = '<div class="spinner"></div>';
    }
  },
  
  // Hide loading spinner
  hideLoading(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
      element.innerHTML = '';
    }
  },
  
  // Show error message
  showError(message, elementId = 'errorContainer') {
    const container = document.getElementById(elementId);
    if (container) {
      container.innerHTML = `
        <div class="error-message fade-in">
          <i class="fas fa-exclamation-circle"></i>
          <span>${message}</span>
        </div>
      `;
      setTimeout(() => {
        container.innerHTML = '';
      }, 5000);
    }
  },
  
  // Show success message
  showSuccess(message, elementId = 'successContainer') {
    const container = document.getElementById(elementId);
    if (container) {
      container.innerHTML = `
        <div class="success-message fade-in">
          <i class="fas fa-check-circle"></i>
          <span>${message}</span>
        </div>
      `;
      setTimeout(() => {
        container.innerHTML = '';
      }, 5000);
    }
  },
  
  // Validate email
  isValidEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
  },
  
  // Validate phone
  isValidPhone(phone) {
    const re = /^[6-9]\d{9}$/; // Indian phone number
    return re.test(phone.replace(/\s+/g, ''));
  },
  
  // Format date
  formatDate(date) {
    return new Date(date).toLocaleDateString('en-IN', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  },
  
  // Format time
  formatDateTime(date) {
    return new Date(date).toLocaleString('en-IN', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  }
};

// Custom Dropdown Component
class CustomDropdown {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    if (!this.container) return;
    
    this.hiddenInput = this.container.querySelector('input[type="hidden"]');
    this.trigger = this.container.querySelector('button');
    this.labelSpan = this.trigger.querySelector('span');
    this.chevron = this.trigger.querySelector('.fa-chevron-down');
    this.panel = this.container.querySelector('div.absolute, div.dropdown-panel');
    
    this.init();
  }
  
  init() {
    // Toggle dropdown
    this.trigger.addEventListener('click', (e) => {
      e.stopPropagation();
      this.toggle();
    });
    
    // Select option
    this.panel.querySelectorAll('button[data-value]').forEach(btn => {
      btn.addEventListener('click', () => {
        this.select(
          btn.getAttribute('data-value'),
          btn.getAttribute('data-label') || btn.textContent.trim()
        );
      });
    });
    
    // Close on outside click
    document.addEventListener('click', (e) => {
      if (!this.container.contains(e.target)) {
        this.close();
      }
    });
  }
  
  toggle() {
    const isOpen = !this.panel.classList.contains('hidden');
    if (isOpen) {
      this.close();
    } else {
      this.open();
    }
  }
  
  open() {
    this.panel.classList.remove('hidden');
    if (this.chevron) {
      this.chevron.classList.add('rotate-180');
    }
  }
  
  close() {
    this.panel.classList.add('hidden');
    if (this.chevron) {
      this.chevron.classList.remove('rotate-180');
    }
  }
  
  select(value, label) {
    this.hiddenInput.value = value;
    this.labelSpan.textContent = label;
    this.close();
    
    // Trigger change event
    this.hiddenInput.dispatchEvent(new Event('change'));
  }
  
  getValue() {
    return this.hiddenInput.value;
  }
  
  setValue(value, label) {
    this.select(value, label);
  }
}

// Language Dropdown Handler
function initLanguageDropdown() {
  const langToggleBtn = document.getElementById('langToggleBtn');
  const languageDropdown = document.getElementById('languageDropdown');
  const languageSearch = document.getElementById('languageSearch');
  const languageList = document.getElementById('languageList');
  const selectedLang = document.getElementById('selectedLang');
  
  if (!langToggleBtn || !languageDropdown) return;
  
  // Toggle dropdown
  langToggleBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    languageDropdown.classList.toggle('hidden');
    if (!languageDropdown.classList.contains('hidden')) {
      languageSearch?.focus();
    }
  });
  
  // Close dropdown when clicking outside
  document.addEventListener('click', (e) => {
    if (!document.getElementById('langWrapper')?.contains(e.target)) {
      languageDropdown.classList.add('hidden');
    }
  });
  
  // Search functionality
  if (languageSearch) {
    languageSearch.addEventListener('input', (e) => {
      const searchTerm = e.target.value.toLowerCase();
      const items = languageList.querySelectorAll('.language-item');
      
      items.forEach(item => {
        const langData = item.getAttribute('data-lang').toLowerCase();
        const text = item.textContent.toLowerCase();
        if (langData.includes(searchTerm) || text.includes(searchTerm)) {
          item.style.display = 'block';
        } else {
          item.style.display = 'none';
        }
      });
    });
  }
  
  // Language selection
  const languageItems = languageList.querySelectorAll('.language-item');
  languageItems.forEach(item => {
    item.addEventListener('click', () => {
      const langName = item.textContent.split('(')[0].trim();
      const langCode = item.getAttribute('data-code');
      
      selectedLang.textContent = langName;
      languageDropdown.classList.add('hidden');
      
      // Store selected language
      StorageService.set('selectedLanguage', { name: langName, code: langCode });
      
      // Reset search
      if (languageSearch) {
        languageSearch.value = '';
        languageItems.forEach(i => i.style.display = 'block');
      }
    });
  });
  
  // Load saved language
  const savedLang = StorageService.get('selectedLanguage');
  if (savedLang) {
    selectedLang.textContent = savedLang.name;
  }
}

// Initialize language dropdown on page load
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initLanguageDropdown);
} else {
  initLanguageDropdown();
}

// Export for use in other files
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    GeolocationService,
    StorageService,
    Utils,
    CustomDropdown,
    initLanguageDropdown
  };
}


/**
 * Theme Management
 * Apply theme on page load
 */
(function initTheme() {
  const theme = StorageService.get('theme', 'dark');
  if (theme === 'light') {
    document.body.classList.add('light-theme');
  }
})();
