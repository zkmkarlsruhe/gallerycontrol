// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT
import { useState, useEffect } from 'react';
import type { Device, Artwork, ProtectionStatus, DeviceInfo, ShellCommand, DeviceAction } from '../types';
import { ConfirmButton } from './ui/ConfirmButton';
import { useDevicePollProgress, useProtectionStatus } from '../context/PollStatusContext';
import { useDeviceInfo } from '../hooks/useDeviceInfo';
import { formatDeviceDisplayName } from '../utils/deviceDisplay';
import { formatRelativeTime, formatSeconds } from '../utils/dateFormat';
import { portUtils } from '../utils/portUtils';

const API_BASE = import.meta.env.VITE_API_BASE || '';

type DeviceState = -1 | 0 | 1 | 2 | 3;

/** Extract host/URL from device - for shell devices, parse from commands */
function extractDeviceHost(device: Device): string | null {
  // For non-shell devices, use host directly (unless it's a placeholder)
  if (device.device_type !== 'shell') {
    return device.host || null;
  }

  // For shell devices, extract from command URLs
  if (device.device_type !== 'shell') return null;
  const shellConfig = device.config as { commands?: Record<string, string | ShellCommand> } | undefined;
  const commands = shellConfig?.commands;
  if (!commands || typeof commands !== 'object') return null;

  // Look through all commands for URLs
  const urlPattern = /https?:\/\/([a-zA-Z0-9._-]+(?::\d+)?)/;

  for (const cmd of Object.values(commands)) {
    const cmdStr = typeof cmd === 'object' && cmd !== null ? (cmd as ShellCommand).cmd : cmd;
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
  artwork: Artwork;
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

/** Freshness indicator for device info */
function FreshnessIndicator({ cachedAt, isStale }: { cachedAt?: Date | null; isStale?: boolean }) {
  if (!cachedAt) return null;
  const timeStr = formatRelativeTime(cachedAt);
  if (isStale) {
    return (
      <span className="device-info-freshness stale" title="Device offline - showing cached data">
        <i className="bi bi-exclamation-triangle"></i> Cached {timeStr}
      </span>
    );
  }
  return (
    <span className="device-info-freshness" title="Last updated">
      Updated {timeStr}
    </span>
  );
}

/** Display extended device info based on device type */
function DeviceInfoPanel({ info, loading, error, deviceType, cachedAt, isStale }: {
  info: DeviceInfo | null;
  loading: boolean;
  error: string | null;
  deviceType: string;
  cachedAt?: Date | null;
  isStale?: boolean;
}) {
  if (loading) {
    return (
      <div className="device-info-extended">
        <span className="text-muted"><i className="bi bi-arrow-repeat spin"></i> Loading device info...</span>
      </div>
    );
  }

  if (error && !info) {
    return (
      <div className="device-info-extended">
        <span className="text-danger"><i className="bi bi-exclamation-triangle"></i> {error}</span>
      </div>
    );
  }

  if (!info) return null;

  // Render based on device type
  if (deviceType === 'pjlink') {
    const pjInfo = info as { manufacturer?: string; product?: string; name?: string; lamp_hours?: number; lamp_on?: boolean; class?: number; has_errors?: boolean; has_warnings?: boolean; errors?: string };
    return (
      <div className="device-info-extended">
        <FreshnessIndicator cachedAt={cachedAt} isStale={isStale} />
        {pjInfo.manufacturer && <span><strong>Manufacturer:</strong> {pjInfo.manufacturer}</span>}
        {pjInfo.product && <span><strong>Model:</strong> {pjInfo.product}</span>}
        {pjInfo.name && <span><strong>Name:</strong> {pjInfo.name}</span>}
        {pjInfo.lamp_hours !== undefined && (
          <span><strong>Lamp:</strong> {pjInfo.lamp_hours}h {pjInfo.lamp_on ? '(on)' : '(off)'}</span>
        )}
        {pjInfo.class && <span><strong>Class:</strong> {pjInfo.class}</span>}
        {pjInfo.has_errors && <span className="text-danger"><strong>Errors:</strong> {pjInfo.errors}</span>}
        {pjInfo.has_warnings && <span className="text-warning"><strong>Warnings:</strong> {pjInfo.errors}</span>}
      </div>
    );
  }

  if (deviceType === 'netio') {
    const netInfo = info as { model?: string; mac?: string; firmware?: string; device_name?: string; voltage?: number; total_power?: number; uptime?: number };
    return (
      <div className="device-info-extended">
        <FreshnessIndicator cachedAt={cachedAt} isStale={isStale} />
        {netInfo.model && <span><strong>Model:</strong> {netInfo.model}</span>}
        {netInfo.mac && <span><strong>MAC:</strong> {netInfo.mac}</span>}
        {netInfo.firmware && <span><strong>Firmware:</strong> {netInfo.firmware}</span>}
        {netInfo.device_name && <span><strong>Name:</strong> {netInfo.device_name}</span>}
        {netInfo.voltage && <span><strong>Voltage:</strong> {netInfo.voltage}V</span>}
        {netInfo.total_power !== undefined && <span><strong>Power:</strong> {netInfo.total_power}W</span>}
        {netInfo.uptime && <span><strong>Uptime:</strong> {Math.floor(netInfo.uptime / 3600)}h</span>}
      </div>
    );
  }

  if (deviceType === 'anel') {
    const anelInfo = info as { name?: string; mac?: string; ip?: string; temperature?: number; ports?: unknown[] };
    return (
      <div className="device-info-extended">
        <FreshnessIndicator cachedAt={cachedAt} isStale={isStale} />
        {anelInfo.name && <span><strong>Name:</strong> {anelInfo.name}</span>}
        {anelInfo.mac && <span><strong>MAC:</strong> {anelInfo.mac}</span>}
        {anelInfo.ip && <span><strong>IP:</strong> {anelInfo.ip}</span>}
        {anelInfo.temperature !== undefined && <span><strong>Temp:</strong> {anelInfo.temperature}°C</span>}
        {anelInfo.ports && <span><strong>Ports:</strong> {anelInfo.ports.length}</span>}
      </div>
    );
  }

  // Generic fallback - show all info
  return (
    <div className="device-info-extended">
      <FreshnessIndicator cachedAt={cachedAt} isStale={isStale} />
      {Object.entries(info).map(([key, value]) => (
        <span key={key}><strong>{key}:</strong> {String(value)}</span>
      ))}
    </div>
  );
}

/** Protection status panel for artwork */
function ProtectionStatusPanel({ artwork, isOpen }: { artwork: Artwork; isOpen: boolean }) {
  const [fetchedStatus, setFetchedStatus] = useState<ProtectionStatus | null>(null);
  const [loading, setLoading] = useState(false);

  // Get real-time SSE updates for protection status
  const { status: sseStatus } = useProtectionStatus(artwork.id);

  // Use SSE status when available, fallback to fetched status
  const status = sseStatus || fetchedStatus;

  // Check if artwork has protection configured
  const hasProtection = Boolean(
    artwork.protection_config?.time_slices &&
    artwork.protection_config.time_slices.length > 0
  );

  useEffect(() => {
    if (!isOpen || !hasProtection) return;

    const fetchStatus = async () => {
      // Skip fetch if we already have SSE data
      if (sseStatus) {
        setLoading(false);
        return;
      }
      setLoading(true);
      try {
        const response = await fetch(`${API_BASE}/api/state/artworks/${artwork.id}/protection-status`);
        if (response.ok) {
          const data = await response.json();
          setFetchedStatus(data);
        }
      } catch (err) {
        console.error('Failed to fetch protection status:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchStatus();
    // Reduce polling to 30 seconds - SSE handles real-time updates
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, [artwork.id, isOpen, hasProtection, sseStatus]);

  if (!hasProtection) return null;
  if (!isOpen) return null;

  if (loading && !status) {
    return (
      <div className="protection-status-panel">
        <span className="text-muted"><i className="bi bi-arrow-repeat spin"></i> Loading protection status...</span>
      </div>
    );
  }

  if (!status?.state) return null;

  const { state } = status;

  return (
    <div className="protection-status-panel">
      <div className="protection-header">
        <i className="bi bi-shield-check"></i>
        <span>Protection Status</span>
        <span className={`protection-gate ${status.accepting_triggers ? 'active' : 'inactive'}`}>
          {status.accepting_triggers ? '⚡ Accepting triggers' : '○ Not accepting'}
        </span>
      </div>

      {/* Time slice budgets */}
      {state.time_slices && state.time_slices.length > 0 && (
        <div className="protection-budgets">
          {state.time_slices.map((slice) => {
            const usedPercent = Math.min(100, (slice.used / slice.max) * 100);
            const remainingMins = Math.floor(slice.remaining / 60);
            return (
              <div key={slice.window} className="budget-row">
                <span className="budget-label">{slice.window}m window:</span>
                <div className="budget-bar-container">
                  <div
                    className={`budget-bar ${usedPercent > 80 ? 'warning' : ''} ${usedPercent >= 100 ? 'depleted' : ''}`}
                    style={{ width: `${100 - usedPercent}%` }}
                  />
                </div>
                <span className="budget-value">{remainingMins}m left</span>
              </div>
            );
          })}
        </div>
      )}

      {/* Current session info */}
      <div className="protection-session">
        {state.is_running ? (
          <span className="session-running">
            <i className="bi bi-play-circle-fill"></i> Running: {formatSeconds(state.runtime_seconds)}
          </span>
        ) : state.cooldown_active ? (
          <span className="session-cooldown">
            <i className="bi bi-hourglass-split"></i> Cooldown: {formatSeconds(state.cooldown_remaining)} remaining
          </span>
        ) : (
          <span className="session-idle">
            <i className="bi bi-pause-circle"></i> Idle
          </span>
        )}

        {!state.can_start && state.block_reason && (
          <span className="session-blocked">
            <i className="bi bi-x-circle"></i> {state.block_reason}
          </span>
        )}
      </div>
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

export function DeviceAccordion({ device, artwork, isOpen, editMode, pendingState, onControl, onAction, onEdit, onDelete }: DeviceAccordionProps) {
  // Use SSE-driven progress from context, with API data as fallback
  const { progress, isVerifying, secondsRemaining } = useDevicePollProgress(device.id, device.poll_status);
  const isFastPolling = device.poll_status?.is_fast_polling || isVerifying;

  // Fetch extended device info when accordion is open (only for non-shell devices)
  const shouldFetchInfo = device.device_type !== 'shell' && isOpen;
  const { info: deviceInfo, loading: infoLoading, error: infoError, cachedAt, isStale } = useDeviceInfo(
    device.id,
    device.device_type,
    shouldFetchInfo
  );

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
        <span>{formatDeviceDisplayName(device)}</span>
        {editMode && (
          <div className="accordion-header-actions">
            {onEdit && (
              <button className="btn btn-edit btn-sm" onClick={() => onEdit(device)} title="Edit">
                <i className="bi bi-pencil"></i>
              </button>
            )}
            {onDelete && (
              <ConfirmButton
                className="btn btn-delete btn-sm"
                onConfirm={() => onDelete(device.id, device.name)}
                confirmText="Sure?"
                title="Delete"
              >
                <i className="bi bi-trash"></i>
              </ConfirmButton>
            )}
          </div>
        )}
      </div>
      <div className="device-info-compact">
        <span><strong>Host:</strong> <HostLink device={device} />
          {device.resolved && device.resolved !== device.host && (
            <span className="resolved-hostname" title="Resolved hostname"> → {device.resolved}</span>
          )}
        </span>
        <span><strong>Type:</strong> {device.device_type}</span>
        {(device.device_type === 'netio' || device.device_type === 'anel') && (
          <span><strong>Port:</strong> {device.port !== null && device.port !== undefined ? portUtils.dbToUI(device.port) : '-'}</span>
        )}
        {device.device_type === 'pjlink' && (
          <span><strong>Port:</strong> {device.port !== null && device.port !== undefined ? device.port : '-'}</span>
        )}
        <span><strong>State:</strong> {getDeviceStateLabel(device.state as DeviceState)}</span>
        {device.device_type === 'pjlink' && (
          <span><strong>Lamp:</strong> {device.lamp_hours !== null && device.lamp_hours !== undefined ? `${device.lamp_hours}h` : '-'}</span>
        )}
        <span><strong>Next poll:</strong> {secondsRemaining}s</span>
      </div>
      {/* Extended device info (MAC, lamp hours, etc.) - shown when open */}
      {isOpen && device.device_type !== 'shell' && (
        <DeviceInfoPanel
          info={deviceInfo}
          loading={infoLoading}
          error={infoError}
          deviceType={device.device_type}
          cachedAt={cachedAt}
          isStale={isStale}
        />
      )}
      {/* Protection status - shown when open and artwork has protection */}
      <ProtectionStatusPanel artwork={artwork} isOpen={isOpen} />
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
          {/* Show custom actions from config.actions (new format) */}
          {device.config && 'actions' in device.config && Array.isArray(device.config.actions) && device.config.actions.map((action: DeviceAction) => (
            <div key={action.name} className="shell-cmd-row">
              <span className="shell-cmd-label">{action.name}:</span>
              <code className="shell-cmd-value">{action.cmd}</code>
            </div>
          ))}
          {/* Fallback: show custom actions from commands dict (old format) */}
          {device.config && !('actions' in device.config) && 'commands' in device.config && device.config.commands && typeof device.config.commands === 'object' && Object.entries(device.config.commands as Record<string, string | { cmd?: string }>)
            .filter(([key]) => !['on', 'off', 'status', 'reachable'].includes(key))
            .map(([name, cfg]) => (
              <div key={name} className="shell-cmd-row">
                <span className="shell-cmd-label">{name}:</span>
                <code className="shell-cmd-value">{typeof cfg === 'object' && cfg !== null ? cfg.cmd : cfg}</code>
              </div>
            ))
          }
        </div>
      )}
      {/* Device controls - unified template */}
      <div className="device-actions">
        {/* ON/OFF buttons - shown for non-shell devices, or shell devices with on/off commands */}
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
        {/* Custom action buttons */}
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
        {/* Manual control indicator */}
        {!device.automation_enabled && (
          <span className="manual-indicator" title="Manual control only - not in bulk ON/OFF">
            <i className="bi bi-hand-index"></i> Manual
          </span>
        )}
      </div>
    </div>
  );
}
