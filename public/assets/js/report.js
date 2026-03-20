/**
 * Report Page JavaScript
 * Handles health report submission form
 */

// Notification function
function showNotification(message, type = 'success') {
  // Remove existing notification if any
  const existing = document.getElementById('toastNotification');
  if (existing) {
    existing.remove();
  }

  const notification = document.createElement('div');
  notification.id = 'toastNotification';
  notification.className = `fixed top-20 right-4 z-50 px-6 py-4 rounded-xl shadow-2xl border backdrop-blur-md transition-all transform translate-x-0 opacity-100 ${
    type === 'success' 
      ? 'bg-green-900/90 border-green-700 text-green-100' 
      : 'bg-red-900/90 border-red-700 text-red-100'
  }`;
  
  notification.innerHTML = `
    <div class="flex items-center gap-3">
      <i class="fa-solid ${type === 'success' ? 'fa-circle-check' : 'fa-circle-exclamation'} text-xl"></i>
      <div>
        <p class="font-semibold">${message}</p>
        <p class="text-xs opacity-80 mt-0.5">Your report has been saved successfully.</p>
      </div>
      <button onclick="this.parentElement.parentElement.remove()" class="ml-4 text-current opacity-70 hover:opacity-100">
        <i class="fa-solid fa-times"></i>
      </button>
    </div>
  `;

  document.body.appendChild(notification);

  // Auto remove after 5 seconds
  setTimeout(() => {
    notification.style.transform = 'translateX(400px)';
    notification.style.opacity = '0';
    setTimeout(() => notification.remove(), 300);
  }, 5000);
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  setupEventListeners();
  setupDropdowns();
});

function setupEventListeners() {
  document.getElementById('reportForm')?.addEventListener('submit', handleSubmit);
}

function setupDropdowns() {
  new CustomDropdown('reportTypeSelect');
  new CustomDropdown('severitySelect');
}

async function handleSubmit(e) {
  e.preventDefault();

  // Validate required fields
  const required = ['reportType', 'location', 'details', 'consent'];
  for (const id of required) {
    const el = document.getElementById(id);
    if ((el.type === 'checkbox' && !el.checked) || (!el.value || el.value.trim() === '')) {
      el.focus();
      el.classList.add('border-red-600');
      setTimeout(() => el.classList.remove('border-red-600'), 1200);
      return;
    }
  }

  // Collect form data
  const form = document.getElementById('reportForm');
  const payload = {
    reportType: form.reportType.value,
    location: form.location.value,
    onsetDate: form.onsetDate.value || null,
    severity: form.severity.value || 'unknown',
    peopleAffected: form.peopleAffected.value || null,
    details: form.details.value,
    name: form.name.value || null,
    contact: form.contact.value || null,
    consent: form.consent.checked,
    createdAt: new Date().toISOString(),
  };

  const submitBtn = form.querySelector('button[type="submit"]');
  const originalText = submitBtn.innerHTML;
  submitBtn.disabled = true;
  submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i>Submitting...';

  try {
    const response = await fetch('/api/v1/reports', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error('Failed to submit report');
    }

    const result = await response.json();
    console.log('Report submitted:', result);

    // Show success message
    const successBox = document.getElementById('successBox');
    successBox.classList.remove('hidden');
    successBox.scrollIntoView({ behavior: 'smooth', block: 'center' });

    // Show toast notification
    showNotification('Report submitted successfully!', 'success');

    // Reset form
    form.reset();

    // Hide success message after 8 seconds
    setTimeout(() => {
      successBox.classList.add('hidden');
    }, 8000);

  } catch (error) {
    console.error('Error:', error);
    showNotification('Failed to submit report. Please try again.', 'error');
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerHTML = originalText;
  }
}
