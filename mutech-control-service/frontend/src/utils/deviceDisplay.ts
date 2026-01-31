// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT
import type { Device } from '../types';
import { portUtils } from './portUtils';

/**
 * Format device name for display in UI.
 * - NETIO hostname: "netzwerksteckdose-netio-009.zkm.de" -> "netio-009:1"
 * - ANEL hostname: "netzwerksteckdose21.zkm.de" -> "anel-21:1"
 * - IP addresses: "192.168.232.69" -> "232.69"
 * - Real names (e.g. "Devecchi", "Americas Finest"): name as-is
 */
export function formatDeviceDisplayName(device: Device): string {
  const { name, device_type, port } = device;
  // Convert 0-indexed DB port to 1-indexed display
  const displayPort = portUtils.dbToUI(port);

  // NETIO: only shorten if name matches hostname pattern "netio-XXX"
  if (device_type === 'netio') {
    const match = name.match(/netio-(\d+)/i);
    if (match) {
      return `netio-${match[1]}:${displayPort}`;
    }
    // Real name like "Devecchi" - just show as-is
    return name;
  }

  // ANEL: only shorten if name matches hostname pattern "netzwerksteckdoseXX"
  if (device_type === 'anel') {
    const match = name.match(/netzwerksteckdose(\d+)/i);
    if (match) {
      return `anel-${match[1]}:${displayPort}`;
    }
    // Real name - just show as-is
    return name;
  }

  // IP addresses: show last 2 octets
  if (/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(name)) {
    return name.split('.').slice(2).join('.');
  }

  return name;
}
