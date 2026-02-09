// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT
/**
 * Form component for configuring artwork protection rules.
 * Prevents overuse with time slices, max runtime, and cooldown.
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import type { ProtectionConfig, ProtectionTimeSlice } from '../../types';

interface ProtectionConfigFormProps {
  value: ProtectionConfig | null | undefined;
  onChange: (config: ProtectionConfig | null) => void;
}

// Validate time slice consistency (pure function, no hooks needed)
function validateTimeSlices(slices: ProtectionTimeSlice[]): string | null {
  if (slices.length < 2) return null;

  const sorted = [...slices].sort((a, b) => a.window - b.window);

  for (let i = 0; i < sorted.length - 1; i++) {
    const inner = sorted[i];
    for (let j = i + 1; j < sorted.length; j++) {
      const outer = sorted[j];
      const maxPossible = (outer.window / inner.window) * inner.max;
      if (outer.max > maxPossible) {
        return `${outer.window}min max (${outer.max}min) exceeds possible from ${inner.window}min window (${Math.floor(maxPossible)}min max)`;
      }
    }
  }

  return null;
}

export function ProtectionConfigForm({ value, onChange }: ProtectionConfigFormProps) {
  const [enabled, setEnabled] = useState(!!value);
  const [timeSlices, setTimeSlices] = useState<ProtectionTimeSlice[]>(
    value?.time_slices || []
  );
  const [maxRuntime, setMaxRuntime] = useState<number | ''>(
    value?.max_runtime ?? ''
  );
  const [cooldown, setCooldown] = useState<number | ''>(value?.cooldown ?? '');
  const [forceCompletion, setForceCompletion] = useState(
    value?.force_completion ?? false
  );
  const [minBudget, setMinBudget] = useState<number | ''>(
    value?.min_budget_to_start ?? ''
  );

  // Derive validation error from time slices (no need for state)
  const validationError = useMemo(() => validateTimeSlices(timeSlices), [timeSlices]);

  // Memoize onChange to avoid unnecessary effect runs
  const stableOnChange = useCallback((config: ProtectionConfig | null) => onChange(config), [onChange]);

  // Update parent when values change
  useEffect(() => {
    if (!enabled) {
      stableOnChange(null);
      return;
    }

    if (validationError) {
      return; // Don't update parent with invalid config
    }

    const config: ProtectionConfig = {};

    if (timeSlices.length > 0) {
      config.time_slices = timeSlices;
    }
    if (typeof maxRuntime === 'number' && maxRuntime > 0) {
      config.max_runtime = maxRuntime;
    }
    if (typeof cooldown === 'number' && cooldown > 0) {
      config.cooldown = cooldown;
    }
    if (forceCompletion) {
      config.force_completion = true;
    }
    if (typeof minBudget === 'number' && minBudget > 0) {
      config.min_budget_to_start = minBudget;
    }

    stableOnChange(Object.keys(config).length > 0 ? config : null);
  }, [enabled, timeSlices, maxRuntime, cooldown, forceCompletion, minBudget, validationError, stableOnChange]);

  const addTimeSlice = () => {
    setTimeSlices([...timeSlices, { window: 15, max: 7 }]);
  };

  const removeTimeSlice = (index: number) => {
    setTimeSlices(timeSlices.filter((_, i) => i !== index));
  };

  const updateTimeSlice = (
    index: number,
    field: 'window' | 'max',
    value: number
  ) => {
    const updated = [...timeSlices];
    updated[index] = { ...updated[index], [field]: value };
    setTimeSlices(updated);
  };

  const formatSeconds = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
  };

  return (
    <div className="protection-config-form">
      <div className="form-check form-switch mb-3">
        <input
          className="form-check-input"
          type="checkbox"
          id="protection-enabled"
          checked={enabled}
          onChange={(e) => setEnabled(e.target.checked)}
          style={{ width: '3rem', height: '1.5rem' }}
        />
        <label className="form-check-label ms-2" htmlFor="protection-enabled">
          <strong>Protection Rules</strong>
        </label>
      </div>

      {!enabled && (
        <div className="info-box">
          Protection is disabled. No runtime limits will be enforced.
        </div>
      )}

      {enabled && (
        <div className="protection-settings">
          {/* Time Slices */}
          <div className="mb-3">
            <label className="form-label d-flex justify-content-between align-items-center">
              <span>Time Windows</span>
              <button
                type="button"
                className="btn btn-outline-primary btn-sm"
                onClick={addTimeSlice}
              >
                + Add Window
              </button>
            </label>
            <div className="small text-muted mb-2">
              Budget limits per time period (e.g., max 7 min per 15-min chunk)
            </div>

            {timeSlices.length === 0 && (
              <div className="text-muted small">No time windows configured</div>
            )}

            {timeSlices.map((slice, index) => (
              <div key={index} className="d-flex gap-2 mb-2 align-items-center">
                <div className="input-group input-group-sm" style={{ flex: 1 }}>
                  <span className="input-group-text">Max</span>
                  <input
                    type="number"
                    className="form-control"
                    min={1}
                    value={slice.max}
                    onChange={(e) =>
                      updateTimeSlice(index, 'max', parseInt(e.target.value) || 1)
                    }
                  />
                  <span className="input-group-text">min per</span>
                  <input
                    type="number"
                    className="form-control"
                    min={1}
                    value={slice.window}
                    onChange={(e) =>
                      updateTimeSlice(
                        index,
                        'window',
                        parseInt(e.target.value) || 1
                      )
                    }
                  />
                  <span className="input-group-text">min</span>
                </div>
                <button
                  type="button"
                  className="btn btn-outline-danger btn-sm"
                  onClick={() => removeTimeSlice(index)}
                  title="Remove"
                >
                  &times;
                </button>
              </div>
            ))}

            {validationError && (
              <div className="text-danger small mt-1">{validationError}</div>
            )}
          </div>

          {/* Max Runtime */}
          <div className="mb-3">
            <label className="form-label">Max Continuous Runtime</label>
            <div className="input-group input-group-sm">
              <input
                type="number"
                className="form-control"
                min={0}
                placeholder="No limit"
                value={maxRuntime}
                onChange={(e) =>
                  setMaxRuntime(e.target.value ? parseInt(e.target.value) : '')
                }
              />
              <span className="input-group-text">seconds</span>
            </div>
            {typeof maxRuntime === 'number' && maxRuntime > 0 && (
              <div className="small text-muted">
                {formatSeconds(maxRuntime)} before forced off
              </div>
            )}
          </div>

          {/* Cooldown */}
          <div className="mb-3">
            <label className="form-label">Cooldown Period</label>
            <div className="input-group input-group-sm">
              <input
                type="number"
                className="form-control"
                min={0}
                placeholder="No cooldown"
                value={cooldown}
                onChange={(e) =>
                  setCooldown(e.target.value ? parseInt(e.target.value) : '')
                }
              />
              <span className="input-group-text">seconds</span>
            </div>
            {typeof cooldown === 'number' && cooldown > 0 && (
              <div className="small text-muted">
                {formatSeconds(cooldown)} rest after max runtime
              </div>
            )}
          </div>

          {/* Min Budget to Start */}
          <div className="mb-3">
            <label className="form-label">Minimum Budget to Start</label>
            <div className="input-group input-group-sm">
              <input
                type="number"
                className="form-control"
                min={0}
                placeholder="0"
                value={minBudget}
                onChange={(e) =>
                  setMinBudget(e.target.value ? parseInt(e.target.value) : '')
                }
              />
              <span className="input-group-text">seconds</span>
            </div>
            <div className="small text-muted">
              Won't start if available budget is below this
            </div>
          </div>

          {/* Force Completion */}
          <div className="form-check mb-3">
            <input
              className="form-check-input"
              type="checkbox"
              id="force-completion"
              checked={forceCompletion}
              onChange={(e) => setForceCompletion(e.target.checked)}
            />
            <label className="form-check-label" htmlFor="force-completion">
              Force Completion Mode
            </label>
            <div className="small text-muted">
              Ignores OFF commands until max runtime is reached
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
