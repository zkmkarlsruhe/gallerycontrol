// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT
/**
 * Device form payload helpers.
 * Handles conversion between UI form data and API payloads.
 */

import type { Device } from '../../../types';
import { portUtils } from '../../../utils/portUtils';
import type {
  DeviceType,
  DeviceFormSlices,
  DevicePayload,
  PJLinkFormData,
  NetioFormData,
  AnelFormData,
  ShellFormData,
  ShellAction,
} from './deviceForm.types';
import { getDefaultSlices } from './deviceForm.types';

/**
 * Build API payload from form state.
 * Handles all device type-specific transformations.
 */
export function buildDevicePayload(
  deviceType: DeviceType,
  slices: DeviceFormSlices,
  includeDeviceType: boolean = true
): DevicePayload {
  switch (deviceType) {
    case 'pjlink':
      return buildPJLinkPayload(slices.pjlink, includeDeviceType);
    case 'netio':
      return buildNetioPayload(slices.netio, includeDeviceType);
    case 'anel':
      return buildAnelPayload(slices.anel, includeDeviceType);
    case 'shell':
      return buildShellPayload(slices.shell, includeDeviceType);
  }
}

function buildPJLinkPayload(data: PJLinkFormData, includeDeviceType: boolean): DevicePayload {
  return {
    name: data.name,
    ...(includeDeviceType && { device_type: 'pjlink' }),
    host: data.host,
    port: data.port,
    enabled: data.enabled,
    automation_enabled: data.automation_enabled,
    config: data.credential_id ? { credential_id: data.credential_id } : {},
  };
}

function buildNetioPayload(data: NetioFormData, includeDeviceType: boolean): DevicePayload {
  // Convert 1-indexed UI port to 0-indexed DB port
  return {
    name: data.name,
    ...(includeDeviceType && { device_type: 'netio' }),
    host: data.host,
    port: portUtils.uiToDB(data.port),
    enabled: data.enabled,
    automation_enabled: data.automation_enabled,
    config: data.credential_id ? { credential_id: data.credential_id } : {},
  };
}

function buildAnelPayload(data: AnelFormData, includeDeviceType: boolean): DevicePayload {
  // Convert 1-indexed UI port to 0-indexed DB port
  return {
    name: data.name,
    ...(includeDeviceType && { device_type: 'anel' }),
    host: data.host,
    port: portUtils.uiToDB(data.port),
    enabled: data.enabled,
    automation_enabled: data.automation_enabled,
    config: data.credential_id ? { credential_id: data.credential_id } : {},
  };
}

interface ShellCommandConfig {
  cmd: string;
  onPattern?: string;
  offPattern?: string;
}

function buildShellPayload(data: ShellFormData, includeDeviceType: boolean): DevicePayload {
  // Build commands object
  const shellCommands: Record<string, ShellCommandConfig> = {};

  // Status command (always included if set)
  if (data.status_cmd) {
    shellCommands.status = {
      cmd: data.status_cmd,
      onPattern: data.on_pattern || undefined,
      offPattern: data.off_pattern || undefined,
    };
  }

  // ON/OFF commands (optional)
  if (data.on_cmd) {
    shellCommands.on = { cmd: data.on_cmd };
  }
  if (data.off_cmd) {
    shellCommands.off = { cmd: data.off_cmd };
  }

  // Custom actions - stored in separate actions array
  const shellActions = data.actions
    .filter(a => a.name && a.cmd)
    .map(a => ({ name: a.name, cmd: a.cmd }));

  // Automation requires both ON and OFF commands
  const hasOnOff = !!(data.on_cmd && data.off_cmd);

  return {
    name: data.name,
    ...(includeDeviceType && { device_type: 'shell' }),
    host: '#nohost',
    enabled: data.enabled,
    automation_enabled: hasOnOff && data.automation_enabled,
    config: {
      credential_id: data.credential_id || undefined,
      commands: shellCommands,
      actions: shellActions.length > 0 ? shellActions : undefined,
    },
  };
}

/**
 * Hydrate form slices from an existing device.
 * Returns the device type and fully populated slices.
 */
export function hydrateFromDevice(device: Device): { deviceType: DeviceType; slices: DeviceFormSlices } {
  const slices = getDefaultSlices();
  const deviceType = device.device_type as DeviceType;

  switch (deviceType) {
    case 'pjlink':
      slices.pjlink = hydratePJLinkData(device);
      break;
    case 'netio':
      slices.netio = hydrateNetioData(device);
      break;
    case 'anel':
      slices.anel = hydrateAnelData(device);
      break;
    case 'shell':
      slices.shell = hydrateShellData(device);
      break;
  }

  return { deviceType, slices };
}

function hydratePJLinkData(device: Device): PJLinkFormData {
  return {
    name: device.name,
    host: device.host,
    port: device.port || 4352,
    credential_id: device.config?.credential_id || '',
    enabled: device.enabled,
    automation_enabled: device.automation_enabled,
  };
}

function hydrateNetioData(device: Device): NetioFormData {
  return {
    name: device.name,
    host: device.host,
    // Convert 0-indexed DB port to 1-indexed UI
    port: portUtils.dbToUI(device.port),
    credential_id: device.config?.credential_id || '',
    enabled: device.enabled,
    automation_enabled: device.automation_enabled,
  };
}

function hydrateAnelData(device: Device): AnelFormData {
  return {
    name: device.name,
    host: device.host,
    // Convert 0-indexed DB port to 1-indexed UI
    port: portUtils.dbToUI(device.port),
    credential_id: device.config?.credential_id || '',
    enabled: device.enabled,
    automation_enabled: device.automation_enabled,
  };
}

function hydrateShellData(device: Device): ShellFormData {
  const commands = device.config?.commands || {};
  const hasOnOff = !!(commands.on?.cmd && commands.off?.cmd);

  // Extract custom actions from:
  // 1. New format: config.actions array
  // 2. Old format: commands that are not on/off/status (backwards compatibility)
  let customActions: ShellAction[] = [];

  // Check new actions array first
  if (device.config && 'actions' in device.config && Array.isArray(device.config.actions)) {
    customActions = (device.config.actions as Array<{ name?: string; cmd?: string }>)
      .filter((a) => a.name && a.cmd)
      .map((a) => ({ name: a.name!, cmd: a.cmd! }));
  }

  // Fall back to old format if no actions array
  if (customActions.length === 0) {
    customActions = Object.entries(commands)
      .filter(([key]) => !['on', 'off', 'status'].includes(key))
      .map(([name, cfg]) => ({ name, cmd: typeof cfg === 'object' && cfg !== null ? (cfg as { cmd?: string }).cmd || '' : '' }));
  }

  return {
    name: device.name,
    credential_id: device.config?.credential_id || '',
    onoff_mode: hasOnOff,
    automation_enabled: device.automation_enabled,
    status_cmd: commands.status?.cmd || '',
    on_pattern: commands.status?.onPattern || '',
    off_pattern: commands.status?.offPattern || '',
    on_cmd: commands.on?.cmd || '',
    off_cmd: commands.off?.cmd || '',
    actions: customActions,
    enabled: device.enabled,
  };
}

/**
 * Compute used ports for a given device type and host.
 * Returns 1-indexed port numbers (UI representation).
 */
export function computeUsedPorts(
  type: 'netio' | 'anel',
  host: string,
  existingDevices: Device[],
  excludeId?: string
): number[] {
  if (!host) return [];

  return existingDevices
    .filter(d => {
      if (d.device_type !== type) return false;
      if (d.host !== host) return false;
      if (d.port === null) return false;
      if (excludeId && d.id === excludeId) return false;
      return true;
    })
    .map(d => portUtils.dbToUI(d.port));
}
