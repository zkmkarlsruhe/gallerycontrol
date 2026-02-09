// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT
import { useState, useEffect, useRef, useCallback, memo } from 'react';
import * as d3 from 'd3';
import { formatDuration } from '../utils/dateFormat';

const API_BASE = import.meta.env.VITE_API_BASE || '';

interface StateChange {
  id: string;
  device_id: string;
  device_name: string;
  device_type: string;
  device_host: string;
  previous_state: number;
  new_state: number;
  timestamp: string;
  trigger: string;
}

interface TimeSegment {
  device_id: string;
  device_name: string;
  device_type: string;
  device_host: string;
  state: number;
  start: Date;
  end: Date;
}

interface StateTimelineProps {
  editMode: boolean;
  filterDeviceId?: string | null;
  exhibitionId?: string | null;
}

const STATE_COLORS: Record<number, string> = {
  [-1]: '#dc3545', // error - red
  0: '#6c757d',    // off - gray
  1: '#28a745',    // on - green
  2: '#ffc107',    // cooling - yellow
  3: '#fd7e14',    // warming - orange
};

const STATE_NAMES: Record<number, string> = {
  [-1]: 'Error',
  0: 'Off',
  1: 'On',
  2: 'Cooling',
  3: 'Warming',
};

type TimeRange = '1h' | '4h' | '12h' | '24h' | 'today';

export const StateTimeline = memo(function StateTimeline({
  editMode,
  filterDeviceId,
  exhibitionId,
}: StateTimelineProps) {
  const [stateChanges, setStateChanges] = useState<StateChange[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  const [timeRange, setTimeRange] = useState<TimeRange>('4h');
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  const getTimeRangeDates = useCallback((range: TimeRange): { from: Date; to: Date } => {
    const now = new Date();
    const to = now;
    let from: Date;

    switch (range) {
      case '1h':
        from = new Date(now.getTime() - 60 * 60 * 1000);
        break;
      case '4h':
        from = new Date(now.getTime() - 4 * 60 * 60 * 1000);
        break;
      case '12h':
        from = new Date(now.getTime() - 12 * 60 * 60 * 1000);
        break;
      case '24h':
        from = new Date(now.getTime() - 24 * 60 * 60 * 1000);
        break;
      case 'today':
        from = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0);
        break;
      default:
        from = new Date(now.getTime() - 4 * 60 * 60 * 1000);
    }

    return { from, to };
  }, []);

  const fetchStateChanges = useCallback(async () => {
    try {
      setError(null);
      const { from, to } = getTimeRangeDates(timeRange);

      const params = new URLSearchParams({
        from_date: from.toISOString(),
        to_date: to.toISOString(),
        limit: '1000',
      });

      if (filterDeviceId) {
        params.set('device_id', filterDeviceId);
      }
      if (exhibitionId) {
        params.set('exhibition_id', exhibitionId);
      }

      const response = await fetch(`${API_BASE}/api/state/changes?${params}`);
      if (!response.ok) throw new Error('Failed to fetch state changes');
      const data = await response.json();
      setStateChanges(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [timeRange, filterDeviceId, exhibitionId, getTimeRangeDates]);

  useEffect(() => {
    if (editMode && !collapsed) {
      fetchStateChanges();
      const interval = setInterval(fetchStateChanges, 10000); // Refresh every 10s
      return () => clearInterval(interval);
    }
  }, [editMode, collapsed, fetchStateChanges]);

  // Process state changes into time segments for the Gantt chart
  const processSegments = useCallback((): { segments: TimeSegment[]; devices: string[] } => {
    if (stateChanges.length === 0) return { segments: [], devices: [] };

    const { from, to } = getTimeRangeDates(timeRange);

    // Group changes by device
    const deviceChanges = new Map<string, StateChange[]>();
    const deviceInfo = new Map<string, { name: string; type: string; host: string }>();

    for (const change of stateChanges) {
      if (!deviceChanges.has(change.device_id)) {
        deviceChanges.set(change.device_id, []);
        deviceInfo.set(change.device_id, {
          name: change.device_name,
          type: change.device_type,
          host: change.device_host,
        });
      }
      deviceChanges.get(change.device_id)!.push(change);
    }

    const segments: TimeSegment[] = [];
    const devices: string[] = [];

    // Sort devices by name
    const sortedDeviceIds = Array.from(deviceInfo.entries())
      .sort((a, b) => a[1].name.localeCompare(b[1].name))
      .map(([id]) => id);

    for (const deviceId of sortedDeviceIds) {
      const info = deviceInfo.get(deviceId)!;
      devices.push(info.name);

      const changes = deviceChanges.get(deviceId)!;
      // Sort changes by timestamp ascending
      changes.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());

      // Create segments from state changes
      for (let i = 0; i < changes.length; i++) {
        const change = changes[i];
        const changeTime = new Date(change.timestamp);

        // Add segment for previous_state from range start to first change
        if (i === 0 && change.previous_state !== undefined) {
          // First segment: from range start to first change
          segments.push({
            device_id: deviceId,
            device_name: info.name,
            device_type: info.type,
            device_host: info.host,
            state: change.previous_state,
            start: from,
            end: changeTime,
          });
        }

        // Add segment for new_state from this change to next change or range end
        const segmentEnd = i < changes.length - 1
          ? new Date(changes[i + 1].timestamp)
          : to;

        segments.push({
          device_id: deviceId,
          device_name: info.name,
          device_type: info.type,
          device_host: info.host,
          state: change.new_state,
          start: changeTime,
          end: segmentEnd,
        });
      }

      // If no changes for a device, we won't see it (it will appear if it has state changes)
    }

    return { segments, devices };
  }, [stateChanges, timeRange, getTimeRangeDates]);

  // Render the D3 chart
  useEffect(() => {
    if (!svgRef.current || !containerRef.current || collapsed) return;

    const { segments, devices } = processSegments();
    if (devices.length === 0) return;

    const containerWidth = containerRef.current.clientWidth;
    const margin = { top: 30, right: 20, bottom: 30, left: 150 };
    const rowHeight = 28;
    const height = Math.max(200, devices.length * rowHeight + margin.top + margin.bottom);
    const width = containerWidth;
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    // Clear previous content
    d3.select(svgRef.current).selectAll('*').remove();

    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', height);

    const g = svg.append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    // Time scale
    const { from, to } = getTimeRangeDates(timeRange);
    const xScale = d3.scaleTime()
      .domain([from, to])
      .range([0, innerWidth]);

    // Device scale
    const yScale = d3.scaleBand()
      .domain(devices)
      .range([0, innerHeight])
      .padding(0.2);

    // X axis (time)
    const xAxis = d3.axisTop(xScale)
      .ticks(8)
      .tickFormat((d) => d3.timeFormat('%H:%M')(d as Date));

    g.append('g')
      .attr('class', 'x-axis')
      .call(xAxis)
      .selectAll('text')
      .attr('fill', '#495057')
      .style('font-size', '11px');

    g.selectAll('.x-axis path, .x-axis line')
      .attr('stroke', '#dee2e6');

    // Y axis (device names)
    const yAxis = d3.axisLeft(yScale);

    g.append('g')
      .attr('class', 'y-axis')
      .call(yAxis)
      .selectAll('text')
      .attr('fill', '#212529')
      .style('font-size', '11px')
      .each(function() {
        const text = d3.select(this);
        const textContent = text.text();
        if (textContent.length > 20) {
          text.text(textContent.substring(0, 18) + '...');
        }
      });

    g.selectAll('.y-axis path, .y-axis line')
      .attr('stroke', '#dee2e6');

    // Grid lines
    g.append('g')
      .attr('class', 'grid')
      .selectAll('line')
      .data(devices)
      .join('line')
      .attr('x1', 0)
      .attr('x2', innerWidth)
      .attr('y1', d => (yScale(d) || 0) + yScale.bandwidth() / 2)
      .attr('y2', d => (yScale(d) || 0) + yScale.bandwidth() / 2)
      .attr('stroke', '#e9ecef')
      .attr('stroke-dasharray', '2,2');

    // Draw segments
    const tooltip = d3.select(tooltipRef.current);

    g.selectAll('.segment')
      .data(segments)
      .join('rect')
      .attr('class', 'segment')
      .attr('x', d => xScale(d.start))
      .attr('y', d => yScale(d.device_name) || 0)
      .attr('width', d => Math.max(2, xScale(d.end) - xScale(d.start)))
      .attr('height', yScale.bandwidth())
      .attr('fill', d => STATE_COLORS[d.state] || '#666')
      .attr('rx', 2)
      .attr('ry', 2)
      .style('cursor', 'pointer')
      .on('mouseover', function(event, d) {
        d3.select(this).attr('opacity', 0.8);
        tooltip
          .style('display', 'block')
          .style('left', (event.pageX + 10) + 'px')
          .style('top', (event.pageY - 10) + 'px')
          .html(`
            <strong>${d.device_name}</strong><br/>
            <span style="color: #adb5bd; font-size: 0.9em">${d.device_host}</span><br/>
            State: ${STATE_NAMES[d.state] || 'Unknown'}<br/>
            From: ${d3.timeFormat('%H:%M:%S')(d.start)}<br/>
            To: ${d3.timeFormat('%H:%M:%S')(d.end)}<br/>
            Duration: ${formatDuration(d.end.getTime() - d.start.getTime())}
          `);
      })
      .on('mouseout', function() {
        d3.select(this).attr('opacity', 1);
        tooltip.style('display', 'none');
      });

    // Current time indicator
    const now = new Date();
    if (now >= from && now <= to) {
      g.append('line')
        .attr('class', 'now-line')
        .attr('x1', xScale(now))
        .attr('x2', xScale(now))
        .attr('y1', 0)
        .attr('y2', innerHeight)
        .attr('stroke', '#fff')
        .attr('stroke-width', 2)
        .attr('stroke-dasharray', '4,2');

      g.append('text')
        .attr('x', xScale(now))
        .attr('y', -10)
        .attr('text-anchor', 'middle')
        .attr('fill', '#fff')
        .style('font-size', '10px')
        .text('now');
    }

  }, [processSegments, collapsed, timeRange, getTimeRangeDates]);

  // Handle window resize
  useEffect(() => {
    const handleResize = () => {
      if (svgRef.current && containerRef.current && !collapsed) {
        // Re-render on resize
        const event = new Event('resize');
        window.dispatchEvent(event);
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [collapsed]);

  if (!editMode) return null;

  return (
    <div className="debug-section state-timeline">
      <div className="debug-header" onClick={() => setCollapsed(!collapsed)}>
        <div className="debug-header-left">
          <i className={`bi bi-chevron-${collapsed ? 'right' : 'down'} me-2`}></i>
          <i className="bi bi-bar-chart-steps me-2"></i>
          <span>State Timeline</span>
          <span className="text-muted ms-2 small">
            ({stateChanges.length} changes)
          </span>
        </div>
        <div className="debug-header-actions" onClick={e => e.stopPropagation()}>
          <select
            className="form-select form-select-sm me-2"
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value as TimeRange)}
            style={{ width: 'auto' }}
          >
            <option value="1h">Last 1 hour</option>
            <option value="4h">Last 4 hours</option>
            <option value="12h">Last 12 hours</option>
            <option value="24h">Last 24 hours</option>
            <option value="today">Today</option>
          </select>
          <button
            className="btn btn-sm btn-outline-secondary"
            onClick={fetchStateChanges}
            title="Refresh"
          >
            <i className="bi bi-arrow-clockwise"></i>
          </button>
        </div>
      </div>

      {!collapsed && (
        <div className="debug-content">
          {loading && stateChanges.length === 0 && (
            <div className="text-muted p-3">Loading timeline...</div>
          )}

          {error && (
            <div className="text-danger p-3">Error: {error}</div>
          )}

          {!loading && !error && stateChanges.length === 0 && (
            <div className="text-muted p-3">
              No state changes in the selected time range.
            </div>
          )}

          {stateChanges.length > 0 && (
            <>
              {/* Legend */}
              <div className="timeline-legend">
                {Object.entries(STATE_NAMES).map(([state, name]) => (
                  <div key={state} className="legend-item">
                    <span
                      className="legend-color"
                      style={{ backgroundColor: STATE_COLORS[parseInt(state)] }}
                    ></span>
                    <span className="legend-label">{name}</span>
                  </div>
                ))}
              </div>

              {/* Chart container */}
              <div ref={containerRef} className="timeline-chart-container">
                <svg ref={svgRef}></svg>
              </div>
            </>
          )}

          {/* Tooltip */}
          <div
            ref={tooltipRef}
            className="timeline-tooltip"
            style={{ display: 'none' }}
          ></div>
        </div>
      )}
    </div>
  );
});
