/**
 * Shared JavaScript for visitor display system
 * Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
 * SPDX-License-Identifier: MIT
 */

(function() {
    'use strict';

    // Configuration
    const POLL_INTERVAL = 2000; // 2 seconds
    const RECONNECT_DELAY = 5000; // 5 seconds on error

    // Get configuration from body data attributes
    const body = document.body;
    const slug = body.dataset.slug;
    const chartType = body.dataset.chartType || 'donut';
    const statusUrl = `/steuerung/${slug}/status`;

    // State
    let lastStatus = null;
    let pollTimer = null;
    let errorCount = 0;

    /**
     * Format seconds as MM:SS or HH:MM:SS
     */
    function formatTime(seconds) {
        if (seconds < 0) seconds = 0;
        seconds = Math.floor(seconds);

        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = seconds % 60;

        if (hours > 0) {
            return `${hours}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
        }
        return `${minutes}:${String(secs).padStart(2, '0')}`;
    }

    /**
     * Format seconds as "X min" or "X min Y sec"
     */
    function formatDuration(seconds) {
        if (seconds < 0) seconds = 0;
        seconds = Math.floor(seconds);

        const minutes = Math.floor(seconds / 60);
        const secs = seconds % 60;

        if (minutes === 0) {
            return `${secs} sec`;
        }
        if (secs === 0) {
            return `${minutes} min`;
        }
        return `${minutes} min ${secs} sec`;
    }

    /**
     * Fetch status from API
     */
    async function fetchStatus() {
        try {
            const response = await fetch(statusUrl);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const data = await response.json();
            errorCount = 0;
            return data;
        } catch (error) {
            errorCount++;
            console.error('Failed to fetch status:', error);
            return null;
        }
    }

    /**
     * Dispatch custom event with status data
     */
    function dispatchStatusEvent(status) {
        const event = new CustomEvent('display-status-update', {
            detail: status
        });
        document.dispatchEvent(event);
    }

    /**
     * Update the display with new status
     */
    function updateDisplay(status) {
        if (!status) return;

        lastStatus = status;

        // Dispatch event for template-specific handlers
        dispatchStatusEvent(status);

        // Update common elements
        updateBudgetDisplay(status);
        updateWarningOverlay(status);
        updateChart(status);
        updateProgressBar(status);
        updateCountdown(status);
        updateResetTimer(status);
        updateRunningState(status);
    }

    /**
     * Update budget display elements
     */
    function updateBudgetDisplay(status) {
        const budgetEl = document.querySelector('.budget-value');
        const budgetPercentEl = document.querySelector('.budget-percent');
        const budgetMaxEl = document.querySelector('.budget-max');

        if (budgetEl) {
            budgetEl.textContent = formatTime(status.budget_remaining);
        }
        if (budgetPercentEl) {
            budgetPercentEl.textContent = `${status.budget_percent}%`;
        }
        if (budgetMaxEl) {
            budgetMaxEl.textContent = formatTime(status.budget_max);
        }

        // Update status class
        const budgetContainer = document.querySelector('.budget-display');
        if (budgetContainer) {
            budgetContainer.classList.remove('status-available', 'status-warning', 'status-cooldown');
            if (status.cooldown_active) {
                budgetContainer.classList.add('status-cooldown');
            } else if (status.budget_percent < 20) {
                budgetContainer.classList.add('status-warning');
            } else {
                budgetContainer.classList.add('status-available');
            }
        }
    }

    /**
     * Update warning overlay visibility
     */
    function updateWarningOverlay(status) {
        const overlay = document.querySelector('.warning-overlay');
        if (!overlay) return;

        const cooldownEl = overlay.querySelector('.cooldown-remaining');
        if (cooldownEl && status.cooldown_active) {
            cooldownEl.textContent = formatDuration(status.cooldown_remaining);
        }

        if (status.cooldown_active || !status.available) {
            overlay.classList.add('active');
        } else {
            overlay.classList.remove('active');
        }
    }

    /**
     * Update D3 chart
     */
    function updateChart(status) {
        const chartContainer = document.querySelector('.chart-container');
        if (!chartContainer) return;

        // Use the chart library if available
        if (window.DisplayCharts) {
            window.DisplayCharts.update(chartType, chartContainer, status);
        }
    }

    /**
     * Update progress bar
     */
    function updateProgressBar(status) {
        const barFill = document.querySelector('.bar-fill');
        const barLabel = document.querySelector('.bar-label');

        if (barFill) {
            barFill.style.width = `${status.budget_percent}%`;
            barFill.classList.toggle('warning', status.budget_percent < 20);
        }

        if (barLabel) {
            barLabel.textContent = formatTime(status.budget_remaining);
        }
    }

    /**
     * Update countdown display
     */
    function updateCountdown(status) {
        const countdownValue = document.querySelector('.countdown-value');
        if (!countdownValue) return;

        if (status.cooldown_active) {
            countdownValue.textContent = formatTime(status.cooldown_remaining);
            countdownValue.parentElement?.classList.add('status-cooldown');
        } else {
            countdownValue.textContent = formatTime(status.budget_remaining);
            countdownValue.parentElement?.classList.remove('status-cooldown');
            countdownValue.parentElement?.classList.toggle('status-warning', status.budget_percent < 20);
        }
    }

    /**
     * Update reset timer display
     */
    function updateResetTimer(status) {
        const resetEl = document.querySelector('.reset-timer');
        if (!resetEl) return;

        if (status.resets_in > 0) {
            resetEl.textContent = `Resets in ${formatDuration(status.resets_in)}`;
            resetEl.classList.remove('hidden');
        } else {
            resetEl.classList.add('hidden');
        }
    }

    /**
     * Update running state indicator
     */
    function updateRunningState(status) {
        const runningEls = document.querySelectorAll('[data-running-indicator]');
        runningEls.forEach(el => {
            el.classList.toggle('is-running', status.is_running);
        });
    }

    /**
     * Main polling loop
     */
    async function poll() {
        const status = await fetchStatus();

        if (status) {
            updateDisplay(status);
            // Normal interval
            pollTimer = setTimeout(poll, POLL_INTERVAL);
        } else {
            // Error - use longer reconnect delay
            pollTimer = setTimeout(poll, RECONNECT_DELAY);
        }
    }

    /**
     * Initialize the display
     */
    function init() {
        console.log(`Display initialized for slug: ${slug}, chart: ${chartType}`);

        // Initialize charts if available
        if (window.DisplayCharts) {
            const chartContainer = document.querySelector('.chart-container');
            if (chartContainer) {
                window.DisplayCharts.init(chartType, chartContainer);
            }
        }

        // Start polling
        poll();
    }

    // Start when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Expose API for template-specific code
    window.DisplayStatus = {
        getLastStatus: () => lastStatus,
        formatTime,
        formatDuration,
        refresh: poll
    };

})();
