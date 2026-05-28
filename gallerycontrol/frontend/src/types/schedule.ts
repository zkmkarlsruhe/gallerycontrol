// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT

/**
 * Shared types for scheduled job management.
 * Used by ScheduleManagerModal and QuickScheduleModal.
 */

/**
 * Represents a scheduled job in the system.
 */
export interface ScheduledJob {
  id: string;
  name: string;
  job_type: string;
  cron_expression: string | null;
  run_once: boolean;
  target_type: string;
  target_id: string | null;
  target_device_id: string | null;
  target_device_name: string | null;
  action_type: string | null;
  action_name: string | null;
  enabled: boolean;
  last_run_at: string | null;
  last_success: boolean | null;
  last_error: string | null;
  next_run_at: string | null;
  executed_at: string | null;
}

/**
 * Payload for creating a recurring (cron) scheduled job.
 */
export interface CreateCronJobPayload {
  name: string;
  cron_expression: string;
  job_type: string;
  target_type: string;
  target_id?: string;
  target_device_id?: string;
  action_type: string;
  action_name?: string;
  enabled: boolean;
}

/**
 * Payload for creating a one-time scheduled job.
 */
export interface CreateOnceJobPayload {
  name: string;
  run_at: string;
  target_type: string;
  target_id: string;
  action_type: string;
}

/**
 * Payload for updating a scheduled job.
 */
export interface UpdateJobPayload {
  name?: string;
  cron_expression?: string;
  action_type?: string;
  action_name?: string;
  enabled?: boolean;
}
