// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT

/**
 * Centralized date/time formatting utilities.
 * Extracted from multiple components to reduce duplication.
 */

/**
 * Format an ISO datetime string to full locale datetime.
 * Handles UTC strings from backend (naive ISO strings without Z).
 * @param isoString - ISO datetime string or null
 * @returns Formatted datetime string or 'Never' if null
 */
export function formatDateTime(isoString: string | null): string {
  if (!isoString) return 'Never';
  // Backend stores UTC but returns naive ISO strings - append Z to parse as UTC
  const utcString = isoString.endsWith('Z') ? isoString : isoString + 'Z';
  const date = new Date(utcString);
  return date.toLocaleString();
}

/**
 * Format an ISO datetime string to short datetime (weekday, month, day + time).
 * @param isoString - ISO datetime string or null
 * @returns Short formatted datetime or 'Never' if null
 */
export function formatShortDateTime(isoString: string | null): string {
  if (!isoString) return 'Never';
  const utcString = isoString.endsWith('Z') ? isoString : isoString + 'Z';
  const date = new Date(utcString);
  return date.toLocaleDateString('de-DE', { weekday: 'short', day: 'numeric', month: 'short' }) +
    ' ' + date.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
}

/**
 * Format a Date object to short date only (weekday, month, day).
 * @param date - Date object
 * @returns Formatted short date string
 */
export function formatShortDate(date: Date): string {
  return date.toLocaleDateString('de-DE', { weekday: 'short', day: 'numeric', month: 'short' });
}

/**
 * Format relative time in the past ("5s ago", "3m ago", "2h ago").
 * @param isoString - ISO datetime string or null
 * @returns Relative time string or 'Never' if null
 */
export function formatTimeAgo(isoString: string | null): string {
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

/**
 * Format relative time in the future ("in 5s", "in 3m", "in 2h").
 * @param isoString - ISO datetime string
 * @returns Relative future time string
 */
export function formatTimeUntil(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = date.getTime() - now.getTime();
  const diffSec = Math.floor(diffMs / 1000);

  if (diffSec <= 0) return 'now';
  if (diffSec < 60) return `in ${diffSec}s`;
  if (diffSec < 3600) return `in ${Math.floor(diffSec / 60)}m`;
  return `in ${Math.floor(diffSec / 3600)}h`;
}

/**
 * Format relative time for a Date object ("just now", "5m ago", "2h ago", "3d ago").
 * @param date - Date object
 * @returns Relative time string
 */
export function formatRelativeTime(date: Date): string {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${diffDays}d ago`;
}

/**
 * Format duration in milliseconds to human-readable string.
 * @param ms - Duration in milliseconds
 * @returns Formatted duration string (e.g., "2h 30m", "5m 10s", "30s")
 */
export function formatDuration(ms: number): string {
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

/**
 * Format seconds to human-readable time string.
 * @param seconds - Duration in seconds
 * @returns Formatted duration string (e.g., "2h 30m", "5m 10s", "30s")
 */
export function formatSeconds(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (mins < 60) return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
  const hours = Math.floor(mins / 60);
  const remainingMins = mins % 60;
  return remainingMins > 0 ? `${hours}h ${remainingMins}m` : `${hours}h`;
}

/**
 * Format timestamp for log display (time only, German locale).
 * @param timestamp - ISO timestamp string
 * @returns Formatted time string (HH:MM:SS)
 */
export function formatLogTime(timestamp: string): string {
  // Backend stores UTC - append Z if missing to parse correctly
  const utcString = timestamp.endsWith('Z') ? timestamp : timestamp + 'Z';
  const date = new Date(utcString);
  return date.toLocaleTimeString('de-DE', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
}

/**
 * Format timestamp for full log display (date + time, German locale).
 * @param timestamp - ISO timestamp string
 * @returns Formatted datetime string (MM/DD HH:MM:SS)
 */
export function formatLogTimeFull(timestamp: string): string {
  // Backend stores UTC - append Z if missing to parse correctly
  const utcString = timestamp.endsWith('Z') ? timestamp : timestamp + 'Z';
  const date = new Date(utcString);
  return date.toLocaleString('de-DE', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
}

/**
 * Format a cron expression to human-readable string.
 * @param cron - Cron expression (5 parts: minute hour dayOfMonth month dayOfWeek)
 * @returns Human-readable description or the original expression if not recognized
 */
export function formatCronExpression(cron: string): string {
  const parts = cron.split(' ');
  if (parts.length !== 5) return cron;

  const [minute, hour, dayOfMonth, month, dayOfWeek] = parts;

  // Common patterns
  if (minute !== '*' && hour !== '*' && dayOfMonth === '*' && month === '*') {
    const timeStr = `${hour.padStart(2, '0')}:${minute.padStart(2, '0')}`;
    if (dayOfWeek === '*') {
      return `Daily at ${timeStr}`;
    }
    if (dayOfWeek === '1-5') {
      return `Weekdays at ${timeStr}`;
    }
    if (dayOfWeek === '0,6') {
      return `Weekends at ${timeStr}`;
    }
    const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    const dayParts = dayOfWeek.split(',');
    if (dayParts.length <= 2) {
      const dayNames = dayParts.map(d => days[parseInt(d)] || d).join(', ');
      return `${dayNames} at ${timeStr}`;
    }
  }

  return cron;
}
