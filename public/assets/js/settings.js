/**
 * Settings Page JavaScript
 * Handles theme switching and settings management
 */

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  loadSettings();
  setupEventListeners();
  applyTheme();
});

function setupEventListeners() {
  // Theme toggle
  document.getElementById('themeToggle')?.addEventListener('click', toggleTheme);
  
  // Toggle switches
  document.querySelectorAll('.toggle-switch').forEach(toggle => {
    toggle.addEventListener('click', function() {
      this.classList.toggle('active');
      const setting = this.getAttribute('data-setting');
      saveSetting(setting, this.classList.contains('active'));
    });
  });
  
  // Language select
  document.getElementById('languageSelect')?.addEventListener('change', function() {
    saveSetting('language', this.value);
  });
  
  // Save button
  document.getElementById('saveSettings')?.addEventListener('click', saveAllSettings);
}

function toggleTheme() {
  const currentTheme = StorageService.get('theme', 'dark');
  const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
  
  StorageService.set('theme', newTheme);
  applyTheme();
  updateThemeUI();
  
  // Show success message
  showNotification('Theme changed successfully');
}

function applyTheme() {
  const theme = StorageService.get('theme', 'dark');
  
  if (theme === 'light') {
    document.body.classList.add('light-theme');
  } else {
    document.body.classList.remove('light-theme');
  }
}

function updateThemeUI() {
  const theme = StorageService.get('theme', 'dark');
  const toggle = document.getElementById('themeToggle');
  const icon = document.getElementById('themeToggleIcon');
  const currentThemeText = document.getElementById('currentTheme');
  
  if (theme === 'light') {
    toggle?.classList.add('bg-blue-600');
    toggle?.classList.remove('bg-gray-700');
    if (icon) {
      icon.innerHTML = '<i class="fa-solid fa-sun text-yellow-500 text-xs flex items-center justify-center h-full"></i>';
      icon.classList.add('translate-x-7');
      icon.classList.remove('translate-x-1');
    }
    if (currentThemeText) currentThemeText.textContent = 'Light';
  } else {
    toggle?.classList.remove('bg-blue-600');
    toggle?.classList.add('bg-gray-700');
    if (icon) {
      icon.innerHTML = '<i class="fa-solid fa-moon text-gray-900 text-xs flex items-center justify-center h-full"></i>';
      icon.classList.remove('translate-x-7');
      icon.classList.add('translate-x-1');
    }
    if (currentThemeText) currentThemeText.textContent = 'Dark';
  }
}

function loadSettings() {
  // Load theme
  updateThemeUI();
  
  // Load notification settings
  const outbreakAlerts = StorageService.get('outbreakAlerts', true);
  const healthBulletins = StorageService.get('healthBulletins', true);
  
  const outbreakToggle = document.querySelector('[data-setting="outbreakAlerts"]');
  const bulletinToggle = document.querySelector('[data-setting="healthBulletins"]');
  
  if (outbreakToggle && !outbreakAlerts) {
    outbreakToggle.classList.remove('active');
  }
  
  if (bulletinToggle && !healthBulletins) {
    bulletinToggle.classList.remove('active');
  }
  
  // Load language
  const language = StorageService.get('language', 'en');
  const languageSelect = document.getElementById('languageSelect');
  if (languageSelect) {
    languageSelect.value = language;
  }
}

function saveSetting(key, value) {
  StorageService.set(key, value);
}

function saveAllSettings() {
  showNotification('Settings saved successfully');
}

function showNotification(message) {
  // Create notification element
  const notification = document.createElement('div');
  notification.className = 'fixed top-20 right-4 z-50 px-4 py-3 rounded-lg bg-green-600 text-white shadow-lg animate-fade-in';
  notification.innerHTML = `
    <div class="flex items-center gap-2">
      <i class="fa-solid fa-check-circle"></i>
      <span>${message}</span>
    </div>
  `;
  
  document.body.appendChild(notification);
  
  // Remove after 3 seconds
  setTimeout(() => {
    notification.classList.add('animate-fade-out');
    setTimeout(() => notification.remove(), 300);
  }, 3000);
}
