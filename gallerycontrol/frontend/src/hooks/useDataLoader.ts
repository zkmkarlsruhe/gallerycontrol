// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT

import { useState, useEffect, useCallback } from 'react';
import type { Exhibition, Credential, ShellTemplate, ServiceHealth } from '../types';

interface UseDataLoaderOptions {
  fetchExhibitions: () => Promise<Exhibition[]>;
  fetchCredentials: () => Promise<Credential[]>;
  fetchShellTemplates: () => Promise<ShellTemplate[]>;
  fetchServiceHealth: () => Promise<ServiceHealth[]>;
  /** Auto-refresh interval for exhibitions in ms (default: 5000) */
  exhibitionsRefreshInterval?: number;
  /** Auto-refresh interval for service health in ms (default: 15000) */
  healthRefreshInterval?: number;
}

interface UseDataLoaderReturn {
  exhibitions: Exhibition[];
  credentials: Credential[];
  templates: ShellTemplate[];
  serviceHealth: ServiceHealth[];
  loading: boolean;
  error: string | null;
  /** Reload exhibitions data */
  loadData: () => Promise<void>;
  /** Reload credentials data */
  loadCredentials: () => Promise<void>;
  /** Reload shell templates data */
  loadTemplates: () => Promise<void>;
  /** Reload service health data */
  loadServiceHealth: () => Promise<void>;
}

/**
 * Custom hook for loading and auto-refreshing application data.
 * Handles exhibitions, credentials, shell templates, and service health.
 */
export function useDataLoader({
  fetchExhibitions,
  fetchCredentials,
  fetchShellTemplates,
  fetchServiceHealth,
  exhibitionsRefreshInterval = 5000,
  healthRefreshInterval = 15000,
}: UseDataLoaderOptions): UseDataLoaderReturn {
  const [exhibitions, setExhibitions] = useState<Exhibition[]>([]);
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [templates, setTemplates] = useState<ShellTemplate[]>([]);
  const [serviceHealth, setServiceHealth] = useState<ServiceHealth[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      const data = await fetchExhibitions();
      setExhibitions(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, [fetchExhibitions]);

  const loadCredentials = useCallback(async () => {
    try {
      const data = await fetchCredentials();
      setCredentials(data);
    } catch {
      // Credentials are optional, don't show error
    }
  }, [fetchCredentials]);

  const loadTemplates = useCallback(async () => {
    try {
      const data = await fetchShellTemplates();
      setTemplates(data);
    } catch {
      // Templates are optional, don't show error
    }
  }, [fetchShellTemplates]);

  const loadServiceHealth = useCallback(async () => {
    const data = await fetchServiceHealth();
    setServiceHealth(data);
  }, [fetchServiceHealth]);

  // Initial load and auto-refresh
  useEffect(() => {
    loadData();
    loadCredentials();
    loadTemplates();
    loadServiceHealth();

    const exhibitionsInterval = setInterval(loadData, exhibitionsRefreshInterval);
    const healthInterval = setInterval(loadServiceHealth, healthRefreshInterval);

    return () => {
      clearInterval(exhibitionsInterval);
      clearInterval(healthInterval);
    };
  }, [loadData, loadCredentials, loadTemplates, loadServiceHealth, exhibitionsRefreshInterval, healthRefreshInterval]);

  return {
    exhibitions,
    credentials,
    templates,
    serviceHealth,
    loading,
    error,
    loadData,
    loadCredentials,
    loadTemplates,
    loadServiceHealth,
  };
}
