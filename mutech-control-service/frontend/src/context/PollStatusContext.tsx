import { createContext, useContext, useEffect, useState, useRef, useCallback, type ReactNode } from 'react';

// Types for SSE events
interface DevicePollStatus {
  nextPollAt: Date;
  lastPollAt: Date;
  lastSuccess: boolean;
  pollInterval: number;
  isVerifying: boolean;
}

interface MonitoringConfig {
  poll_interval_seconds: number;
  fast_poll_interval_seconds: number;
  batch_size: number;
  device_timeout_seconds: number;
}

interface PollStatusContextType {
  deviceStatus: Map<string, DevicePollStatus>;
  config: MonitoringConfig | null;
  connected: boolean;
  clientCount: number;
}

const defaultConfig: MonitoringConfig = {
  poll_interval_seconds: 60,
  fast_poll_interval_seconds: 30,
  batch_size: 30,
  device_timeout_seconds: 5,
};

const PollStatusContext = createContext<PollStatusContextType>({
  deviceStatus: new Map(),
  config: defaultConfig,
  connected: false,
  clientCount: 0,
});

export function PollStatusProvider({ children }: { children: ReactNode }) {
  const [deviceStatus, setDeviceStatus] = useState<Map<string, DevicePollStatus>>(new Map());
  const [config, setConfig] = useState<MonitoringConfig | null>(defaultConfig);
  const [connected, setConnected] = useState(false);
  const [clientCount, setClientCount] = useState(0);
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);

  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const data = JSON.parse(event.data);

      switch (data.type) {
        case 'connected':
          setConfig(data.monitoring);
          break;

        case 'poll_complete':
          setDeviceStatus(prev => {
            const next = new Map(prev);
            const existing = prev.get(data.device_id);
            next.set(data.device_id, {
              nextPollAt: new Date(data.next_poll_at),
              lastPollAt: new Date(data.timestamp),
              lastSuccess: data.success,
              pollInterval: data.poll_interval,
              isVerifying: existing?.isVerifying || false,
            });
            return next;
          });
          break;

        case 'config_change':
          setConfig(data.monitoring);
          break;

        case 'verification_start':
          setDeviceStatus(prev => {
            const next = new Map(prev);
            const existing = prev.get(data.device_id);
            if (existing) {
              next.set(data.device_id, {
                ...existing,
                pollInterval: data.poll_interval,
                isVerifying: true,
              });
            } else {
              // Create new entry for device
              next.set(data.device_id, {
                nextPollAt: new Date(Date.now() + data.poll_interval * 1000),
                lastPollAt: new Date(),
                lastSuccess: true,
                pollInterval: data.poll_interval,
                isVerifying: true,
              });
            }
            return next;
          });
          break;

        case 'verification_end':
          setDeviceStatus(prev => {
            const next = new Map(prev);
            const existing = prev.get(data.device_id);
            if (existing) {
              next.set(data.device_id, {
                ...existing,
                pollInterval: data.poll_interval,
                isVerifying: false,
              });
            }
            return next;
          });
          break;

        case 'heartbeat':
          setClientCount(data.client_count || 0);
          break;
      }
    } catch (e) {
      console.error('Error parsing SSE event:', e);
    }
  }, []);

  const connect = useCallback(() => {
    // Close existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const eventSource = new EventSource('/api/state/stream');
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      setConnected(true);
      console.log('SSE connected');
    };

    eventSource.onerror = () => {
      setConnected(false);
      eventSource.close();

      // Reconnect after 5 seconds
      reconnectTimeoutRef.current = window.setTimeout(() => {
        console.log('SSE reconnecting...');
        connect();
      }, 5000);
    };

    eventSource.onmessage = handleMessage;
  }, [handleMessage]);

  useEffect(() => {
    connect();

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [connect]);

  return (
    <PollStatusContext.Provider value={{ deviceStatus, config, connected, clientCount }}>
      {children}
    </PollStatusContext.Provider>
  );
}

export const usePollStatus = () => useContext(PollStatusContext);

// Hook for getting a specific device's poll progress (0-100%)
export function useDevicePollProgress(deviceId: string, fallbackPollStatus?: { last_polled_at: string | null; poll_interval: number; is_verifying?: boolean } | null): {
  progress: number;
  isVerifying: boolean;
  pollInterval: number;
  secondsRemaining: number;
} {
  const { deviceStatus, config } = usePollStatus();
  const [progress, setProgress] = useState(100);
  const [secondsRemaining, setSecondsRemaining] = useState(0);

  const status = deviceStatus.get(deviceId);
  // Use SSE status first, fallback to API poll_status for is_verifying
  const isVerifying = status?.isVerifying || fallbackPollStatus?.is_verifying || false;
  const pollInterval = status?.pollInterval || config?.poll_interval_seconds || fallbackPollStatus?.poll_interval || 60;

  useEffect(() => {
    const calcProgress = () => {
      const now = Date.now();

      // Get the best available last poll time
      let lastPollTime: number | null = null;

      // SSE data is more recent/accurate
      if (status?.lastPollAt) {
        lastPollTime = status.lastPollAt.getTime();
      } else if (fallbackPollStatus?.last_polled_at) {
        lastPollTime = new Date(fallbackPollStatus.last_polled_at).getTime();
      }

      if (!lastPollTime) {
        // No data yet
        setSecondsRemaining(pollInterval);
        return 100;
      }

      // Estimate next poll time
      const elapsed = (now - lastPollTime) / 1000;

      // How far into the current cycle are we?
      const cyclePosition = elapsed % pollInterval;
      const remaining = pollInterval - cyclePosition;

      setSecondsRemaining(Math.ceil(remaining));
      return Math.max(0, Math.min(100, (remaining / pollInterval) * 100));
    };

    setProgress(calcProgress());
    const intervalId = setInterval(() => setProgress(calcProgress()), 1000);
    return () => clearInterval(intervalId);
  }, [deviceId, status?.lastPollAt, pollInterval, fallbackPollStatus?.last_polled_at]);

  return { progress, isVerifying, pollInterval, secondsRemaining };
}
