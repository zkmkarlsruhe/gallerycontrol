// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT

import { useState, useCallback } from 'react';
import type {
  ScheduledJob,
  CreateCronJobPayload,
  CreateOnceJobPayload,
  UpdateJobPayload,
} from '../types/schedule';

const API_BASE = import.meta.env.VITE_API_BASE || '';

interface UseScheduledJobsOptions {
  showToast: (message: string, type: 'success' | 'danger' | 'info') => void;
}

interface UseScheduledJobsReturn {
  jobs: ScheduledJob[];
  loading: boolean;
  /** Fetch jobs for a specific target (or all if no target specified) */
  fetchJobs: (targetType?: string, targetId?: string, targetDeviceId?: string) => Promise<void>;
  /** Create a recurring job with cron expression */
  createCronJob: (payload: CreateCronJobPayload) => Promise<boolean>;
  /** Create a one-time job */
  createOnceJob: (payload: CreateOnceJobPayload) => Promise<boolean>;
  /** Update an existing job */
  updateJob: (jobId: string, payload: UpdateJobPayload) => Promise<boolean>;
  /** Delete a job */
  deleteJob: (jobId: string) => Promise<boolean>;
  /** Toggle job enabled state */
  toggleJob: (job: ScheduledJob) => Promise<boolean>;
  /** Get cron expression preview (next run times) */
  getCronPreview: (cronExpression: string, count?: number) => Promise<string[]>;
}

/**
 * Custom hook for managing scheduled jobs.
 * Provides CRUD operations for the scheduled jobs API.
 */
export function useScheduledJobs({
  showToast,
}: UseScheduledJobsOptions): UseScheduledJobsReturn {
  const [jobs, setJobs] = useState<ScheduledJob[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchJobs = useCallback(async (
    targetType?: string,
    targetId?: string,
    targetDeviceId?: string
  ) => {
    setLoading(true);
    try {
      let url = `${API_BASE}/api/admin/scheduled-jobs`;
      const params = new URLSearchParams();

      if (targetType) {
        params.set('target_type', targetType);
      }
      if (targetDeviceId) {
        params.set('target_device_id', targetDeviceId);
      } else if (targetId && targetType !== 'all') {
        params.set('target_id', targetId);
      }

      if (params.toString()) {
        url += `?${params.toString()}`;
      }

      const response = await fetch(url);
      if (!response.ok) throw new Error('Failed to fetch schedules');
      const data = await response.json();
      setJobs(data);
    } catch (err) {
      console.error('Failed to fetch schedules:', err);
      showToast('Failed to load schedules', 'danger');
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  const createCronJob = useCallback(async (payload: CreateCronJobPayload): Promise<boolean> => {
    try {
      const response = await fetch(`${API_BASE}/api/admin/scheduled-jobs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to create schedule');
      }

      showToast('Schedule created', 'success');
      return true;
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Failed to create schedule', 'danger');
      return false;
    }
  }, [showToast]);

  const createOnceJob = useCallback(async (payload: CreateOnceJobPayload): Promise<boolean> => {
    try {
      const response = await fetch(`${API_BASE}/api/admin/scheduled-jobs/once`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to create schedule');
      }

      showToast('Schedule created', 'success');
      return true;
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Failed to create schedule', 'danger');
      return false;
    }
  }, [showToast]);

  const updateJob = useCallback(async (
    jobId: string,
    payload: UpdateJobPayload
  ): Promise<boolean> => {
    try {
      const response = await fetch(`${API_BASE}/api/admin/scheduled-jobs/${jobId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to update schedule');
      }

      showToast('Schedule updated', 'success');
      return true;
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Failed to update schedule', 'danger');
      return false;
    }
  }, [showToast]);

  const deleteJob = useCallback(async (jobId: string): Promise<boolean> => {
    try {
      const response = await fetch(`${API_BASE}/api/admin/scheduled-jobs/${jobId}`, {
        method: 'DELETE',
      });
      if (!response.ok) throw new Error('Failed to delete');
      showToast('Schedule deleted', 'success');
      return true;
    } catch {
      showToast('Failed to delete schedule', 'danger');
      return false;
    }
  }, [showToast]);

  const toggleJob = useCallback(async (job: ScheduledJob): Promise<boolean> => {
    try {
      const response = await fetch(`${API_BASE}/api/admin/scheduled-jobs/${job.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !job.enabled }),
      });
      if (!response.ok) throw new Error('Failed to update');
      showToast(`Schedule ${job.enabled ? 'disabled' : 'enabled'}`, 'success');
      return true;
    } catch {
      showToast('Failed to update schedule', 'danger');
      return false;
    }
  }, [showToast]);

  const getCronPreview = useCallback(async (
    cronExpression: string,
    count: number = 3
  ): Promise<string[]> => {
    if (!cronExpression.trim()) return [];

    try {
      const response = await fetch(
        `${API_BASE}/api/admin/scheduled-jobs/cron/preview?cron_expression=${encodeURIComponent(cronExpression)}&count=${count}`
      );
      if (response.ok) {
        const data = await response.json();
        return data.next_runs || [];
      }
    } catch {
      // Silently fail - preview is optional
    }
    return [];
  }, []);

  return {
    jobs,
    loading,
    fetchJobs,
    createCronJob,
    createOnceJob,
    updateJob,
    deleteJob,
    toggleJob,
    getCronPreview,
  };
}
