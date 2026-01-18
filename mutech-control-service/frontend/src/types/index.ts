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
}

export interface Artwork {
  id: string;
  name: string;
  enabled: boolean;
  effective_enabled: boolean;
  devices: Device[];
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
