// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT
import { createContext, useContext, useEffect, useState, useRef, useCallback, type ReactNode } from 'react';
import type { ProtectionStatus } from '../types';

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

// Protection status update from SSE
interface ArtworkProtectionStatus {
  status: ProtectionStatus;
  lastUpdated: Date;
}

interface PollStatusContextType {
  deviceStatus: Map<string, DevicePollStatus>;
  protectionStatus: Map<string, ArtworkProtectionStatus>;
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
  protectionStatus: new Map(),
  config: defaultConfig,
  connected: false,
  clientCount: 0,
});

export function PollStatusProvider({ children }: { children: ReactNode }) {
  const [deviceStatus, setDeviceStatus] = useState<Map<string, DevicePollStatus>>(new Map());
  const [protectionStatus, setProtectionStatus] = useState<Map<string, ArtworkProtectionStatus>>(new Map());
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

        case 'protection_status':
          // Full protection status update for an artwork
          setProtectionStatus(prev => {
            const next = new Map(prev);
            next.set(data.artwork_id, {
              status: data.status,
              lastUpdated: new Date(data.timestamp),
            });
            return next;
          });
          break;

        case 'accepting_triggers_change':
          // Update just the accepting_triggers field
          setProtectionStatus(prev => {
            const next = new Map(prev);
            const existing = prev.get(data.artwork_id);
            if (existing) {
              next.set(data.artwork_id, {
                ...existing,
                status: {
                  ...existing.status,
                  accepting_triggers: data.accepting_triggers,
                },
                lastUpdated: new Date(data.timestamp),
              });
            }
            return next;
          });
          break;

        case 'protection_forced_off':
          // Log forced off events - the backend sends a follow-up protection_status
          // event with the full updated state, so we just log here
          console.warn(`Protection forced off for artwork ${data.artwork_id}: ${data.reason}`);
          break;
      }
    } catch (e) {
      console.error('Error parsing SSE event:', e);
    }
  }, []);

  // Use ref for reconnection to avoid hoisting issues
  const connectRef = useRef<() => void>(() => {});

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
        connectRef.current();
      }, 5000);
    };

    eventSource.onmessage = handleMessage;
  }, [handleMessage]);

  // Keep ref in sync with connect function
  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

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
    <PollStatusContext.Provider value={{ deviceStatus, protectionStatus, config, connected, clientCount }}>
      {children}
    </PollStatusContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export const usePollStatus = () => useContext(PollStatusContext);

// Hook for getting a specific device's poll progress (0-100%)
// eslint-disable-next-line react-refresh/only-export-components
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

    // Initial progress calculation - intentional initialization
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setProgress(calcProgress());
    const intervalId = setInterval(() => setProgress(calcProgress()), 1000);
    return () => clearInterval(intervalId);
  }, [deviceId, status?.lastPollAt, pollInterval, fallbackPollStatus?.last_polled_at]);

  return { progress, isVerifying, pollInterval, secondsRemaining };
}

// Hook for getting protection status for a specific artwork
// eslint-disable-next-line react-refresh/only-export-components
export function useProtectionStatus(artworkId: string): {
  status: ProtectionStatus | null;
  lastUpdated: Date | null;
} {
  const { protectionStatus } = usePollStatus();
  const entry = protectionStatus.get(artworkId);
  return {
    status: entry?.status || null,
    lastUpdated: entry?.lastUpdated || null,
  };
}
