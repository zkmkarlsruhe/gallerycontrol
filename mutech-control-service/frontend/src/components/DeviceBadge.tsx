import type { Device } from '../types';
import { useDevicePollProgress } from '../context/PollStatusContext';
import { formatDeviceDisplayName } from '../utils/deviceDisplay';

type DeviceState = -1 | 0 | 1 | 2 | 3;

interface DeviceBadgeProps {
  device: Device;
  isExpanded: boolean;
  pendingState?: 'on' | 'off';
  onClick: () => void;
}

function getDeviceStateClass(state: DeviceState): string {
  switch (state) {
    case 1: return 'device-on';
    case 0: return 'device-off';
    case 2: case 3: return 'device-cooling';
    default: return 'device-error';
  }
}

function getDeviceTypeIcon(type: string): string {
  switch (type) {
    case 'pjlink': return 'bi-projector';
    case 'shell': return 'bi-terminal';
    case 'netio': return 'bi-plug';
    case 'anel': return 'bi-lightning';
    default: return 'bi-device-hdd';
  }
}

function PollProgress({ device }: { device: Device }) {
  // Use SSE-driven progress from context, with API data as fallback
  const { progress, isVerifying } = useDevicePollProgress(device.id, device.poll_status);
  const isFastPolling = device.poll_status?.is_fast_polling || isVerifying;

  return (
    <div className="badge-progress-container">
      <div
        className={`badge-progress-bar ${isFastPolling ? 'fast' : ''} ${isVerifying ? 'verifying' : ''}`}
        style={{ width: `${progress}%` }}
      />
    </div>
  );
}

export function DeviceBadge({ device, isExpanded, pendingState, onClick }: DeviceBadgeProps) {
  const state = device.state as DeviceState;
  const hasCooldown = state === 2 || state === 3;
  const isDisabled = !device.enabled || !device.effective_enabled;
  const isVerifying = device.poll_status?.is_verifying || false;

  // Show stripes if: client-side pending state OR server-side verifying
  // When verifying from server (e.g. after refresh), use current state as the pending indicator
  const pendingClass = pendingState
    ? `pending-${pendingState}`
    : isVerifying
      ? `pending-${state === 1 ? 'on' : 'off'}`
      : '';

  return (
    <div
      className={`device-badge ${getDeviceStateClass(state)} ${isExpanded ? 'active' : ''} ${hasCooldown ? 'has-cooldown' : ''} ${isDisabled ? 'disabled' : ''} ${pendingClass}`}
      onClick={onClick}
      title={`${device.device_type} - ${device.host}${device.port ? ':' + device.port : ''}`}
    >
      <PollProgress device={device} />
      <span className="badge-content">
        <i className={`bi ${getDeviceTypeIcon(device.device_type)} badge-icon`}></i>
        <span className="badge-name">{formatDeviceDisplayName(device)}</span>
        {!device.automation_enabled && (
          <i className="bi bi-hand-index badge-manual" title="Manual control only"></i>
        )}
      </span>
      {hasCooldown && <span className="cooldown-indicator"></span>}
    </div>
  );
}
