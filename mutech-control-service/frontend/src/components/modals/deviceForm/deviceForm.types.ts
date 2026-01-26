/**
 * Shared types for device form state management.
 * Used by both AddDeviceModal and EditDeviceModal.
 */

import type { ReachabilityStatus } from '../../../hooks/useHostReachability';

// Device types supported by the system
export type DeviceType = 'pjlink' | 'netio' | 'anel' | 'shell';

// Individual form data types for each device
export interface PJLinkFormData {
  name: string;
  host: string;
  port: number;
  credential_id: string;
  enabled: boolean;
  automation_enabled: boolean;
}

export interface NetioFormData {
  name: string;
  host: string;
  port: number; // 1-indexed in UI
  credential_id: string;
  enabled: boolean;
  automation_enabled: boolean;
}

export interface AnelFormData {
  name: string;
  host: string;
  port: number; // 1-indexed in UI
  credential_id: string;
  enabled: boolean;
  automation_enabled: boolean;
}

export interface ShellAction {
  name: string;
  cmd: string;
}

export interface ShellFormData {
  name: string;
  credential_id: string;
  onoff_mode: boolean;
  automation_enabled: boolean;
  status_cmd: string;
  on_pattern: string;
  off_pattern: string;
  on_cmd: string;
  off_cmd: string;
  actions: ShellAction[];
  enabled: boolean;
}

// Union of all form data types
export type DeviceFormData = PJLinkFormData | NetioFormData | AnelFormData | ShellFormData;

// State slices for all device forms
export interface DeviceFormSlices {
  pjlink: PJLinkFormData;
  netio: NetioFormData;
  anel: AnelFormData;
  shell: ShellFormData;
}

// Complete device form state
export interface DeviceFormState {
  deviceType: DeviceType;
  slices: DeviceFormSlices;
  reachabilityStatus: ReachabilityStatus;
}

// API payload structure for creating/updating devices
export interface DevicePayload {
  name: string;
  device_type?: DeviceType; // Only for create
  host: string;
  port?: number;
  enabled: boolean;
  automation_enabled: boolean;
  schedules_enabled?: boolean; // Only for update
  config: Record<string, any>;
}

// Default values for each device form
export const defaultPJLinkData: PJLinkFormData = {
  name: '',
  host: '',
  port: 4352,
  credential_id: '',
  enabled: true,
  automation_enabled: true,
};

export const defaultNetioData: NetioFormData = {
  name: '',
  host: '',
  port: 1, // 1-indexed in UI
  credential_id: '',
  enabled: true,
  automation_enabled: true,
};

export const defaultAnelData: AnelFormData = {
  name: '',
  host: '',
  port: 1, // 1-indexed in UI
  credential_id: '',
  enabled: true,
  automation_enabled: true,
};

export const defaultShellData: ShellFormData = {
  name: '',
  credential_id: '',
  onoff_mode: false,
  automation_enabled: true,
  status_cmd: '',
  on_pattern: '',
  off_pattern: '',
  on_cmd: '',
  off_cmd: '',
  actions: [],
  enabled: true,
};

export const emptyShellAction: ShellAction = { name: '', cmd: '' };

// Get default slices for all device forms
export function getDefaultSlices(): DeviceFormSlices {
  return {
    pjlink: { ...defaultPJLinkData },
    netio: { ...defaultNetioData },
    anel: { ...defaultAnelData },
    shell: { ...defaultShellData },
  };
}
