import type { Device } from '../types';
import { ConfirmButton } from './ui/ConfirmButton';
import { useDevicePollProgress } from '../context/PollStatusContext';

type DeviceState = -1 | 0 | 1 | 2 | 3;

interface DeviceAccordionProps {
  device: Device;
  isOpen: boolean;
  editMode?: boolean;
  pendingState?: 'on' | 'off';
  onControl: (deviceId: string, command: 'on' | 'off', deviceName: string) => void;
  onAction: (deviceId: string, actionName: string, deviceName: string) => void;
  onEdit?: (device: Device) => void;
  onDelete?: (deviceId: string, deviceName: string) => void;
}

function getDeviceStateLabel(state: DeviceState): string {
  switch (state) {
    case 1: return 'ON';
    case 0: return 'OFF';
    case 2: return 'COOLING';
    case 3: return 'WARMING';
    default: return 'ERROR';
  }
}

function PollProgressBar({ progress, isFastPolling, isVerifying }: { progress: number; isFastPolling: boolean; isVerifying: boolean }) {
  return (
    <div className="poll-progress-container">
      <div
        className={`poll-progress-bar ${isFastPolling ? 'fast' : ''} ${isVerifying ? 'verifying' : ''}`}
        style={{ width: `${progress}%` }}
      />
    </div>
  );
}

export function DeviceAccordion({ device, isOpen, editMode, pendingState, onControl, onAction, onEdit, onDelete }: DeviceAccordionProps) {
  // Use SSE-driven progress from context, with API data as fallback
  const { progress, isVerifying, secondsRemaining } = useDevicePollProgress(device.id, device.poll_status);
  const isFastPolling = device.poll_status?.is_fast_polling || isVerifying;

  // Show stripes if: client-side pending state OR server-side verifying
  const pendingClass = pendingState
    ? `pending-${pendingState}`
    : isVerifying
      ? `pending-${device.state === 1 ? 'on' : 'off'}`
      : '';

  return (
    <div className={`device-accordion ${isOpen ? 'open' : ''} ${pendingClass}`}>
      <PollProgressBar progress={progress} isFastPolling={isFastPolling} isVerifying={isVerifying} />
      <div className="accordion-header">
        <span>{device.name}</span>
        {editMode && (
          <div className="accordion-header-actions">
            {onEdit && (
              <button className="btn btn-edit btn-sm" onClick={() => onEdit(device)}>Edit</button>
            )}
            {onDelete && (
              <ConfirmButton
                className="btn btn-delete btn-sm"
                onConfirm={() => onDelete(device.id, device.name)}
                confirmText="Sure?"
              >
                Delete
              </ConfirmButton>
            )}
          </div>
        )}
      </div>
      <div className="device-info-compact">
        <span><strong>Host:</strong> {device.host}</span>
        <span><strong>Type:</strong> {device.device_type}</span>
        {device.device_type !== 'shell' && <span><strong>Port:</strong> {device.port || '-'}</span>}
        <span><strong>State:</strong> {getDeviceStateLabel(device.state as DeviceState)}</span>
        <span><strong>Next poll:</strong> {secondsRemaining}s</span>
      </div>
      {/* Shell command details */}
      {device.device_type === 'shell' && device.config?.commands && (
        <div className="shell-commands-info">
          {device.config.commands.status?.cmd && (
            <div className="shell-cmd-row">
              <span className="shell-cmd-label">Status:</span>
              <code className="shell-cmd-value">{device.config.commands.status.cmd}</code>
              {(device.config.commands.status.onPattern || device.config.commands.status.offPattern) && (
                <span className="shell-cmd-patterns">
                  {device.config.commands.status.onPattern && <span className="pattern-on">ON: {device.config.commands.status.onPattern}</span>}
                  {device.config.commands.status.offPattern && <span className="pattern-off">OFF: {device.config.commands.status.offPattern}</span>}
                </span>
              )}
            </div>
          )}
          {device.config.commands.on?.cmd && (
            <div className="shell-cmd-row">
              <span className="shell-cmd-label">ON:</span>
              <code className="shell-cmd-value">{device.config.commands.on.cmd}</code>
            </div>
          )}
          {device.config.commands.off?.cmd && (
            <div className="shell-cmd-row">
              <span className="shell-cmd-label">OFF:</span>
              <code className="shell-cmd-value">{device.config.commands.off.cmd}</code>
            </div>
          )}
          {device.config.commands.reachable?.cmd && (
            <div className="shell-cmd-row">
              <span className="shell-cmd-label">Reachable:</span>
              <code className="shell-cmd-value">{device.config.commands.reachable.cmd}</code>
            </div>
          )}
          {/* Show custom actions */}
          {device.config?.commands && typeof device.config.commands === 'object' && Object.entries(device.config.commands || {})
            .filter(([key]) => !['on', 'off', 'status', 'reachable'].includes(key))
            .map(([name, cfg]: [string, any]) => (
              <div key={name} className="shell-cmd-row">
                <span className="shell-cmd-label">{name}:</span>
                <code className="shell-cmd-value">{cfg?.cmd}</code>
              </div>
            ))
          }
        </div>
      )}
      <div className="device-actions">
        {/* Custom action buttons (always shown if device has actions) */}
        {device.actions && device.actions.length > 0 && (
          <div className="device-custom-commands">
            {device.actions.map(action => (
              <ConfirmButton
                key={action.name}
                className="btn btn-action btn-sm"
                onConfirm={() => onAction(device.id, action.name, device.name)}
                confirmText="Run?"
              >
                {action.name}
              </ConfirmButton>
            ))}
          </div>
        )}
        {/* ON/OFF buttons - shown for devices that support ON/OFF */}
        {(device.device_type !== 'shell' || (device.config?.commands?.on?.cmd && device.config?.commands?.off?.cmd)) && (
          <div className="btn-group">
            <ConfirmButton
              className="btn btn-on btn-sm"
              onConfirm={() => onControl(device.id, 'on', device.name)}
              confirmText="ON?"
            >
              ON
            </ConfirmButton>
            <ConfirmButton
              className="btn btn-off btn-sm"
              onConfirm={() => onControl(device.id, 'off', device.name)}
              confirmText="OFF?"
            >
              OFF
            </ConfirmButton>
          </div>
        )}
        {/* Show indicator if manual control only */}
        {!device.automation_enabled && (
          <span className="manual-indicator" title="Manual control only - not in bulk ON/OFF">
            <i className="bi bi-hand-index"></i> Manual
          </span>
        )}
      </div>
    </div>
  );
}
