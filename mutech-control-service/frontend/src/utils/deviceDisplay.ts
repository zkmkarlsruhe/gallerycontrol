import type { Device } from '../types';

/**
 * Format device name for display in UI.
 * - NETIO: "netzwerksteckdose-netio-009.zkm.de" -> "netio-009:1"
 * - ANEL: "netzwerksteckdose21.zkm.de" -> "anel-21:0"
 * - IP addresses: "192.168.232.69" -> "232.69"
 * - Others: name as-is
 */
export function formatDeviceDisplayName(device: Device): string {
  const { name, device_type, port } = device;

  // NETIO: extract "netio-XXX" and append :port
  if (device_type === 'netio') {
    const match = name.match(/netio-(\d+)/i);
    if (match) {
      return `netio-${match[1]}:${port}`;
    }
    // Fallback: just show name:port
    return `${name}:${port}`;
  }

  // ANEL: similar pattern
  if (device_type === 'anel') {
    const match = name.match(/netzwerksteckdose(\d+)/i);
    if (match) {
      return `anel-${match[1]}:${port}`;
    }
  }

  // IP addresses: show last 2 octets
  if (/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(name)) {
    return name.split('.').slice(2).join('.');
  }

  return name;
}
