// API Response Types

export interface DeviceAction {
  name: string;
  cmd: string;
}

export interface PollStatus {
  is_fast_polling: boolean;
  is_verifying: boolean;
  poll_count: number;
  poll_interval: number;
  last_polled_at: string | null;
  seconds_until_next_poll: number;
}

export interface Device {
  id: string;
  name: string;
  device_type: 'pjlink' | 'netio' | 'anel' | 'shell';
  host: string;
  port: number | null;
  state: -1 | 0 | 1 | 2 | 3; // -1=error, 0=off, 1=on, 2=cooling, 3=warming
  enabled: boolean;
  effective_enabled: boolean;
  automation_enabled: boolean; // false = manual device, needs inline buttons
  last_checked_at: string | null;
  next_check_allowed_at: string | null;
  poll_status: PollStatus | null;
  actions: DeviceAction[];
  config?: Record<string, any>; // Device-specific configuration
  resolved?: string | null; // Resolved hostname/IP from DNS
  asset_id?: string | null; // Linked asset ID (PJLink only)
  lamp_hours?: number | null; // Last recorded lamp hours (PJLink only)
}

export interface Artwork {
  id: string;
  name: string;
  enabled: boolean;
  effective_enabled: boolean;
  accepting_triggers: boolean; // Gate for fast-lane API triggers
  devices: Device[];
  protection_config?: ProtectionConfig | null;
}

export interface Exhibition {
  id: string;
  name: string;
  enabled: boolean;
  artworks: Artwork[];
}

// UI State Types

export type ViewMode = 'control' | 'all';

export interface AppState {
  exhibitions: Exhibition[];
  loading: boolean;
  error: string | null;
  lastUpdate: Date | null;
  isLocked: boolean;
  viewMode: ViewMode;
  isOnline: boolean;
}

// Control Result Types

export interface ControlResult {
  success: boolean;
  error?: string;
  action?: string;
  output?: string;
}

// Credential Types

export type CredentialType = 'shell' | 'pjlink' | 'netio' | 'anel';

export interface Credential {
  id: string;
  name: string;
  credential_type: CredentialType;
  username: string | null;
  password: string; // Always masked as "********" in responses
  description: string | null;
  created_at: string;
  updated_at: string;
  used_by: string[]; // Device names using this credential (max 3, then "and X more")
  used_by_count: number; // Total count of devices using this credential
}

export interface CredentialCreate {
  name: string;
  credential_type?: CredentialType;
  username?: string;
  password: string;
  description?: string;
}

export interface CredentialUpdate {
  name?: string;
  credential_type?: CredentialType;
  username?: string;
  password?: string;
  description?: string;
}

// Shell Template Types

export interface ShellTemplateAction {
  name: string;
  cmd: string;
}

export interface ShellTemplate {
  id: string;
  name: string;
  description: string | null;
  status_command: string | null;
  status_on_pattern: string | null;
  status_off_pattern: string | null;
  on_command: string | null;
  off_command: string | null;
  actions: ShellTemplateAction[];
  onoff_mode: boolean;
  created_at: string;
  updated_at: string;
}

export interface ShellTemplateCreate {
  name: string;
  description?: string;
  status_command?: string;
  status_on_pattern?: string;
  status_off_pattern?: string;
  on_command?: string;
  off_command?: string;
  actions?: ShellTemplateAction[];
  onoff_mode?: boolean;
}

export interface ShellTemplateUpdate {
  name?: string;
  description?: string;
  status_command?: string;
  status_on_pattern?: string;
  status_off_pattern?: string;
  on_command?: string;
  off_command?: string;
  actions?: ShellTemplateAction[];
  onoff_mode?: boolean;
}

// Asset Types

export interface Asset {
  id: string;
  asset_number: string;
  hostname: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  current_device_id: string | null;
  current_device_name: string | null;
  device_state: number | null;
  artwork_name: string | null;
  exhibition_name: string | null;
  last_lamp_hours: number | null;
  last_event_type: string | null;
  last_event_at: string | null;
}

export interface LampHoursLog {
  id: string;
  asset_id: string;
  device_id: string | null;
  lamp_hours: number;
  event_type: 'onboard' | 'power_on' | 'power_off' | 'offboard' | 'manual';
  exhibition_name: string | null;
  artwork_name: string | null;
  device_name: string | null;
  timestamp: string;
}

export interface AssetUpdate {
  hostname?: string;
  notes?: string;
}

export interface ManualLampHoursRequest {
  lamp_hours: number;
  device_id?: string;
  notes?: string;
}

// Protection Types

export interface ProtectionTimeSlice {
  window: number; // Window size in minutes
  max: number; // Max runtime in minutes
}

export interface ProtectionConfig {
  time_slices?: ProtectionTimeSlice[];
  max_runtime?: number; // Max continuous runtime in seconds
  cooldown?: number; // Cooldown period in seconds
  force_completion?: boolean; // Ignore OFF until max_runtime
  min_budget_to_start?: number; // Minimum budget to start (seconds)
}

export interface ProtectionTimeSliceStatus {
  window: number;
  used: number; // seconds
  max: number; // seconds
  remaining: number; // seconds
  resets_at: string; // ISO timestamp
}

export interface ProtectionStatus {
  accepting_triggers: boolean; // Gate for fast-lane API triggers
  protected: boolean;
  config?: ProtectionConfig;
  state?: {
    is_running: boolean;
    runtime_seconds: number;
    cooldown_active: boolean;
    cooldown_remaining: number;
    time_slices: ProtectionTimeSliceStatus[];
    can_start: boolean;
    block_reason: string | null;
  };
}

// Service Health Types

export type ServiceStatus = 'online' | 'offline' | 'degraded' | 'unknown';

export interface ServiceHealth {
  service_id: string;
  name: string;
  description: string;
  status: ServiceStatus;
  last_check: string | null;
  last_seen: string | null;
  error: string | null;
  response_time_ms: number | null;
  affects_device_types: string[];
  consecutive_failures: number;
}
