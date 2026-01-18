import { useState } from 'react';
import type { Device } from '../types';
import { ConfirmButton } from './ui/ConfirmButton';
import { useDevicePollProgress } from '../context/PollStatusContext';

type DeviceState = -1 | 0 | 1 | 2 | 3;

/** Extract host/URL from device - for shell devices, parse from commands */
function extractDeviceHost(device: Device): string | null {
  // For non-shell devices, use host directly (unless it's a placeholder)
  if (device.device_type !== 'shell') {
    return device.host || null;
  }

  // For shell devices, extract from command URLs
  const commands = device.config?.commands;
  if (!commands || typeof commands !== 'object') return null;

  // Look through all commands for URLs
  const urlPattern = /https?:\/\/([a-zA-Z0-9._-]+(?::\d+)?)/;

  for (const cmd of Object.values(commands)) {
    const cmdStr = typeof cmd === 'object' && cmd !== null ? (cmd as any).cmd : cmd;
    if (typeof cmdStr === 'string') {
      const match = cmdStr.match(urlPattern);
      if (match) {
        return match[1]; // Return just the host:port part
      }
    }
  }

  return null;
}

/** Build a clickable URL for the device */
function buildDeviceUrl(host: string, deviceType: string): string | null {
  if (!host || host === '#nohost') return null;

  // If host already has a port, use http
  if (host.includes(':')) {
    return `http://${host}`;
  }

  // For projectors, typically no web interface on default port
  if (deviceType === 'pjlink') {
    return null; // PJLink uses port 4352, not HTTP
  }

  // For power strips and shell devices, try http
  return `http://${host}`;
}

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

/** Clickable host link with copy button */
function HostLink({ device }: { device: Device }) {
  const [copied, setCopied] = useState(false);

  const host = extractDeviceHost(device);
  const url = host ? buildDeviceUrl(host, device.device_type) : null;

  if (!host || host === '#nohost') {
    return <span className="host-value">-</span>;
  }

  const handleCopy = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(host);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  return (
    <span className="host-link-container">
      {url ? (
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="host-link"
          onClick={(e) => e.stopPropagation()}
          title={`Open ${url}`}
        >
          {host}
        </a>
      ) : (
        <span className="host-value">{host}</span>
      )}
      <button
        className="btn-copy"
        onClick={handleCopy}
        title="Copy to clipboard"
      >
        {copied ? '✓' : '📋'}
      </button>
    </span>
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
        <span><strong>Host:</strong> <HostLink device={device} /></span>
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
