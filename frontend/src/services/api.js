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
 * Get Metabase connection status (without credentials)
 * @returns {Promise<Object>} { configurado, servidor, autenticacion, card_id }
 */
export const getMetabaseStatus = async () => {
  const response = await apiClient.get('/metabase/estado');
  return response.data;
};

/**
 * Fetch work orders (OTs) from a Metabase question
 * @param {string} cardId - Question id; empty uses METABASE_CARD_ID
 * @returns {Promise<Object>} OTs, column mapping, OR counts and warnings
 */
export const fetchMetabaseOTs = async (cardId) => {
  const response = await apiClient.get('/metabase/ots', {
    params: cardId ? { card_id: cardId } : {},
  });
  return response.data;
};

/**
 * Get Bia bases and contractor sites
 * @returns {Promise<Object>} { sedes, empresas, avisos }
 */
export const getCatalog = async () => {
  const response = await apiClient.get('/catalogo');
  return response.data;
};

/**
 * Get in-house technicians and contractors per OR
 * @returns {Promise<Object>} { tecnicos, or_contratistas }
 */
export const getAssignmentConfig = async () => {
  const response = await apiClient.get('/asignacion/config');
  return response.data;
};

/**
 * Save in-house technicians and contractors per OR
 * @param {Object} config - { tecnicos, or_contratistas }
 * @returns {Promise<Object>} Saved configuration
 */
export const saveAssignmentConfig = async (config) => {
  const response = await apiClient.put('/asignacion/config', config);
  return response.data;
};

/**
 * Assign OTs filtered by OR to in-house technicians or contractors
 * @param {Object} request - { modo, actividades, or_filtro, tecnicos_ids, jornada }
 * @returns {Promise<Object>} Assignment result with routes per technician/contractor
 */
export const assignActivities = async (request) => {
  const response = await apiClient.post('/asignar', request);
  return response.data;
};

export default apiClient;
