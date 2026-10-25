import axios from 'axios';

// API base URL
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

// Create axios instance with default config
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 300000, // 5 minutes for long operations
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for logging
apiClient.interceptors.request.use(
  (config) => {
    console.log(`API Request: ${config.method.toUpperCase()} ${config.url}`);
    return config;
  },
  (error) => {
    console.error('Request error:', error);
    return Promise.reject(error);
  }
);

// Response interceptor for logging and error handling
apiClient.interceptors.response.use(
  (response) => {
    console.log(`API Response: ${response.config.url} - Status: ${response.status}`);
    return response;
  },
  (error) => {
    console.error('Response error:', error);

    // Extract error message
    let errorMessage = 'An error occurred';
    if (error.response) {
      errorMessage = error.response.data?.detail || error.response.statusText;
    } else if (error.request) {
      errorMessage = 'No response from server';
    } else {
      errorMessage = error.message;
    }

    return Promise.reject(new Error(errorMessage));
  }
);

// API functions

/**
 * Upload activity file
 * @param {File} file - Excel or CSV file
 * @returns {Promise<Object>} Upload result with activities
 */
export const uploadFile = async (file) => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await apiClient.post('/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });

  return response.data;
};

/**
 * Optimize routes for activity lot
 * @param {Object} activityLot - Activity lot with configuration
 * @returns {Promise<Object>} Optimization result
 */
export const optimizeRoutes = async (activityLot) => {
  const response = await apiClient.post('/optimize', activityLot);
  return response.data;
};

/**
 * Estimate number of crews needed
 * @param {Object} activityLot - Activity lot with configuration
 * @returns {Promise<Object>} Crew estimation
 */
export const estimateCrews = async (activityLot) => {
  const response = await apiClient.post('/estimate-crews', activityLot);
  return response.data;
};

/**
 * Get geographic summary of activities
 * @param {Object} activityLot - Activity lot
 * @returns {Promise<Object>} Geographic summary
 */
export const getGeographicSummary = async (activityLot) => {
  const response = await apiClient.post('/geographic-summary', activityLot);
  return response.data;
};

/**
 * Check health of all services
 * @returns {Promise<Object>} Health status
 */
export const checkServicesHealth = async () => {
  const response = await apiClient.get('/health/services');
  return response.data;
};

/**
 * Get API information
 * @returns {Promise<Object>} API info
 */
export const getApiInfo = async () => {
  const response = await apiClient.get('/info');
  return response.data;
};

/**
 * Analyze proximity clusters
 * @param {Object} activityLot - Activity lot to analyze
 * @param {number} maxDistanceKm - Maximum distance for clustering (default: 20)
 * @param {string} method - Clustering method: "proximity" or "kmeans" (default: "proximity")
 * @returns {Promise<Object>} Proximity clustering result
 */
export const analyzeProximity = async (activityLot, maxDistanceKm = 20.0, method = 'proximity') => {
  const response = await apiClient.post('/analyze-proximity', activityLot, {
    params: {
      max_distance_km: maxDistanceKm,
      method: method
    }
  });
  return response.data;
};

/**
 * Optimize routes by proximity clusters
 * @param {Object} activityLot - Activity lot to optimize
 * @param {number} maxDistanceKm - Maximum distance for clustering (default: 20)
 * @param {string} method - Clustering method: "proximity" or "kmeans" (default: "proximity")
 * @returns {Promise<Object>} Cluster optimization result
 */
export const optimizeByClusters = async (activityLot, maxDistanceKm = 20.0, method = 'proximity') => {
  const response = await apiClient.post('/optimize-by-clusters', activityLot, {
    params: {
      max_distance_km: maxDistanceKm,
      method: method
    }
  });
  return response.data;
};

export default apiClient;
