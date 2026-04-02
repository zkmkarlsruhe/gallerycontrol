/**
 * D3.js Chart implementations for visitor display system
 * Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
 * SPDX-License-Identifier: MIT
 *
 * Supported chart types:
 * - pie: Simple pie chart
 * - donut: Donut chart with center text
 * - bar-horizontal: Horizontal progress bar
 * - bar-vertical: Vertical progress bar
 * - gauge: Arc/speedometer style gauge
 * - digits-only: No chart, just large digits
 */

(function() {
    'use strict';

    // Check if D3 is available
    if (typeof d3 === 'undefined') {
        console.warn('D3.js not loaded, charts will not render');
        return;
    }

    const Charts = {
        // Store SVG references for updates
        _svgs: new WeakMap(),
        _initialized: new WeakMap(),

        /**
         * Initialize a chart in a container
         */
        init(chartType, container) {
            if (this._initialized.get(container)) return;

            switch (chartType) {
                case 'pie':
                case 'donut':
                    this._initPieDonut(container, chartType === 'donut');
                    break;
                case 'bar-horizontal':
                    this._initBarHorizontal(container);
                    break;
                case 'bar-vertical':
                    this._initBarVertical(container);
                    break;
                case 'gauge':
                    this._initGauge(container);
                    break;
                case 'digits-only':
                    this._initDigits(container);
                    break;
                default:
                    console.warn('Unknown chart type:', chartType);
            }

            this._initialized.set(container, true);
        },

        /**
         * Update a chart with new data
         */
        update(chartType, container, status) {
            switch (chartType) {
                case 'pie':
                case 'donut':
                    this._updatePieDonut(container, status, chartType === 'donut');
                    break;
                case 'bar-horizontal':
                    this._updateBarHorizontal(container, status);
                    break;
                case 'bar-vertical':
                    this._updateBarVertical(container, status);
                    break;
                case 'gauge':
                    this._updateGauge(container, status);
                    break;
                case 'digits-only':
                    this._updateDigits(container, status);
                    break;
            }
        },

        /**
         * Initialize pie/donut chart
         */
        _initPieDonut(container, isDonut) {
            const width = container.clientWidth || 300;
            const height = container.clientHeight || 300;
            const radius = Math.min(width, height) / 2;
            const innerRadius = isDonut ? radius * 0.6 : 0;

            const svg = d3.select(container)
                .append('svg')
                .attr('viewBox', `0 0 ${width} ${height}`)
                .attr('preserveAspectRatio', 'xMidYMid meet')
                .append('g')
                .attr('transform', `translate(${width / 2}, ${height / 2})`);

            // Create arc generators
            const arc = d3.arc()
                .innerRadius(innerRadius)
                .outerRadius(radius - 10);

            // Store for updates
            this._svgs.set(container, { svg, arc, radius, innerRadius, width, height });

            // Add center text group for donut
            if (isDonut) {
                const centerGroup = svg.append('g').attr('class', 'center-text-group');
                centerGroup.append('text')
                    .attr('class', 'chart-center-text')
                    .attr('y', -10);
                centerGroup.append('text')
                    .attr('class', 'chart-center-label')
                    .attr('y', 30)
                    .text('remaining');
            }
        },

        /**
         * Update pie/donut chart
         */
        _updatePieDonut(container, status, isDonut) {
            const refs = this._svgs.get(container);
            if (!refs) return;

            const { svg, arc } = refs;
            const available = status.budget_remaining;
            const used = status.budget_max - status.budget_remaining;
            const isWarning = status.budget_percent < 20;

            // Pie data
            const pie = d3.pie()
                .sort(null)
                .value(d => d.value);

            const data = [
                { key: 'available', value: Math.max(0, available) },
                { key: 'used', value: Math.max(0, used) }
            ];

            // Bind data
            const arcs = svg.selectAll('.chart-arc')
                .data(pie(data), d => d.data.key);

            // Enter
            arcs.enter()
                .append('path')
                .attr('class', d => `chart-arc chart-arc-${d.data.key}`)
                .attr('d', arc)
                .style('fill', d => {
                    if (d.data.key === 'available') {
                        return isWarning
                            ? 'var(--warning-color)'
                            : 'var(--available-color)';
                    }
                    return 'var(--used-color)';
                });

            // Update
            arcs.transition()
                .duration(300)
                .attr('d', arc)
                .style('fill', d => {
                    if (d.data.key === 'available') {
                        return isWarning
                            ? 'var(--warning-color)'
                            : 'var(--available-color)';
                    }
                    return 'var(--used-color)';
                });

            // Update center text for donut
            if (isDonut) {
                const centerText = svg.select('.chart-center-text');
                centerText.text(window.DisplayStatus?.formatTime(available) || '0:00');
            }
        },

        /**
         * Initialize horizontal bar chart
         */
        _initBarHorizontal(container) {
            const width = container.clientWidth || 400;
            const height = container.clientHeight || 60;

            const svg = d3.select(container)
                .append('svg')
                .attr('viewBox', `0 0 ${width} ${height}`)
                .attr('preserveAspectRatio', 'xMidYMid meet');

            // Background
            svg.append('rect')
                .attr('class', 'bar-bg')
                .attr('x', 0)
                .attr('y', 0)
                .attr('width', width)
                .attr('height', height)
                .attr('rx', 8)
                .attr('fill', 'rgba(255, 255, 255, 0.1)');

            // Fill bar
            svg.append('rect')
                .attr('class', 'bar-fill-rect')
                .attr('x', 0)
                .attr('y', 0)
                .attr('width', 0)
                .attr('height', height)
                .attr('rx', 8)
                .attr('fill', 'var(--available-color)');

            // Label
            svg.append('text')
                .attr('class', 'bar-text')
                .attr('x', width / 2)
                .attr('y', height / 2)
                .attr('text-anchor', 'middle')
                .attr('dominant-baseline', 'central')
                .attr('fill', 'var(--text-color)')
                .attr('font-size', '1.5rem')
                .attr('font-weight', '600');

            this._svgs.set(container, { svg, width, height });
        },

        /**
         * Update horizontal bar chart
         */
        _updateBarHorizontal(container, status) {
            const refs = this._svgs.get(container);
            if (!refs) return;

            const { svg, width } = refs;
            const percent = status.budget_percent;
            const isWarning = percent < 20;

            svg.select('.bar-fill-rect')
                .transition()
                .duration(300)
                .attr('width', (percent / 100) * width)
                .attr('fill', isWarning ? 'var(--warning-color)' : 'var(--available-color)');

            svg.select('.bar-text')
                .text(window.DisplayStatus?.formatTime(status.budget_remaining) || '0:00');
        },

        /**
         * Initialize vertical bar chart
         */
        _initBarVertical(container) {
            const width = container.clientWidth || 80;
            const height = container.clientHeight || 300;

            const svg = d3.select(container)
                .append('svg')
                .attr('viewBox', `0 0 ${width} ${height}`)
                .attr('preserveAspectRatio', 'xMidYMid meet');

            // Background
            svg.append('rect')
                .attr('class', 'bar-bg')
                .attr('x', 0)
                .attr('y', 0)
                .attr('width', width)
                .attr('height', height)
                .attr('rx', 8)
                .attr('fill', 'rgba(255, 255, 255, 0.1)');

            // Fill bar (from bottom)
            svg.append('rect')
                .attr('class', 'bar-fill-rect')
                .attr('x', 0)
                .attr('y', height)
                .attr('width', width)
                .attr('height', 0)
                .attr('rx', 8)
                .attr('fill', 'var(--available-color)');

            this._svgs.set(container, { svg, width, height });
        },

        /**
         * Update vertical bar chart
         */
        _updateBarVertical(container, status) {
            const refs = this._svgs.get(container);
            if (!refs) return;

            const { svg, height } = refs;
            const percent = status.budget_percent;
            const isWarning = percent < 20;
            const fillHeight = (percent / 100) * height;

            svg.select('.bar-fill-rect')
                .transition()
                .duration(300)
                .attr('y', height - fillHeight)
                .attr('height', fillHeight)
                .attr('fill', isWarning ? 'var(--warning-color)' : 'var(--available-color)');
        },

        /**
         * Initialize gauge chart
         */
        _initGauge(container) {
            const width = container.clientWidth || 300;
            const height = container.clientHeight || 200;
            const radius = Math.min(width, height) - 20;

            const svg = d3.select(container)
                .append('svg')
                .attr('viewBox', `0 0 ${width} ${height}`)
                .attr('preserveAspectRatio', 'xMidYMid meet')
                .append('g')
                .attr('transform', `translate(${width / 2}, ${height - 20})`);

            // Arc generator for semicircle (180 degrees)
            const arcGen = d3.arc()
                .innerRadius(radius * 0.7)
                .outerRadius(radius)
                .startAngle(-Math.PI / 2);

            // Background arc
            svg.append('path')
                .attr('class', 'gauge-arc-bg')
                .attr('d', arcGen.endAngle(Math.PI / 2)());

            // Fill arc
            svg.append('path')
                .attr('class', 'gauge-arc-fill')
                .attr('d', arcGen.endAngle(-Math.PI / 2)());

            // Center value text
            svg.append('text')
                .attr('class', 'gauge-value')
                .attr('y', -radius * 0.3)
                .attr('text-anchor', 'middle')
                .attr('fill', 'var(--text-color)')
                .attr('font-size', '2.5rem')
                .attr('font-weight', '600');

            // Label
            svg.append('text')
                .attr('class', 'gauge-label')
                .attr('y', -radius * 0.1)
                .attr('text-anchor', 'middle')
                .attr('fill', 'var(--text-color)')
                .attr('font-size', '1rem')
                .attr('opacity', '0.7')
                .text('remaining');

            this._svgs.set(container, { svg, radius, arcGen });
        },

        /**
         * Update gauge chart
         */
        _updateGauge(container, status) {
            const refs = this._svgs.get(container);
            if (!refs) return;

            const { svg, arcGen } = refs;
            const percent = status.budget_percent;
            const isWarning = percent < 20;

            // Calculate end angle based on percent (semicircle)
            const endAngle = -Math.PI / 2 + (percent / 100) * Math.PI;

            svg.select('.gauge-arc-fill')
                .transition()
                .duration(300)
                .attr('d', arcGen.endAngle(endAngle)())
                .attr('fill', isWarning ? 'var(--warning-color)' : 'var(--available-color)');

            svg.select('.gauge-value')
                .text(window.DisplayStatus?.formatTime(status.budget_remaining) || '0:00');
        },

        /**
         * Initialize digits-only display
         */
        _initDigits(container) {
            // For digits-only, we just use HTML elements, no SVG needed
            container.innerHTML = `
                <div class="digits-container">
                    <div class="digits-main" data-running-indicator>0:00</div>
                    <div class="digits-label">remaining</div>
                </div>
            `;
        },

        /**
         * Update digits-only display
         */
        _updateDigits(container, status) {
            const digitsEl = container.querySelector('.digits-main');
            if (!digitsEl) return;

            digitsEl.textContent = window.DisplayStatus?.formatTime(status.budget_remaining) || '0:00';

            // Update color based on warning state
            const isWarning = status.budget_percent < 20;
            digitsEl.style.color = isWarning ? 'var(--warning-color)' : 'var(--available-color)';
        }
    };

    // Expose globally
    window.DisplayCharts = Charts;

})();
