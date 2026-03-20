/**
 * API Configuration
 * Central configuration for all API endpoints and settings
 */

// Environment detection
const ENV = {
  DEVELOPMENT: 'development',
  PRODUCTION: 'production',
  STAGING: 'staging'
};

// Current environment (change based on deployment)
const CURRENT_ENV = ENV.DEVELOPMENT;

// Base URLs for different environments
const BASE_URLS = {
  [ENV.DEVELOPMENT]: 'http://localhost:3000/api',
  [ENV.STAGING]: 'https://staging-api.healthchatbot.com/api',
  [ENV.PRODUCTION]: 'https://api.healthchatbot.com/api'
};

// API Configuration
export const API_CONFIG = {
  BASE_URL: BASE_URLS[CURRENT_ENV],
  TIMEOUT: 30000, // 30 seconds
  RETRY_ATTEMPTS: 3,
  RETRY_DELAY: 1000, // 1 second
};

// API Endpoints
export const ENDPOINTS = {
  // Chatbot
  CHATBOT: {
    SEND_MESSAGE: '/chatbot/message',
    GET_HISTORY: '/chatbot/history',
    CLEAR_HISTORY: '/chatbot/history/clear',
  },
  
  // Emergency
  EMERGENCY: {
    REQUEST_AMBULANCE: '/emergency/request-ambulance',
    REQUEST_MEDICINE: '/emergency/request-medicine',
    REQUEST_DOCTOR: '/emergency/request-doctor',
    FIND_HOSPITALS: '/emergency/hospitals/nearby',
    GET_HOSPITAL_DETAILS: '/emergency/hospitals',
  },
  
  // Alerts
  ALERTS: {
    GET_OUTBREAKS: '/alerts/outbreaks',
    GET_BY_LOCATION: '/alerts/outbreaks/location',
    SUBSCRIBE: '/alerts/subscribe',
    UNSUBSCRIBE: '/alerts/unsubscribe',
  },
  
  // Education
  EDUCATION: {
    GET_VIDEOS: '/education/videos',
    GET_ARTICLES: '/education/articles',
    SEARCH: '/education/search',
    GENERATE_SUMMARY: '/education/generate-summary',
    GENERATE_TRANSCRIPT: '/education/generate-transcript',
    REPORT_MISSING: '/education/report-missing',
  },
  
  // Connect (Doctors)
  CONNECT: {
    FIND_DOCTORS: '/connect/doctors/nearby',
    SEARCH_DOCTORS: '/connect/doctors/search',
    GET_DOCTOR_DETAILS: '/connect/doctors',
    BOOK_APPOINTMENT: '/connect/doctors/book',
  },
  
  // Report
  REPORT: {
    SUBMIT_HEALTH: '/report/health',
    GET_HISTORY: '/report/history',
    GET_STATISTICS: '/report/statistics',
  },
  
  // User
  USER: {
    LOGIN: '/user/login',
    REGISTER: '/user/register',
    PROFILE: '/user/profile',
    UPDATE_PROFILE: '/user/profile/update',
  }
};

// External API Keys (should be in .env in production)
export const EXTERNAL_APIS = {
  GOOGLE_MAPS_KEY: process.env.GOOGLE_MAPS_API_KEY || '',
  OPENAI_KEY: process.env.OPENAI_API_KEY || '',
  TWILIO_KEY: process.env.TWILIO_API_KEY || '',
};

// HTTP Status Codes
export const HTTP_STATUS = {
  OK: 200,
  CREATED: 201,
  BAD_REQUEST: 400,
  UNAUTHORIZED: 401,
  FORBIDDEN: 403,
  NOT_FOUND: 404,
  INTERNAL_SERVER_ERROR: 500,
  SERVICE_UNAVAILABLE: 503,
};

// Error Messages
export const ERROR_MESSAGES = {
  NETWORK_ERROR: 'Network error. Please check your internet connection.',
  TIMEOUT_ERROR: 'Request timeout. Please try again.',
  SERVER_ERROR: 'Server error. Please try again later.',
  UNAUTHORIZED: 'Unauthorized. Please login again.',
  NOT_FOUND: 'Resource not found.',
  VALIDATION_ERROR: 'Validation error. Please check your input.',
};

export default API_CONFIG;
