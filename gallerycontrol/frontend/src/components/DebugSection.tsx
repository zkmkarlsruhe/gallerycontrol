// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT
import { useState, useEffect, useCallback, useRef, memo } from 'react';
import { formatLogTime } from '../utils/dateFormat';

const API_BASE = import.meta.env.VITE_API_BASE || '';

interface TimelineEntry {
  id: string;
  type: 'operation' | 'state_change';
  device_id: string;
  device_name: string;
  device_type: string;
  timestamp: string;
  operation_type?: string;
  source?: string;
  success?: boolean;
  state_before?: number;
  state_after?: number;
  error_message?: string | null;
  duration_ms?: number;
  previous_state?: number;
  new_state?: number;
  trigger?: string;
}

interface DeviceOption {
  id: string;
  name: string;
  type: string;
}

interface DebugSectionProps {
  editMode: boolean;
  filterDeviceId?: string | null;
  onFilterChange?: (deviceId: string | null) => void;
  devices?: DeviceOption[];
}

const STATE_NAMES: Record<number, string> = {
  [-1]: 'ERR',
  0: 'OFF',
  1: 'ON',
  2: 'COOL',
  3: 'WARM',
};

function formatLogLine(entry: TimelineEntry): { time: string; level: string; message: string } {
  const time = formatLogTime(entry.timestamp);

  if (entry.type === 'operation') {
    const level = entry.success ? 'INFO' : 'ERR ';
    const op = (entry.operation_type || 'unknown').padEnd(12);
    const device = entry.device_name.substring(0, 25).padEnd(25);
    const type = entry.device_type.padEnd(6);

    let details = '';
    if (entry.state_before !== undefined && entry.state_after !== undefined) {
      details = ` ${STATE_NAMES[entry.state_before] || '?'}->${STATE_NAMES[entry.state_after] || '?'}`;
    }
    if (entry.duration_ms !== undefined) {
      details += ` ${entry.duration_ms}ms`;
    }
    if (entry.error_message) {
      details += ` | ${entry.error_message}`;
    }

    return {
      time,
      level,
      message: `[${type}] ${device} ${op}${details}`
    };
  } else {
    const level = 'STATE';
    const device = entry.device_name.substring(0, 25).padEnd(25);
    const type = entry.device_type.padEnd(6);
    const change = `${STATE_NAMES[entry.previous_state!] || '?'}->${STATE_NAMES[entry.new_state!] || '?'}`;

    return {
      time,
      level,
      message: `[${type}] ${device} ${change.padEnd(12)} (${entry.trigger || 'unknown'})`
    };
  }
}

export const DebugSection = memo(function DebugSection({
  editMode,
  filterDeviceId,
  onFilterChange,
  devices = []
}: DebugSectionProps) {
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  const [localFilter, setLocalFilter] = useState<string>('');
  const [autoScroll, setAutoScroll] = useState(true);
  const [paused, setPaused] = useState(false);
  const logContainerRef = useRef<HTMLDivElement>(null);

  const activeFilter = filterDeviceId !== undefined ? filterDeviceId : (localFilter || null);

  const fetchTimeline = useCallback(async () => {
    if (paused) return;

    try {
      setError(null);
      const url = activeFilter
        ? `${API_BASE}/api/debug/timeline?device_id=${activeFilter}&limit=200`
        : `${API_BASE}/api/debug/timeline?limit=200`;

      const response = await fetch(url);
      if (!response.ok) throw new Error('Failed to fetch logs');
      const data = await response.json();
      setTimeline(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [activeFilter, paused]);

  useEffect(() => {
    if (editMode && !collapsed) {
      fetchTimeline();
      const interval = setInterval(fetchTimeline, 3000);
      return () => clearInterval(interval);
    }
  }, [editMode, collapsed, fetchTimeline]);

  useEffect(() => {
    if (autoScroll && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [timeline, autoScroll]);

  const handleFilterChange = (deviceId: string) => {
    if (onFilterChange) {
      onFilterChange(deviceId || null);
    } else {
      setLocalFilter(deviceId);
    }
  };

  const clearFilter = () => {
    if (onFilterChange) {
      onFilterChange(null);
    } else {
      setLocalFilter('');
    }
  };

  if (!editMode) return null;

  const filteredDeviceName = activeFilter
    ? devices.find(d => d.id === activeFilter)?.name || timeline[0]?.device_name || 'device'
    : null;

  // Reverse timeline for journalctl-style (newest at bottom)
  const sortedTimeline = [...timeline].reverse();

  return (
    <div className="debug-section debug-journal">
      <div className="debug-header" onClick={() => setCollapsed(!collapsed)}>
        <div className="debug-header-left">
          <i className={`bi bi-chevron-${collapsed ? 'right' : 'down'} me-2`}></i>
          <i className="bi bi-terminal me-2"></i>
          <span>Log Viewer</span>
          {activeFilter && (
            <span className="badge bg-warning text-dark ms-2">
              {filteredDeviceName}
            </span>
          )}
          <span className="text-muted ms-2 small">
            ({timeline.length} entries)
          </span>
        </div>
        <div className="debug-header-actions" onClick={e => e.stopPropagation()}>
          <button
            className={`btn btn-sm ${paused ? 'btn-warning' : 'btn-outline-secondary'} me-1`}
            onClick={() => setPaused(!paused)}
            title={paused ? 'Resume' : 'Pause'}
          >
            <i className={`bi bi-${paused ? 'play-fill' : 'pause-fill'}`}></i>
          </button>
          <button
            className={`btn btn-sm ${autoScroll ? 'btn-outline-secondary' : 'btn-outline-secondary'} me-1`}
            onClick={() => setAutoScroll(!autoScroll)}
            title={autoScroll ? 'Auto-scroll ON' : 'Auto-scroll OFF'}
          >
            <i className="bi bi-arrow-down-circle"></i>
          </button>
          {activeFilter && (
            <button
              className="btn btn-sm btn-outline-warning me-1"
              onClick={clearFilter}
              title="Clear filter"
            >
              <i className="bi bi-x-lg"></i>
            </button>
          )}
          <button
            className="btn btn-sm btn-outline-secondary"
            onClick={fetchTimeline}
            title="Refresh"
          >
            <i className="bi bi-arrow-clockwise"></i>
          </button>
        </div>
      </div>

      {!collapsed && (
        <div className="debug-content">
          {/* Filter Bar */}
          <div className="debug-filter-bar">
            <select
              className="form-select form-select-sm debug-filter-select"
              value={activeFilter || ''}
              onChange={(e) => handleFilterChange(e.target.value)}
            >
              <option value="">-- all devices --</option>
              {devices.map(device => (
                <option key={device.id} value={device.id}>
                  {device.name} [{device.type}]
                </option>
              ))}
            </select>
          </div>

          {/* Log Container */}
          <div className="debug-log-container" ref={logContainerRef}>
            {loading && timeline.length === 0 && (
              <div className="debug-log-line text-muted">Loading...</div>
            )}

            {error && (
              <div className="debug-log-line text-danger">ERROR: {error}</div>
            )}

            {!loading && !error && timeline.length === 0 && (
              <div className="debug-log-line text-muted">
                -- No log entries in the last 24 hours {activeFilter ? 'for this device' : ''} --
              </div>
            )}

            {sortedTimeline.map((entry, idx) => {
              const { time, level, message } = formatLogLine(entry);
              const levelClass = level === 'ERR ' ? 'log-error' : level === 'STATE' ? 'log-state' : 'log-info';

              return (
                <div
                  key={entry.id || idx}
                  className={`debug-log-line ${levelClass}`}
                  onClick={() => handleFilterChange(entry.device_id)}
                  title="Click to filter by this device"
                >
                  <span className="log-time">{time}</span>
                  <span className={`log-level ${levelClass}`}>{level}</span>
                  <span className="log-message">{message}</span>
                </div>
              );
            })}

            {paused && (
              <div className="debug-log-line text-warning">
                -- PAUSED --
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
});
