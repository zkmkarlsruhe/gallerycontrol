import { useState, useEffect } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE || '';

export interface DeviceInfo {
  device_id: string;
  device_type: string;
  info: Record<string, any>;
  error?: string;
}

/**
 * Fetch extended device info (MAC, lamp hours, temperature, etc.)
 * Only fetches when enabled=true (e.g., when accordion is open)
 */
export function useDeviceInfo(deviceId: string, deviceType: string, enabled: boolean) {
  const [info, setInfo] = useState<Record<string, any> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled || !deviceId) {
      return;
    }

    // Don't fetch for shell devices - they don't have device info
    if (deviceType === 'shell') {
      return;
    }

    let cancelled = false;

    const fetchInfo = async () => {
      setLoading(true);
      setError(null);

      try {
        const response = await fetch(`${API_BASE}/api/debug/device/${deviceId}/info`);
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const data: DeviceInfo = await response.json();

        if (!cancelled) {
          if (data.error) {
            setError(data.error);
            setInfo(null);
          } else {
            setInfo(data.info);
          }
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to fetch');
          setInfo(null);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    fetchInfo();

    return () => {
      cancelled = true;
    };
  }, [deviceId, deviceType, enabled]);

  return { info, loading, error };
}
