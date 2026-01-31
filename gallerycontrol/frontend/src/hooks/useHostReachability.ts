// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT
import { useState, useEffect, useCallback, useRef } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE || '';

export type ReachabilityStatus = 'idle' | 'checking' | 'reachable' | 'unreachable';

interface HostReachabilityResult {
  status: ReachabilityStatus;
  error: string | null;
  checkHost: () => void;
}

interface CheckHostResponse {
  reachable: boolean;
  host: string;
  port: number;
  error?: string;
  duration_ms: number;
}

/**
 * Hook to check if a host is reachable via TCP connection.
 * Automatically debounces checks while the user is typing.
 *
 * @param host - The hostname or IP address to check
 * @param port - The port to check (uses device-specific defaults if not specified)
 * @param deviceType - The device type (pjlink, netio, anel) for default port selection
 * @param debounceMs - Debounce delay in milliseconds (default 500ms)
 */
export function useHostReachability(
  host: string,
  port: number,
  deviceType: 'pjlink' | 'netio' | 'anel',
  debounceMs: number = 500
): HostReachabilityResult {
  const [status, setStatus] = useState<ReachabilityStatus>('idle');
  const [error, setError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const debounceTimerRef = useRef<number | null>(null);

  const checkHost = useCallback(async () => {
    // Don't check if host is empty or too short
    if (!host || host.length < 3) {
      setStatus('idle');
      setError(null);
      return;
    }

    // Cancel any pending request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    // Create new abort controller
    abortControllerRef.current = new AbortController();
    setStatus('checking');
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/api/admin/check-host`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          host,
          port,
          device_type: deviceType,
        }),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        throw new Error('Failed to check host');
      }

      const data: CheckHostResponse = await response.json();

      if (data.reachable) {
        setStatus('reachable');
        setError(null);
      } else {
        setStatus('unreachable');
        setError(data.error || 'Host is not reachable');
      }
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        // Request was aborted, ignore
        return;
      }
      setStatus('unreachable');
      setError(err instanceof Error ? err.message : 'Check failed');
    }
  }, [host, port, deviceType]);

  // Debounced effect to check host when host/port changes
  useEffect(() => {
    // Clear any pending timer
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    // Don't check if host is empty
    if (!host || host.length < 3) {
      setStatus('idle');
      setError(null);
      return;
    }

    // Set status to checking immediately for feedback
    setStatus('checking');

    // Debounce the actual check
    debounceTimerRef.current = window.setTimeout(() => {
      checkHost();
    }, debounceMs);

    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [host, port, checkHost, debounceMs]);

  return { status, error, checkHost };
}
