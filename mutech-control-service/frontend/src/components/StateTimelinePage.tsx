import { useState, useEffect, useRef, useCallback } from 'react';
import * as d3 from 'd3';

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
  device_port: number | null;
  state: number;
  start: Date;
  end: Date;
  rowIndex: number;
}

interface RowInfo {
  type: 'exhibition' | 'artwork' | 'device';
  label: string;
  deviceId?: string;
  index: number;
}

interface DeviceOption {
  id: string;
  name: string;
  type: string;
  host: string;
  port: number | null;
  artworkName: string;
  exhibitionName: string;
  state: number;
}

interface StateTimelinePageProps {
  onClose: () => void;
  devices: DeviceOption[];
}

const STATE_COLORS: Record<number, string> = {
  [-1]: '#e74c3c', // error - red
  0: '#6c757d',    // off - gray
  1: '#27ae60',    // on - green
  2: '#f39c12',    // cooling - yellow
  3: '#e67e22',    // warming - orange
};

const STATE_NAMES: Record<number, string> = {
  [-1]: 'Error',
  0: 'Off',
  1: 'On',
  2: 'Cooling',
  3: 'Warming',
};

type TimeRange = '1h' | '4h' | '12h' | '24h' | 'today' | '7d' | '30d' | 'custom';

export function StateTimelinePage({ onClose, devices }: StateTimelinePageProps) {
  const [stateChanges, setStateChanges] = useState<StateChange[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [timeRange, setTimeRange] = useState<TimeRange>('4h');
  const [filterExhibition, setFilterExhibition] = useState<string | null>(null);
  const [customFrom, setCustomFrom] = useState<string>('');
  const [customTo, setCustomTo] = useState<string>('');
  const [zoomLevel, setZoomLevel] = useState<string>('100%');
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const zoomRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null);
  const currentTransformRef = useRef<d3.ZoomTransform>(d3.zoomIdentity);

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
      case '7d':
        from = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        break;
      case '30d':
        from = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
        break;
      case 'custom':
        from = customFrom ? new Date(customFrom) : new Date(now.getTime() - 4 * 60 * 60 * 1000);
        return {
          from,
          to: customTo ? new Date(customTo) : now,
        };
      default:
        from = new Date(now.getTime() - 4 * 60 * 60 * 1000);
    }

    return { from, to };
  }, [customFrom, customTo]);

  const fetchStateChanges = useCallback(async () => {
    try {
      setError(null);
      const { from, to } = getTimeRangeDates(timeRange);

      const params = new URLSearchParams({
        from_date: from.toISOString(),
        to_date: to.toISOString(),
        limit: '5000',
      });

      const response = await fetch(`${API_BASE}/api/state/changes?${params}`);
      if (!response.ok) throw new Error('Failed to fetch state changes');
      const data = await response.json();
      setStateChanges(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [timeRange, getTimeRangeDates]);

  useEffect(() => {
    fetchStateChanges();
    const interval = setInterval(fetchStateChanges, 15000);
    return () => clearInterval(interval);
  }, [fetchStateChanges]);

  // Get unique exhibitions from devices
  const exhibitions = [...new Set(devices.map(d => d.exhibitionName))].sort();

  // Filter devices by exhibition
  const filteredDeviceIds = filterExhibition
    ? new Set(devices.filter(d => d.exhibitionName === filterExhibition).map(d => d.id))
    : null;

  // Process state changes into grouped segments
  const processSegments = useCallback((): { segments: TimeSegment[]; rows: RowInfo[]; totalRows: number } => {
    const { from, to } = getTimeRangeDates(timeRange);

    // Filter devices by exhibition if needed
    const filteredDevices = filteredDeviceIds
      ? devices.filter(d => filteredDeviceIds.has(d.id))
      : devices;

    if (filteredDevices.length === 0) return { segments: [], rows: [], totalRows: 0 };

    // Group state changes by device
    const deviceChanges = new Map<string, StateChange[]>();
    for (const change of stateChanges) {
      if (!deviceChanges.has(change.device_id)) {
        deviceChanges.set(change.device_id, []);
      }
      deviceChanges.get(change.device_id)!.push(change);
    }

    // Sort all filtered devices (not just those with changes)
    const sortedDevices = [...filteredDevices].sort((a, b) => {
      const exCmp = a.exhibitionName.localeCompare(b.exhibitionName);
      if (exCmp !== 0) return exCmp;
      const awCmp = a.artworkName.localeCompare(b.artworkName);
      if (awCmp !== 0) return awCmp;
      return a.name.localeCompare(b.name);
    });

    // Build rows with exhibition and artwork headers
    const rows: RowInfo[] = [];
    const segments: TimeSegment[] = [];
    let currentExhibition = '';
    let currentArtwork = '';
    let rowIndex = 0;

    for (const device of sortedDevices) {
      // Add exhibition header if new exhibition
      if (device.exhibitionName !== currentExhibition) {
        currentExhibition = device.exhibitionName;
        currentArtwork = ''; // Reset artwork
        rows.push({
          type: 'exhibition',
          label: currentExhibition,
          index: rowIndex,
        });
        rowIndex++;
      }

      // Add artwork header if new artwork
      if (device.artworkName !== currentArtwork) {
        currentArtwork = device.artworkName;
        rows.push({
          type: 'artwork',
          label: currentArtwork,
          index: rowIndex,
        });
        rowIndex++;
      }

      // Add device row
      rows.push({
        type: 'device',
        label: device.name,
        deviceId: device.id,
        index: rowIndex,
      });

      // Process segments for this device
      const changes = deviceChanges.get(device.id);

      if (changes && changes.length > 0) {
        // Device has state changes - process them
        changes.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());

        for (let i = 0; i < changes.length; i++) {
          const change = changes[i];
          const changeTime = new Date(change.timestamp);

          // First segment: previous state from range start to first change
          if (i === 0 && change.previous_state !== undefined) {
            segments.push({
              device_id: device.id,
              device_name: device.name,
              device_type: device.type,
              device_host: device.host,
              device_port: device.port,
              state: change.previous_state,
              start: from,
              end: changeTime,
              rowIndex: rowIndex,
            });
          }

          // Segment for new state
          const isLastChange = i === changes.length - 1;
          const segmentEnd = isLastChange ? to : new Date(changes[i + 1].timestamp);

          // Self-healing: For the last segment, if the current device state differs
          // from the last logged state, use the current state and add a transition.
          // This handles cases where polling detected a change but hasn't logged it yet.
          if (isLastChange && device.state !== change.new_state && device.state >= 0) {
            // Add segment for the logged state up to a recent point
            // Assume the state changed recently (use midpoint as approximation)
            const now = new Date();
            const transitionTime = new Date(Math.max(
              changeTime.getTime() + 60000, // At least 1 minute after logged change
              now.getTime() - 60000 // Or 1 minute ago, whichever is later
            ));

            // Logged state segment (ends at transition point)
            segments.push({
              device_id: device.id,
              device_name: device.name,
              device_type: device.type,
              device_host: device.host,
              device_port: device.port,
              state: change.new_state,
              start: changeTime,
              end: transitionTime < to ? transitionTime : changeTime,
              rowIndex: rowIndex,
            });

            // Current state segment (from transition to now) - self-healed
            if (transitionTime < to) {
              segments.push({
                device_id: device.id,
                device_name: device.name,
                device_type: device.type,
                device_host: device.host,
                device_port: device.port,
                state: device.state,
                start: transitionTime,
                end: to,
                rowIndex: rowIndex,
              });
            }
          } else {
            // Normal case: use the logged state
            segments.push({
              device_id: device.id,
              device_name: device.name,
              device_type: device.type,
              device_host: device.host,
              device_port: device.port,
              state: change.new_state,
              start: changeTime,
              end: segmentEnd,
              rowIndex: rowIndex,
            });
          }
        }
      } else {
        // Device has no state changes - show current state for entire range
        segments.push({
          device_id: device.id,
          device_name: device.name,
          device_type: device.type,
          device_host: device.host,
          device_port: device.port,
          state: device.state,
          start: from,
          end: to,
          rowIndex: rowIndex,
        });
      }

      rowIndex++;
    }

    return { segments, rows, totalRows: rowIndex };
  }, [stateChanges, timeRange, getTimeRangeDates, filteredDeviceIds, devices]);

  // Render the D3 chart with zoom
  useEffect(() => {
    if (!svgRef.current || !containerRef.current) return;

    const { segments, rows } = processSegments();
    if (rows.length === 0) {
      d3.select(svgRef.current).selectAll('*').remove();
      return;
    }

    const containerWidth = containerRef.current.clientWidth - 20; // Account for scrollbar
    const margin = { top: 40, right: 20, bottom: 10, left: 180 };
    const rowHeight = 26;
    const exhibitionRowHeight = 32;
    const artworkRowHeight = 28;

    // Calculate actual height based on row types
    let totalHeight = 0;
    for (const row of rows) {
      if (row.type === 'exhibition') totalHeight += exhibitionRowHeight;
      else if (row.type === 'artwork') totalHeight += artworkRowHeight;
      else totalHeight += rowHeight;
    }

    const height = Math.max(300, totalHeight + margin.top + margin.bottom);
    const width = containerWidth; // Fit to container width, no minimum
    const innerWidth = width - margin.left - margin.right;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    svg.attr('width', width).attr('height', height);

    // Create defs for clip path
    const defs = svg.append('defs');
    defs.append('clipPath')
      .attr('id', 'chart-clip')
      .append('rect')
      .attr('x', 0)
      .attr('y', -margin.top)
      .attr('width', innerWidth)
      .attr('height', height);

    const g = svg.append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    const { from, to } = getTimeRangeDates(timeRange);
    const xScale = d3.scaleTime()
      .domain([from, to])
      .range([0, innerWidth]);

    // Calculate Y positions for each row
    const rowPositions = new Map<number, { y: number; height: number }>();
    let currentY = 0;
    for (const row of rows) {
      const h = row.type === 'exhibition' ? exhibitionRowHeight
        : row.type === 'artwork' ? artworkRowHeight
        : rowHeight;
      rowPositions.set(row.index, { y: currentY, height: h });
      currentY += h;
    }

    // Create a group for zoomable content
    const chartGroup = g.append('g')
      .attr('class', 'chart-content')
      .attr('clip-path', 'url(#chart-clip)');

    // Function to render chart content with current scale
    const renderChart = (xScaleZoomed: d3.ScaleTime<number, number>) => {
      chartGroup.selectAll('*').remove();

      // Vertical grid lines
      const xTicks = xScaleZoomed.ticks(10);
      chartGroup.append('g')
        .attr('class', 'grid-vertical')
        .selectAll('line')
        .data(xTicks)
        .join('line')
        .attr('x1', d => xScaleZoomed(d))
        .attr('x2', d => xScaleZoomed(d))
        .attr('y1', 0)
        .attr('y2', currentY)
        .attr('stroke', '#dee2e6')
        .attr('stroke-dasharray', '2,4');

      // Draw row backgrounds for chart area
      for (const row of rows) {
        const pos = rowPositions.get(row.index)!;

        if (row.type === 'exhibition') {
          chartGroup.append('rect')
            .attr('x', 0)
            .attr('y', pos.y)
            .attr('width', innerWidth)
            .attr('height', pos.height)
            .attr('fill', '#e3f2fd');
        } else if (row.type === 'artwork') {
          chartGroup.append('rect')
            .attr('x', 0)
            .attr('y', pos.y)
            .attr('width', innerWidth)
            .attr('height', pos.height)
            .attr('fill', '#f5f5f5');
        } else {
          // Horizontal grid line for device rows
          chartGroup.append('line')
            .attr('x1', 0)
            .attr('x2', innerWidth)
            .attr('y1', pos.y + pos.height / 2)
            .attr('y2', pos.y + pos.height / 2)
            .attr('stroke', '#e9ecef')
            .attr('stroke-dasharray', '2,2');
        }
      }

      // Draw segments
      const tooltip = d3.select(tooltipRef.current);

      chartGroup.selectAll('.segment')
        .data(segments)
        .join('rect')
        .attr('class', 'segment')
        .attr('x', d => xScaleZoomed(d.start))
        .attr('y', d => {
          const pos = rowPositions.get(d.rowIndex);
          return pos ? pos.y + 3 : 0;
        })
        .attr('width', d => Math.max(2, xScaleZoomed(d.end) - xScaleZoomed(d.start)))
        .attr('height', d => {
          const pos = rowPositions.get(d.rowIndex);
          return pos ? pos.height - 6 : rowHeight - 6;
        })
        .attr('fill', d => STATE_COLORS[d.state] || '#666')
        .attr('rx', 3)
        .attr('ry', 3)
        .style('cursor', 'pointer')
        .on('mouseover', function(event, d) {
          d3.select(this).attr('opacity', 0.8).attr('stroke', '#fff').attr('stroke-width', 1);
          tooltip
            .style('display', 'block')
            .style('left', (event.pageX + 15) + 'px')
            .style('top', (event.pageY - 10) + 'px')
            .html(`
              <strong>${d.device_name || '(unnamed)'}</strong><br/>
              <span class="tooltip-host">${d.device_host}${(d.device_type.toLowerCase() === 'netio' || d.device_type.toLowerCase() === 'anel') && d.device_port !== null ? ` :${d.device_port + 1}` : ''}</span><br/>
              <span class="tooltip-type">${d.device_type.toUpperCase()}</span><br/>
              State: <span style="color:${STATE_COLORS[d.state]}">${STATE_NAMES[d.state] || 'Unknown'}</span><br/>
              From: ${d3.timeFormat('%Y-%m-%d %H:%M:%S')(d.start)}<br/>
              To: ${d3.timeFormat('%Y-%m-%d %H:%M:%S')(d.end)}<br/>
              Duration: ${formatDuration(d.end.getTime() - d.start.getTime())}
            `);
        })
        .on('mouseout', function() {
          d3.select(this).attr('opacity', 1).attr('stroke', 'none');
          tooltip.style('display', 'none');
        });

      // Current time indicator
      const now = new Date();
      if (now >= from && now <= to) {
        chartGroup.append('line')
          .attr('class', 'now-line')
          .attr('x1', xScaleZoomed(now))
          .attr('x2', xScaleZoomed(now))
          .attr('y1', -10)
          .attr('y2', currentY + 10)
          .attr('stroke', '#42a5f5')
          .attr('stroke-width', 2)
          .attr('stroke-dasharray', '6,3');

        chartGroup.append('text')
          .attr('x', xScaleZoomed(now))
          .attr('y', -20)
          .attr('text-anchor', 'middle')
          .attr('fill', '#42a5f5')
          .style('font-size', '11px')
          .style('font-weight', '600')
          .text('NOW');
      }
    };

    // Draw row labels (static, outside zoom)
    const labelsGroup = g.append('g').attr('class', 'labels');

    for (const row of rows) {
      const pos = rowPositions.get(row.index)!;

      if (row.type === 'exhibition') {
        // Exhibition header background
        labelsGroup.append('rect')
          .attr('x', -margin.left)
          .attr('y', pos.y)
          .attr('width', margin.left)
          .attr('height', pos.height)
          .attr('fill', '#e3f2fd');

        // Exhibition label
        labelsGroup.append('text')
          .attr('x', -margin.left + 10)
          .attr('y', pos.y + pos.height / 2)
          .attr('dy', '0.35em')
          .attr('fill', '#1565c0')
          .style('font-size', '13px')
          .style('font-weight', '600')
          .text(row.label.length > 28 ? row.label.substring(0, 26) + '...' : row.label);

      } else if (row.type === 'artwork') {
        // Artwork header background
        labelsGroup.append('rect')
          .attr('x', -margin.left)
          .attr('y', pos.y)
          .attr('width', margin.left)
          .attr('height', pos.height)
          .attr('fill', '#f5f5f5');

        // Artwork label (indented)
        labelsGroup.append('text')
          .attr('x', -margin.left + 20)
          .attr('y', pos.y + pos.height / 2)
          .attr('dy', '0.35em')
          .attr('fill', '#00796b')
          .style('font-size', '12px')
          .style('font-weight', '500')
          .text(row.label.length > 26 ? row.label.substring(0, 24) + '...' : row.label);

      } else {
        // Device row - subtle background
        labelsGroup.append('rect')
          .attr('x', -margin.left)
          .attr('y', pos.y)
          .attr('width', margin.left)
          .attr('height', pos.height)
          .attr('fill', '#ffffff');

        // Device label (more indented)
        labelsGroup.append('text')
          .attr('x', -margin.left + 30)
          .attr('y', pos.y + pos.height / 2)
          .attr('dy', '0.35em')
          .attr('fill', '#495057')
          .style('font-size', '11px')
          .text(row.label.length > 24 ? row.label.substring(0, 22) + '...' : row.label);
      }
    }

    // X axis (top) - will be updated on zoom
    const xAxisGroup = g.append('g').attr('class', 'x-axis');
    const xAxisBottomGroup = g.append('g')
      .attr('class', 'x-axis-bottom')
      .attr('transform', `translate(0,${currentY})`);

    const updateAxes = (xScaleZoomed: d3.ScaleTime<number, number>) => {
      // Determine tick format based on visible range
      const domain = xScaleZoomed.domain();
      const rangeMs = domain[1].getTime() - domain[0].getTime();
      const rangeHours = rangeMs / (1000 * 60 * 60);

      let tickFormat: (d: Date) => string;
      if (rangeHours > 48) {
        tickFormat = d3.timeFormat('%m/%d %H:%M');
      } else if (rangeHours > 12) {
        tickFormat = d3.timeFormat('%H:%M');
      } else {
        tickFormat = d3.timeFormat('%H:%M:%S');
      }

      const xAxis = d3.axisTop(xScaleZoomed)
        .ticks(10)
        .tickFormat((d) => tickFormat(d as Date));

      xAxisGroup.call(xAxis)
        .selectAll('text')
        .attr('fill', '#495057')
        .style('font-size', '11px');

      xAxisGroup.selectAll('path, line').attr('stroke', '#dee2e6');

      const xAxisBottom = d3.axisBottom(xScaleZoomed)
        .ticks(10)
        .tickFormat((d) => tickFormat(d as Date));

      xAxisBottomGroup.call(xAxisBottom)
        .selectAll('text')
        .attr('fill', '#495057')
        .style('font-size', '11px');

      xAxisBottomGroup.selectAll('path, line').attr('stroke', '#dee2e6');
    };

    // Initial render
    renderChart(xScale);
    updateAxes(xScale);

    // Setup zoom behavior - require Ctrl/Cmd for scroll zoom to allow normal page scrolling
    // scaleExtent: 0.05 = can zoom out to 20x time range, 50 = zoom in 50x
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.05, 50])
      .extent([[0, 0], [innerWidth, height]])
      .filter((event) => {
        // Allow programmatic zoom and touch events
        if (!event) return true;
        // For wheel events, require Ctrl/Cmd key to zoom (allow normal scroll otherwise)
        if (event.type === 'wheel') {
          return event.ctrlKey || event.metaKey;
        }
        // Allow other events (drag for pan, double-click, touch pinch)
        return !event.button;
      })
      .on('zoom', (event) => {
        currentTransformRef.current = event.transform;
        const newXScale = event.transform.rescaleX(xScale);
        renderChart(newXScale);
        updateAxes(newXScale);
        setZoomLevel(`${Math.round(event.transform.k * 100)}%`);
      });

    zoomRef.current = zoom;
    svg.call(zoom);

    // Apply stored transform
    if (currentTransformRef.current !== d3.zoomIdentity) {
      svg.call(zoom.transform, currentTransformRef.current);
    }

  }, [processSegments, timeRange, getTimeRangeDates]);

  // Zoom control functions
  const handleZoomIn = () => {
    if (svgRef.current && zoomRef.current) {
      const svg = d3.select(svgRef.current);
      svg.transition().duration(300).call(zoomRef.current.scaleBy, 1.5);
    }
  };

  const handleZoomOut = () => {
    if (svgRef.current && zoomRef.current) {
      const svg = d3.select(svgRef.current);
      svg.transition().duration(300).call(zoomRef.current.scaleBy, 0.67);
    }
  };

  const handleZoomReset = () => {
    if (svgRef.current && zoomRef.current) {
      const svg = d3.select(svgRef.current);
      svg.transition().duration(300).call(zoomRef.current.transform, d3.zoomIdentity);
      currentTransformRef.current = d3.zoomIdentity;
    }
  };

  // Handle window resize
  useEffect(() => {
    const handleResize = () => {
      currentTransformRef.current = d3.zoomIdentity;
      fetchStateChanges();
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [fetchStateChanges]);

  const { rows } = processSegments();
  const deviceCount = rows.filter(r => r.type === 'device').length;

  // Initialize custom date inputs when switching to custom
  useEffect(() => {
    if (timeRange === 'custom' && !customFrom) {
      const now = new Date();
      const from = new Date(now.getTime() - 24 * 60 * 60 * 1000);
      setCustomFrom(from.toISOString().slice(0, 16));
      setCustomTo(now.toISOString().slice(0, 16));
    }
  }, [timeRange, customFrom]);

  return (
    <div className="timeline-page">
      {/* Header */}
      <div className="sub-page-header">
        <div className="sub-page-header-left">
          <button className="btn btn-sm btn-outline-secondary" onClick={onClose}>
            <i className="bi bi-arrow-left me-1"></i>
            Back
          </button>
          <h2>
            <i className="bi bi-bar-chart-steps me-2"></i>
            Timeline
          </h2>
          <span className="text-muted">
            {deviceCount} devices
          </span>
        </div>
        <div className="sub-page-header-right">
          {/* Exhibition filter */}
          <select
            className="form-select form-select-sm"
            value={filterExhibition || ''}
            onChange={(e) => setFilterExhibition(e.target.value || null)}
            style={{ width: 'auto', maxWidth: '180px' }}
          >
            <option value="">All exhibitions</option>
            {exhibitions.map(ex => (
              <option key={ex} value={ex}>{ex}</option>
            ))}
          </select>

          {/* Time range selector */}
          <select
            className="form-select form-select-sm"
            value={timeRange}
            onChange={(e) => {
              setTimeRange(e.target.value as TimeRange);
              currentTransformRef.current = d3.zoomIdentity;
            }}
            style={{ width: 'auto' }}
          >
            <option value="1h">1 hour</option>
            <option value="4h">4 hours</option>
            <option value="12h">12 hours</option>
            <option value="24h">24 hours</option>
            <option value="today">Today</option>
            <option value="7d">7 days</option>
            <option value="30d">30 days</option>
            <option value="custom">Custom</option>
          </select>

          {/* Custom date inputs inline */}
          {timeRange === 'custom' && (
            <>
              <input
                type="datetime-local"
                className="form-control form-control-sm"
                value={customFrom}
                onChange={(e) => setCustomFrom(e.target.value)}
                style={{ width: 'auto' }}
              />
              <span className="text-muted">to</span>
              <input
                type="datetime-local"
                className="form-control form-control-sm"
                value={customTo}
                onChange={(e) => setCustomTo(e.target.value)}
                style={{ width: 'auto' }}
              />
            </>
          )}

          <button
            className="btn btn-sm btn-outline-secondary"
            onClick={() => {
              currentTransformRef.current = d3.zoomIdentity;
              fetchStateChanges();
            }}
            title="Refresh data"
          >
            <i className="bi bi-arrow-clockwise me-1"></i>
            Refresh
          </button>
        </div>
      </div>

      {/* Action row */}
      <div className="sub-page-actions">
        <span className="zoom-level">{zoomLevel}</span>
        <button
          className="btn btn-sm btn-outline-secondary"
          onClick={handleZoomOut}
          title="Zoom out"
        >
          <i className="bi bi-zoom-out me-1"></i>
          Out
        </button>
        <button
          className="btn btn-sm btn-outline-secondary"
          onClick={handleZoomReset}
          title="Reset zoom"
        >
          <i className="bi bi-arrows-angle-contract me-1"></i>
          Reset
        </button>
        <button
          className="btn btn-sm btn-outline-secondary"
          onClick={handleZoomIn}
          title="Zoom in"
        >
          <i className="bi bi-zoom-in me-1"></i>
          In
        </button>
      </div>

      {/* Chart Container */}
      <div className="timeline-page-content" ref={containerRef}>
        {loading && stateChanges.length === 0 && (
          <div className="timeline-loading">
            <div className="spinner-border text-light" role="status">
              <span className="visually-hidden">Loading...</span>
            </div>
          </div>
        )}

        {error && (
          <div className="timeline-error">
            <i className="bi bi-exclamation-triangle me-2"></i>
            Error: {error}
          </div>
        )}

        {!loading && !error && deviceCount === 0 && (
          <div className="timeline-empty">
            <i className="bi bi-inbox me-2"></i>
            No devices to display.
          </div>
        )}

        {deviceCount > 0 && (
          <div className="timeline-chart-scroll">
            <svg ref={svgRef}></svg>
          </div>
        )}
      </div>

      {/* Legend and zoom hint */}
      <div className="timeline-legend-hint">
        <div className="legend-inline">
          {Object.entries(STATE_NAMES).map(([state, name]) => (
            <span key={state} className="legend-item-inline">
              <span
                className="legend-dot"
                style={{ backgroundColor: STATE_COLORS[parseInt(state)] }}
              ></span>
              {name}
            </span>
          ))}
        </div>
        <span className="zoom-hint-text">
          <i className="bi bi-mouse me-1"></i>
          Ctrl+Scroll to zoom, drag to pan
        </span>
      </div>

      {/* Tooltip */}
      <div
        ref={tooltipRef}
        className="timeline-tooltip"
        style={{ display: 'none' }}
      ></div>
    </div>
  );
}

function formatDuration(ms: number): string {
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (days > 0) {
    return `${days}d ${hours % 24}h`;
  } else if (hours > 0) {
    return `${hours}h ${minutes % 60}m`;
  } else if (minutes > 0) {
    return `${minutes}m ${seconds % 60}s`;
  } else {
    return `${seconds}s`;
  }
}
