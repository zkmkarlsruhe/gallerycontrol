// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT
import { useState, useEffect } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE || '';

export interface DeviceInfoResponse {
  device_id: string;
  device_type: string;
  info: Record<string, any>;
  error?: string;
  cached_at?: string;  // ISO timestamp when cache was updated
  is_stale?: boolean;  // True if data is from stale cache
}

export interface DeviceInfoResult {
  info: Record<string, any> | null;
  loading: boolean;
  error: string | null;
  cachedAt: Date | null;
  isStale: boolean;
}

/**
 * Fetch extended device info (MAC, lamp hours, temperature, etc.)
 * Only fetches when enabled=true (e.g., when accordion is open)
 *
 * Returns cached_at and is_stale for freshness display
 */
export function useDeviceInfo(deviceId: string, deviceType: string, enabled: boolean): DeviceInfoResult {
  const [info, setInfo] = useState<Record<string, any> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cachedAt, setCachedAt] = useState<Date | null>(null);
  const [isStale, setIsStale] = useState(false);

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
        const data: DeviceInfoResponse = await response.json();

        if (!cancelled) {
          if (data.error && !data.info) {
            // Only treat as error if no info provided
            setError(data.error);
            setInfo(null);
            setCachedAt(null);
            setIsStale(false);
          } else {
            setInfo(data.info);
            setCachedAt(data.cached_at ? new Date(data.cached_at) : null);
            setIsStale(data.is_stale || false);
            // Clear error if we got data (even stale)
            if (data.info && Object.keys(data.info).length > 0) {
              setError(null);
            } else if (data.error) {
              setError(data.error);
            }
          }
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to fetch');
          setInfo(null);
          setCachedAt(null);
          setIsStale(false);
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

  return { info, loading, error, cachedAt, isStale };
}
