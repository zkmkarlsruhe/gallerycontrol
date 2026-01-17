import { useState, useEffect, useCallback, useRef } from 'react';

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

function formatLogLine(entry: TimelineEntry): { time: string; level: string; message: string } {
  const time = formatLogTime(entry.timestamp);
  const artwork = entry.artwork_name ? entry.artwork_name.substring(0, 18) : '';
  const device = entry.device_name.substring(0, 15);
  const prefix = artwork ? `${artwork}/${device}` : device;

  if (entry.type === 'operation') {
    const level = entry.success ? 'OK' : 'ERR';

    let details = '';
    if (entry.error_message) {
      // Shorten common error messages
      let err = entry.error_message;
      if (err.includes('Timeout')) err = 'Timeout';
      else if (err.includes('Connection refused')) err = 'Refused';
      else if (err.includes('name resolution')) err = 'DNS fail';
      else if (err.length > 20) err = err.substring(0, 20) + '...';
      details = ` ${err}`;
    }

    return {
      time,
      level,
      message: `${prefix}${details}`
    };
  } else {
    const level = 'CHG';
    const change = `${STATE_NAMES[entry.previous_state!] || '?'}->${STATE_NAMES[entry.new_state!] || '?'}`;

    return {
      time,
      level,
      message: `${prefix} ${change}`
    };
  }
}

export function LogViewer({ onClose, initialFilterDeviceId, devices }: LogViewerProps) {
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterDeviceId, setFilterDeviceId] = useState<string | null>(initialFilterDeviceId || null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [paused, setPaused] = useState(false);
  const [showOnlyErrors, setShowOnlyErrors] = useState(false);
  const logContainerRef = useRef<HTMLDivElement>(null);

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

  useEffect(() => {
    fetchTimeline();
    const interval = setInterval(fetchTimeline, 3000);
    return () => clearInterval(interval);
  }, [fetchTimeline]);

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

  return (
    <div className="log-viewer-page">
      {/* Header */}
      <div className="log-viewer-header">
        <div className="log-viewer-header-left">
          <button className="btn btn-sm btn-outline-light" onClick={onClose}>
            <i className="bi bi-arrow-left me-1"></i>
            Back
          </button>
          <h2>
            <i className="bi bi-terminal me-2"></i>
            Log Viewer
          </h2>
          {filteredDeviceName && (
            <span className="badge bg-warning text-dark ms-2">
              {filteredDeviceName}
            </span>
          )}
        </div>
        <div className="log-viewer-header-right">
          <span className="text-muted me-3">
            {displayTimeline.length} entries
            {errorCount > 0 && (
              <span className="text-danger ms-2">({errorCount} errors)</span>
            )}
          </span>
          <button
            className={`btn btn-sm ${showOnlyErrors ? 'btn-danger' : 'btn-outline-danger'} me-1`}
            onClick={() => setShowOnlyErrors(!showOnlyErrors)}
            title={showOnlyErrors ? 'Show all' : 'Show only errors'}
          >
            <i className="bi bi-exclamation-triangle"></i>
          </button>
          <button
            className={`btn btn-sm ${paused ? 'btn-warning' : 'btn-outline-secondary'} me-1`}
            onClick={() => setPaused(!paused)}
            title={paused ? 'Resume' : 'Pause'}
          >
            <i className={`bi bi-${paused ? 'play-fill' : 'pause-fill'}`}></i>
          </button>
          <button
            className={`btn btn-sm ${autoScroll ? 'btn-outline-light' : 'btn-outline-secondary'} me-1`}
            onClick={() => setAutoScroll(!autoScroll)}
            title={autoScroll ? 'Auto-scroll ON' : 'Auto-scroll OFF'}
          >
            <i className="bi bi-arrow-down-circle"></i>
          </button>
          {filterDeviceId && (
            <button
              className="btn btn-sm btn-outline-warning me-1"
              onClick={() => setFilterDeviceId(null)}
              title="Clear filter"
            >
              <i className="bi bi-x-lg"></i>
            </button>
          )}
          <button
            className="btn btn-sm btn-outline-light"
            onClick={fetchTimeline}
            title="Refresh"
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
          const { time, level, message } = formatLogLine(entry);
          const levelClass = level === 'ERR' ? 'log-error' : level === 'CHG' ? 'log-state' : 'log-info';

          return (
            <div
              key={entry.id || idx}
              className={`log-viewer-line ${levelClass}`}
              onClick={() => setFilterDeviceId(entry.device_id)}
              title="Click to filter by this device"
            >
              <span className="log-time">{time}</span>
              <span className={`log-level ${levelClass}`}>{level}</span>
              <span className="log-message">{message}</span>
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
