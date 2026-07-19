export class ApiError extends Error {
  constructor(message, status, details = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.details = details;
  }
}

const API_BASE = (import.meta.env && import.meta.env.VITE_API_BASE_URL) || '';

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const readPayload = async (response) => {
  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    try {
      return await response.json();
    } catch (e) {
      return null;
    }
  }
  try {
    const text = await response.text();
    return text || null;
  } catch (e) {
    return null;
  }
};

const shouldRetry = (error, responseStatus) => {
  if (responseStatus) return responseStatus >= 500;
  return error instanceof TypeError; // network/connection level fetch errors
};

const inFlightRequests = new Map();

/**
 * Minimal fetch wrapper with retries, JSON parsing, and uniform errors.
 */
export async function apiRequest(path, options = {}) {
  const {
    method = 'GET',
    body,
    headers = {},
    token,
    retries = 1,
    retryDelayMs = 250,
    credentials = 'same-origin',
    auth = false,
    signal,
  } = options;

  const resolvedToken = token || localStorage.getItem('doctalk_token');
  const finalHeaders = { ...headers };

  let payload = body;
  const isForm = typeof FormData !== 'undefined' && body instanceof FormData;
  if (body && !isForm && typeof body === 'object' && !(body instanceof URLSearchParams) && !finalHeaders['Content-Type']) {
    finalHeaders['Content-Type'] = 'application/json';
    payload = JSON.stringify(body);
  }

  if (auth && resolvedToken && !finalHeaders.Authorization) {
    finalHeaders.Authorization = `Bearer ${resolvedToken}`;
  }

  const cacheKey = method === 'GET' ? `${method}:${path}:${resolvedToken || ''}` : null;
  if (cacheKey && inFlightRequests.has(cacheKey)) {
    return inFlightRequests.get(cacheKey);
  }

  const performRequest = async () => {
    let attempt = 0;
    let lastError = null;

    while (attempt <= retries) {
      try {
        const response = await fetch(API_BASE + path, {
          method,
          headers: finalHeaders,
          body: payload,
          credentials,
          signal,
        });

        const data = await readPayload(response);
        if (response.ok) return data;

        const message = (data && (data.detail || data.error || data.message)) || `Request failed (${response.status})`;
        const apiError = new ApiError(message, response.status, data);

        if (response.status === 401) {
          localStorage.removeItem('doctalk_token');
          window.location.href = '/login';
        }

        if (attempt < retries && shouldRetry(apiError, response.status)) {
          await sleep(retryDelayMs * (attempt + 1));
          attempt += 1;
          continue;
        }
        throw apiError;
      } catch (error) {
        lastError = error;
        if (attempt < retries && shouldRetry(error)) {
          await sleep(retryDelayMs * (attempt + 1));
          attempt += 1;
          continue;
        }
        break;
      }
    }

    if (lastError instanceof ApiError) throw lastError;
    throw new ApiError(lastError?.message || 'Network request failed', 0, null);
  };

  const requestPromise = performRequest();
  
  if (cacheKey) {
    inFlightRequests.set(cacheKey, requestPromise);
    requestPromise.finally(() => {
      if (inFlightRequests.get(cacheKey) === requestPromise) {
        inFlightRequests.delete(cacheKey);
      }
    });
  }

  return requestPromise;
}

export const apiClient = {
  request: apiRequest,
  get: (path, options = {}) => apiRequest(path, { ...options, method: 'GET' }),
  post: (path, body, options = {}) => apiRequest(path, { ...options, method: 'POST', body }),
  put: (path, body, options = {}) => apiRequest(path, { ...options, method: 'PUT', body }),
  patch: (path, body, options = {}) => apiRequest(path, { ...options, method: 'PATCH', body }),
  delete: (path, options = {}) => apiRequest(path, { ...options, method: 'DELETE' }),
};
