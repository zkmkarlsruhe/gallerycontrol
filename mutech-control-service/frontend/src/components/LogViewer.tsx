import { useState, useEffect, useCallback, useRef } from 'react';
import { useMobile } from '../hooks/useMobile';

const API_BASE = import.meta.env.VITE_API_BASE || '';

interface TimelineEntry {
  id: string;
  type: 'operation' | 'state_change';
  device_id: string;
  device_name: string;
  device_type: string;
  artwork_name?: string;
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
  artworkName: string;
  exhibitionName: string;
}

interface LogViewerProps {
  onClose: () => void;
  initialFilterDeviceId?: string | null;
  devices: DeviceOption[];
}

interface TaskStatus {
  enabled: boolean;
  interval_seconds: number;
  last_run_at: string | null;
  next_run_at: string;
  fail_count: number;
  circuit_open: boolean;
  is_running: boolean;
  last_error: string | null;
  last_result: Record<string, unknown> | null;
}

interface SchedulerStatus {
  enabled: boolean;
  running: boolean;
  check_interval_seconds: number;
  tasks: Record<string, TaskStatus>;
}

const STATE_NAMES: Record<number, string> = {
  [-1]: 'ERR',
  0: 'OFF',
  1: 'ON',
  2: 'COOL',
  3: 'WARM',
};

function formatLogTime(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleTimeString('de-DE', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
}

function formatLogTimeFull(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleString('de-DE', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
}

function formatTimeAgo(isoString: string | null): string {
  if (!isoString) return 'Never';
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);

  if (diffSec < 60) return `${diffSec}s ago`;
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  return date.toLocaleDateString();
}

function formatLogLine(entry: TimelineEntry, advanced: boolean): { time: string; level: string; message: string; details?: string } {
  const time = advanced ? formatLogTimeFull(entry.timestamp) : formatLogTime(entry.timestamp);
  const artwork = entry.artwork_name ? entry.artwork_name.substring(0, advanced ? 30 : 18) : '';
  const device = entry.device_name.substring(0, advanced ? 25 : 15);
  const prefix = artwork ? `${artwork}/${device}` : device;

  if (entry.type === 'operation') {
    const level = entry.success ? 'OK' : 'ERR';

    let details = '';
    if (entry.error_message) {
      if (advanced) {
        // Show full error in advanced mode
        details = entry.error_message;
      } else {
        // Shorten common error messages
        let err = entry.error_message;
        if (err.includes('Timeout')) err = 'Timeout';
        else if (err.includes('Connection refused')) err = 'Refused';
        else if (err.includes('name resolution')) err = 'DNS fail';
        else if (err.length > 20) err = err.substring(0, 20) + '...';
        details = ` ${err}`;
      }
    }

    if (advanced) {
      const parts = [];
      if (entry.operation_type) parts.push(`op=${entry.operation_type}`);
      if (entry.source) parts.push(`src=${entry.source}`);
      if (entry.duration_ms !== undefined) parts.push(`${entry.duration_ms}ms`);
      const advancedDetails = parts.length > 0 ? parts.join(' | ') : undefined;

      return {
        time,
        level,
        message: `[${entry.device_type}] ${prefix}`,
        details: details || advancedDetails ? `${details}${details && advancedDetails ? ' | ' : ''}${advancedDetails || ''}` : undefined
      };
    }

    return {
      time,
      level,
      message: `${prefix}${details}`
    };
  } else {
    const level = 'CHG';
    const change = `${STATE_NAMES[entry.previous_state!] || '?'}->${STATE_NAMES[entry.new_state!] || '?'}`;

    if (advanced) {
      const parts = [];
      if (entry.trigger) parts.push(`trigger=${entry.trigger}`);
      const advancedDetails = parts.length > 0 ? parts.join(' | ') : undefined;

      return {
        time,
        level,
        message: `[${entry.device_type}] ${prefix} ${change}`,
        details: advancedDetails
      };
    }

    return {
      time,
      level,
      message: `${prefix} ${change}`
    };
  }
}

export function LogViewer({ onClose, initialFilterDeviceId, devices }: LogViewerProps) {
  const isMobile = useMobile();
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterDeviceId, setFilterDeviceId] = useState<string | null>(initialFilterDeviceId || null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [paused, setPaused] = useState(false);
  const [showOnlyErrors, setShowOnlyErrors] = useState(false);
  const [advancedView, setAdvancedView] = useState(false);
  const [schedulerStatus, setSchedulerStatus] = useState<SchedulerStatus | null>(null);
  const [schedulerExpanded, setSchedulerExpanded] = useState(false);
  const logContainerRef = useRef<HTMLDivElement>(null);

  // Force simple view on mobile
  const effectiveAdvancedView = isMobile ? false : advancedView;

  const fetchTimeline = useCallback(async () => {
    if (paused) return;

    try {
      setError(null);
      const url = filterDeviceId
        ? `${API_BASE}/api/debug/timeline?device_id=${filterDeviceId}&limit=500`
        : `${API_BASE}/api/debug/timeline?limit=500`;

      const response = await fetch(url);
      if (!response.ok) throw new Error('Failed to fetch logs');
      const data = await response.json();
      setTimeline(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [filterDeviceId, paused]);

  const fetchSchedulerStatus = useCallback(async () => {
    if (!effectiveAdvancedView) return;

    try {
      const response = await fetch(`${API_BASE}/api/admin/scheduler/status`);
      if (response.ok) {
        const data = await response.json();
        setSchedulerStatus(data);
      }
    } catch {
      // Silently fail - scheduler status is optional
    }
  }, [effectiveAdvancedView]);

  useEffect(() => {
    fetchTimeline();
    const interval = setInterval(fetchTimeline, 3000);
    return () => clearInterval(interval);
  }, [fetchTimeline]);

  useEffect(() => {
    if (effectiveAdvancedView) {
      fetchSchedulerStatus();
      const interval = setInterval(fetchSchedulerStatus, 5000);
      return () => clearInterval(interval);
    }
  }, [effectiveAdvancedView, fetchSchedulerStatus]);

  useEffect(() => {
    if (autoScroll && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [timeline, autoScroll]);

  // Update filter when initialFilterDeviceId changes
  useEffect(() => {
    if (initialFilterDeviceId !== undefined) {
      setFilterDeviceId(initialFilterDeviceId);
    }
  }, [initialFilterDeviceId]);

  const filteredDeviceName = filterDeviceId
    ? devices.find(d => d.id === filterDeviceId)?.name || timeline[0]?.device_name || 'device'
    : null;

  // Reverse timeline for journalctl-style (newest at bottom) and apply error filter
  let displayTimeline = [...timeline].reverse();
  if (showOnlyErrors) {
    displayTimeline = displayTimeline.filter(e => e.type === 'operation' && e.success === false);
  }

  const errorCount = timeline.filter(e => e.type === 'operation' && e.success === false).length;
  const stateChangeCount = timeline.filter(e => e.type === 'state_change').length;

  return (
    <div className={`log-viewer-page ${isMobile ? 'log-viewer-mobile' : ''} ${effectiveAdvancedView ? 'log-viewer-advanced' : 'log-viewer-simple'}`}>
      {/* Header */}
      <div className="log-viewer-header">
        <div className="log-viewer-header-left">
          <button className="btn btn-sm btn-outline-light" onClick={onClose}>
            <i className="bi bi-arrow-left"></i>
            {!isMobile && <span className="ms-1">Back</span>}
          </button>
          <h2>
            <i className="bi bi-terminal"></i>
            {!isMobile && (
              <span className="ms-2">
                {effectiveAdvancedView ? 'Advanced Logs' : 'Logs'}
              </span>
            )}
          </h2>
          {filteredDeviceName && (
            <span className={`badge bg-warning text-dark ${isMobile ? 'log-filter-badge-mobile' : ''}`}>
              {filteredDeviceName}
            </span>
          )}
        </div>
        <div className="log-viewer-header-right">
          {/* Stats - hidden on mobile */}
          {!isMobile && (
            <span className="log-stats text-muted me-2">
              {displayTimeline.length}
              {errorCount > 0 && (
                <span className="text-danger ms-1">/ {errorCount} err</span>
              )}
              {effectiveAdvancedView && stateChangeCount > 0 && (
                <span className="text-warning ms-1">/ {stateChangeCount} chg</span>
              )}
            </span>
          )}

          {/* Advanced toggle - desktop only */}
          {!isMobile && (
            <button
              className={`btn btn-sm ${advancedView ? 'btn-info' : 'btn-outline-info'} me-1`}
              onClick={() => setAdvancedView(!advancedView)}
              title={advancedView ? 'Switch to simple view' : 'Switch to advanced view'}
            >
              <i className={`bi bi-${advancedView ? 'phone' : 'display'}`}></i>
              <span className="ms-1">{advancedView ? 'Simple' : 'Advanced'}</span>
            </button>
          )}

          {/* Error filter */}
          <button
            className={`btn btn-sm ${showOnlyErrors ? 'btn-danger' : 'btn-outline-danger'}`}
            onClick={() => setShowOnlyErrors(!showOnlyErrors)}
            title={showOnlyErrors ? 'Show all entries' : 'Show only errors'}
          >
            <i className={`bi bi-exclamation-triangle${showOnlyErrors ? '-fill' : ''}`}></i>
          </button>

          {/* Pause/Resume */}
          <button
            className={`btn btn-sm ${paused ? 'btn-warning' : 'btn-outline-secondary'}`}
            onClick={() => setPaused(!paused)}
            title={paused ? 'Resume auto-refresh' : 'Pause auto-refresh'}
          >
            <i className={`bi bi-${paused ? 'play-fill' : 'pause-fill'}`}></i>
          </button>

          {/* Auto-scroll */}
          <button
            className={`btn btn-sm ${autoScroll ? 'btn-outline-light' : 'btn-outline-secondary'}`}
            onClick={() => setAutoScroll(!autoScroll)}
            title={autoScroll ? 'Auto-scroll enabled' : 'Auto-scroll disabled'}
          >
            <i className={`bi bi-arrow-down-circle${autoScroll ? '-fill' : ''}`}></i>
          </button>

          {/* Clear filter */}
          {filterDeviceId && (
            <button
              className="btn btn-sm btn-outline-warning"
              onClick={() => setFilterDeviceId(null)}
              title="Clear device filter"
            >
              <i className="bi bi-x-lg"></i>
            </button>
          )}

          {/* Refresh */}
          <button
            className="btn btn-sm btn-outline-light"
            onClick={() => { fetchTimeline(); fetchSchedulerStatus(); }}
            title="Refresh logs"
          >
            <i className="bi bi-arrow-clockwise"></i>
          </button>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="log-viewer-filter-bar">
        <select
          className="form-select form-select-sm log-viewer-filter-select"
          value={filterDeviceId || ''}
          onChange={(e) => setFilterDeviceId(e.target.value || null)}
        >
          <option value="">-- all devices --</option>
          {(() => {
            // Group devices by exhibition
            const byExhibition = new Map<string, DeviceOption[]>();
            for (const device of devices) {
              const list = byExhibition.get(device.exhibitionName) || [];
              list.push(device);
              byExhibition.set(device.exhibitionName, list);
            }
            // Sort exhibitions alphabetically
            const sortedExhibitions = Array.from(byExhibition.keys()).sort((a, b) => a.localeCompare(b));
            return sortedExhibitions.map(exhibitionName => {
              const exhibitionDevices = byExhibition.get(exhibitionName)!;
              // Sort devices within exhibition by artwork name, then device name
              exhibitionDevices.sort((a, b) =>
                a.artworkName.localeCompare(b.artworkName) || a.name.localeCompare(b.name)
              );
              return (
                <optgroup key={exhibitionName} label={exhibitionName}>
                  {exhibitionDevices.map(device => (
                    <option key={device.id} value={device.id}>
                      {device.artworkName} / {device.name} [{device.type}]
                    </option>
                  ))}
                </optgroup>
              );
            });
          })()}
        </select>
      </div>

      {/* Advanced: Scheduler Status Panel */}
      {effectiveAdvancedView && schedulerStatus && (
        <div className="log-viewer-scheduler-panel">
          <div
            className="log-viewer-scheduler-header"
            onClick={() => setSchedulerExpanded(!schedulerExpanded)}
          >
            <span>
              <i className={`bi bi-chevron-${schedulerExpanded ? 'down' : 'right'} me-2`}></i>
              <i className="bi bi-clock-history me-2"></i>
              Task Scheduler
              <span className={`badge ms-2 ${schedulerStatus.running ? 'bg-success' : 'bg-secondary'}`}>
                {schedulerStatus.running ? 'Running' : 'Stopped'}
              </span>
            </span>
            <span className="text-muted">
              {Object.keys(schedulerStatus.tasks).length} tasks
            </span>
          </div>
          {schedulerExpanded && (
            <div className="log-viewer-scheduler-body">
              {Object.entries(schedulerStatus.tasks).map(([taskName, task]) => (
                <div key={taskName} className="log-viewer-scheduler-task">
                  <div className="scheduler-task-row">
                    <span className="scheduler-task-name">
                      {taskName}
                      {task.is_running && (
                        <span className="badge bg-info ms-2">
                          <span className="spinner-border spinner-border-sm me-1" style={{ width: '0.6em', height: '0.6em' }}></span>
                          Running
                        </span>
                      )}
                      {task.circuit_open && (
                        <span className="badge bg-danger ms-2">Circuit Open</span>
                      )}
                    </span>
                    <span className="scheduler-task-timing">
                      Last: {formatTimeAgo(task.last_run_at)} |
                      Next: {formatTimeAgo(task.next_run_at).replace(' ago', '')}
                      {task.fail_count > 0 && (
                        <span className="text-danger ms-2">({task.fail_count} fails)</span>
                      )}
                    </span>
                  </div>
                  {task.last_error && (
                    <div className="scheduler-task-error">
                      <i className="bi bi-exclamation-triangle text-danger me-1"></i>
                      {task.last_error}
                    </div>
                  )}
                  {task.last_result && !task.last_error && (
                    <div className="scheduler-task-result">
                      <i className="bi bi-check-circle text-success me-1"></i>
                      {JSON.stringify(task.last_result)}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Log Container */}
      <div className="log-viewer-container" ref={logContainerRef}>
        {loading && timeline.length === 0 && (
          <div className="log-viewer-line text-muted">Loading...</div>
        )}

        {error && (
          <div className="log-viewer-line text-danger">ERROR: {error}</div>
        )}

        {!loading && !error && displayTimeline.length === 0 && (
          <div className="log-viewer-line text-muted">
            -- No log entries in the last 24 hours {filterDeviceId ? 'for this device' : ''} --
          </div>
        )}

        {displayTimeline.map((entry, idx) => {
          const { time, level, message, details } = formatLogLine(entry, effectiveAdvancedView);
          const levelClass = level === 'ERR' ? 'log-error' : level === 'CHG' ? 'log-state' : 'log-info';

          return (
            <div
              key={entry.id || idx}
              className={`log-viewer-line ${levelClass} ${effectiveAdvancedView ? 'log-viewer-line-advanced' : ''}`}
              onClick={() => setFilterDeviceId(entry.device_id)}
              title="Click to filter by this device"
            >
              <span className="log-time">{time}</span>
              <span className={`log-level ${levelClass}`}>{level}</span>
              <span className="log-message">{message}</span>
              {effectiveAdvancedView && details && (
                <span className="log-details">{details}</span>
              )}
            </div>
          );
        })}

        {paused && (
          <div className="log-viewer-line text-warning">
            -- PAUSED --
          </div>
        )}
      </div>
    </div>
  );
}
