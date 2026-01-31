// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT
/**
 * Modal for editing artwork protection configuration (time slices).
 */

import { useState, useEffect } from 'react';
import { Modal } from '../ui/Modal';
import type { Artwork, ProtectionConfig, ProtectionTimeSlice } from '../../types';

interface ProtectionConfigModalProps {
  isOpen: boolean;
  artwork: Artwork | null;
  onClose: () => void;
  onSave: (artworkId: string, config: ProtectionConfig | null) => Promise<void>;
}

export function ProtectionConfigModal({
  isOpen,
  artwork,
  onClose,
  onSave,
}: ProtectionConfigModalProps) {
  const [timeSlices, setTimeSlices] = useState<ProtectionTimeSlice[]>([]);
  const [maxRuntime, setMaxRuntime] = useState<number | ''>('');
  const [cooldown, setCooldown] = useState<number | ''>('');
  const [minBudgetToStart, setMinBudgetToStart] = useState<number | ''>('');
  const [forceCompletion, setForceCompletion] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (artwork?.protection_config) {
      const config = artwork.protection_config;
      setTimeSlices(config.time_slices || []);
      setMaxRuntime(config.max_runtime ?? '');
      setCooldown(config.cooldown ?? '');
      setMinBudgetToStart(config.min_budget_to_start ?? '');
      setForceCompletion(config.force_completion ?? false);
    } else {
      // Reset to defaults
      setTimeSlices([]);
      setMaxRuntime('');
      setCooldown('');
      setMinBudgetToStart('');
      setForceCompletion(false);
    }
  }, [artwork]);

  if (!artwork) return null;

  const handleAddTimeSlice = () => {
    setTimeSlices([...timeSlices, { window: 1, max: 0.5 }]);
  };

  const handleRemoveTimeSlice = (index: number) => {
    setTimeSlices(timeSlices.filter((_, i) => i !== index));
  };

  const handleUpdateTimeSlice = (index: number, field: 'window' | 'max', value: number) => {
    const updated = [...timeSlices];
    updated[index] = { ...updated[index], [field]: value };
    setTimeSlices(updated);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      // Build config - only include fields that have values
      const hasAnyConfig = timeSlices.length > 0 || maxRuntime !== '' || cooldown !== '' || minBudgetToStart !== '';

      if (!hasAnyConfig) {
        // Remove protection config entirely
        await onSave(artwork.id, null);
      } else {
        const config: ProtectionConfig = {};

        if (timeSlices.length > 0) {
          config.time_slices = timeSlices;
        }
        if (maxRuntime !== '') {
          config.max_runtime = maxRuntime;
        }
        if (cooldown !== '') {
          config.cooldown = cooldown;
        }
        if (minBudgetToStart !== '') {
          config.min_budget_to_start = minBudgetToStart;
        }
        if (forceCompletion) {
          config.force_completion = forceCompletion;
        }

        await onSave(artwork.id, config);
      }
      onClose();
    } finally {
      setSaving(false);
    }
  };

  const handleClearAll = async () => {
    setSaving(true);
    try {
      await onSave(artwork.id, null);
      onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      title={`Protection Config: ${artwork.name}`}
      onClose={onClose}
      footer={
        <>
          <button
            type="button"
            className="btn btn-outline-danger btn-sm me-auto"
            onClick={handleClearAll}
            disabled={saving || (!artwork.protection_config && timeSlices.length === 0)}
            title="Remove all protection settings"
          >
            Clear All
          </button>
          <button type="button" className="btn btn-secondary btn-sm" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-primary btn-sm"
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
        </>
      }
    >
      {/* Time Slices */}
      <div className="mb-3">
        <label className="form-label d-flex justify-content-between align-items-center">
          <span>Time Slices</span>
          <button
            type="button"
            className="btn btn-sm btn-outline-primary"
            onClick={handleAddTimeSlice}
          >
            + Add Slice
          </button>
        </label>
        <div className="info-box mb-2">
          Limit how long the artwork can run within a time window.
          Example: max 30 seconds per 1 minute window.
        </div>
        {timeSlices.length === 0 ? (
          <div className="text-muted small">No time slices configured</div>
        ) : (
          <div className="time-slices-list">
            {timeSlices.map((slice, index) => (
              <div key={index} className="time-slice-row d-flex align-items-center gap-2 mb-2">
                <span className="text-muted small">Max</span>
                <input
                  type="number"
                  className="form-control form-control-sm"
                  style={{ width: '70px' }}
                  value={slice.max}
                  onChange={(e) => handleUpdateTimeSlice(index, 'max', parseFloat(e.target.value) || 0)}
                  step="0.25"
                  min="0"
                />
                <span className="text-muted small">min per</span>
                <input
                  type="number"
                  className="form-control form-control-sm"
                  style={{ width: '60px' }}
                  value={slice.window}
                  onChange={(e) => handleUpdateTimeSlice(index, 'window', parseInt(e.target.value) || 1)}
                  min="1"
                />
                <span className="text-muted small">min window</span>
                <button
                  type="button"
                  className="btn btn-sm btn-outline-danger"
                  onClick={() => handleRemoveTimeSlice(index)}
                  title="Remove this time slice"
                >
                  <i className="bi bi-trash"></i>
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Max Runtime */}
      <div className="mb-3">
        <label className="form-label">Max Runtime (seconds)</label>
        <input
          type="number"
          className="form-control form-control-sm"
          value={maxRuntime}
          onChange={(e) => setMaxRuntime(e.target.value === '' ? '' : parseInt(e.target.value))}
          placeholder="No limit"
          min="1"
        />
        <div className="form-text">Maximum continuous ON time before auto-OFF</div>
      </div>

      {/* Cooldown */}
      <div className="mb-3">
        <label className="form-label">Cooldown (seconds)</label>
        <input
          type="number"
          className="form-control form-control-sm"
          value={cooldown}
          onChange={(e) => setCooldown(e.target.value === '' ? '' : parseInt(e.target.value))}
          placeholder="No cooldown"
          min="0"
        />
        <div className="form-text">Wait time after OFF before allowing ON again</div>
      </div>

      {/* Min Budget to Start */}
      <div className="mb-3">
        <label className="form-label">Min Budget to Start (seconds)</label>
        <input
          type="number"
          className="form-control form-control-sm"
          value={minBudgetToStart}
          onChange={(e) => setMinBudgetToStart(e.target.value === '' ? '' : parseInt(e.target.value))}
          placeholder="0"
          min="0"
        />
        <div className="form-text">Minimum remaining budget required to turn ON</div>
      </div>

      {/* Force Completion */}
      <div className="mb-3">
        <div className="form-check form-switch">
          <input
            className="form-check-input"
            type="checkbox"
            id="force-completion"
            checked={forceCompletion}
            onChange={(e) => setForceCompletion(e.target.checked)}
          />
          <label className="form-check-label" htmlFor="force-completion">
            Force Completion
          </label>
        </div>
        <div className="form-text">Ignore OFF commands until max_runtime is reached</div>
      </div>
    </Modal>
  );
}
