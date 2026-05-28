// Minimal real-time client with SSE and polling fallback.
// Usage: const client = createRealTimeClient({ url: '/api/stream/notifications', pollRequest: () => fetchSnapshot(), onMessage }); client.start();

const DEFAULT_POLL_INTERVAL = 5000;
const DEFAULT_RECONNECT_DELAY = 1000;
const DEFAULT_MAX_RECONNECT_DELAY = 30000;

function safeJsonParse(value) {
  if (typeof value !== 'string') return value;
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}

function defaultSnapshotKey(payload) {
  try {
    return JSON.stringify(payload);
  } catch {
    return String(payload);
  }
}

export function createRealTimeClient({
  url,
  mode = 'auto',
  pollInterval = DEFAULT_POLL_INTERVAL,
  reconnectDelay = DEFAULT_RECONNECT_DELAY,
  maxReconnectDelay = DEFAULT_MAX_RECONNECT_DELAY,
  pollRequest,
  onMessage,
  onOpen,
  onError,
  onStatus,
  getSnapshotKey = defaultSnapshotKey,
  fetchOptions = {},
} = {}) {
  let eventSource = null;
  let pollTimer = null;
  let stopped = true;
  let requestInFlight = false;
  let generation = 0;
  let currentReconnectDelay = reconnectDelay;
  let lastSnapshotKey = null;

  const setStatus = (status) => {
    onStatus && onStatus(status);
  };

  const clearPollTimer = () => {
    if (pollTimer) {
      clearTimeout(pollTimer);
      pollTimer = null;
    }
  };

  const emitIfChanged = (payload) => {
    const snapshotKey = getSnapshotKey(payload);
    if (snapshotKey === lastSnapshotKey) return false;
    lastSnapshotKey = snapshotKey;
    onMessage && onMessage(payload);
    return true;
  };

  const readSnapshot = async () => {
    if (typeof pollRequest === 'function') {
      return await pollRequest();
    }

    const response = await fetch(url, { credentials: 'include', ...fetchOptions });
    if (!response.ok) {
      const error = new Error(`Realtime poll failed with status ${response.status}`);
      error.status = response.status;
      throw error;
    }
    return await response.json();
  };

  const schedulePolling = (delay) => {
    if (stopped) return;
    clearPollTimer();
    const waitMs = Math.max(0, Number.isFinite(delay) ? delay : pollInterval);
    pollTimer = setTimeout(async () => {
      if (stopped || requestInFlight) return;
      requestInFlight = true;
      const activeGeneration = generation;
      let succeeded = false;

      try {
        const payload = await readSnapshot();
        if (stopped || activeGeneration !== generation) return;
        emitIfChanged(safeJsonParse(payload));
        currentReconnectDelay = reconnectDelay;
        succeeded = true;
        setStatus('polling');
      } catch (error) {
        if (!stopped && activeGeneration === generation) {
          onError && onError(error);
          setStatus('reconnecting');
          currentReconnectDelay = Math.min(currentReconnectDelay * 2, maxReconnectDelay);
        }
      } finally {
        requestInFlight = false;
      }

      if (!stopped && activeGeneration === generation) {
        schedulePolling(succeeded ? pollInterval : currentReconnectDelay);
      }
    }, waitMs);
  };

  const startPolling = () => {
    if (!stopped && pollTimer) return;
    stopped = false;
    setStatus('polling');
    schedulePolling(0);
  };

  const startEventSource = () => {
    if (typeof EventSource === 'undefined') {
      startPolling();
      return;
    }

    try {
      eventSource = new EventSource(url, { withCredentials: true });
      setStatus('connecting');

      eventSource.onopen = () => {
        if (stopped) return;
        currentReconnectDelay = reconnectDelay;
        setStatus('connected');
        onOpen && onOpen();
      };

      eventSource.onmessage = (event) => {
        if (stopped) return;
        emitIfChanged(safeJsonParse(event.data));
      };

      eventSource.onerror = (error) => {
        if (stopped) return;
        onError && onError(error);
        setStatus('reconnecting');
        try {
          eventSource.close();
        } catch (_) {}
        eventSource = null;
        startPolling();
      };
    } catch (error) {
      onError && onError(error);
      startPolling();
    }
  };

  function start() {
    if (!stopped) return;
    stopped = false;
    generation += 1;
    currentReconnectDelay = reconnectDelay;
    lastSnapshotKey = null;

    if (mode === 'poll') {
      startPolling();
      return;
    }

    if (mode === 'sse' || mode === 'auto') {
      startEventSource();
      return;
    }

    startPolling();
  }

  function stop() {
    stopped = true;
    generation += 1;
    clearPollTimer();
    requestInFlight = false;
    lastSnapshotKey = null;

    if (eventSource) {
      try {
        eventSource.close();
      } catch (_) {}
      eventSource = null;
    }
  }

  return {
    start,
    stop,
    refresh: async () => {
      if (stopped || requestInFlight) return;
      requestInFlight = true;
      const activeGeneration = generation;
      try {
        const payload = await readSnapshot();
        if (!stopped && activeGeneration === generation) {
          emitIfChanged(safeJsonParse(payload));
        }
      } catch (error) {
        if (!stopped && activeGeneration === generation) {
          onError && onError(error);
        }
      } finally {
        requestInFlight = false;
      }
    },
  };
}

export default createRealTimeClient;
