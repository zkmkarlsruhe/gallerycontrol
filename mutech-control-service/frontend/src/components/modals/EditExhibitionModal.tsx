/**
 * Modal for editing exhibition properties including schedules feature toggle
 * and satellite relay assignment.
 */

import { useState, useEffect } from 'react';
import { Modal } from '../ui/Modal';
import type { Satellite } from '../../types';

interface EditExhibitionModalProps {
  isOpen: boolean;
  exhibition: {
    id: string;
    name: string;
    enabled: boolean;
    schedules_enabled: boolean;
    satellite_id: string | null;
  } | null;
  onClose: () => void;
  onSave: (
    id: string,
    data: { name: string; enabled: boolean; schedules_enabled: boolean; satellite_id: string | null }
  ) => Promise<void>;
}

export function EditExhibitionModal({
  isOpen,
  exhibition,
  onClose,
  onSave,
}: EditExhibitionModalProps) {
  const [name, setName] = useState('');
  const [enabled, setEnabled] = useState(true);
  const [schedulesEnabled, setSchedulesEnabled] = useState(false);
  const [satelliteId, setSatelliteId] = useState<string | null>(null);
  const [satellites, setSatellites] = useState<Satellite[]>([]);
  const [loadingSatellites, setLoadingSatellites] = useState(false);
  const [saving, setSaving] = useState(false);

  // Load satellites when modal opens
  useEffect(() => {
    if (isOpen) {
      setLoadingSatellites(true);
      fetch('/api/admin/satellites')
        .then((res) => res.json())
        .then((data) => {
          setSatellites(data.filter((s: Satellite) => s.status === 'approved'));
        })
        .catch((err) => {
          console.error('Failed to load satellites:', err);
          setSatellites([]);
        })
        .finally(() => setLoadingSatellites(false));
    }
  }, [isOpen]);

  useEffect(() => {
    if (exhibition) {
      setName(exhibition.name);
      setEnabled(exhibition.enabled);
      setSchedulesEnabled(exhibition.schedules_enabled);
      setSatelliteId(exhibition.satellite_id);
    }
  }, [exhibition]);

  if (!exhibition) return null;

  const handleSave = async () => {
    if (!name.trim()) return;
    setSaving(true);
    try {
      await onSave(exhibition.id, {
        name: name.trim(),
        enabled,
        schedules_enabled: schedulesEnabled,
        satellite_id: satelliteId,
      });
      onClose();
    } finally {
      setSaving(false);
    }
  };

  const selectedSatellite = satellites.find((s) => s.id === satelliteId);

  return (
    <Modal
      isOpen={isOpen}
      title="Edit Exhibition"
      onClose={onClose}
      footer={
        <>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={onClose}
          >
            Close
          </button>
          <button
            type="button"
            className="btn btn-primary btn-sm"
            onClick={handleSave}
            disabled={saving || !name.trim()}
          >
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
        </>
      }
    >
      <div className="mb-3">
        <label className="form-label">Exhibition Name</label>
        <input
          type="text"
          className="form-control"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSave()}
          autoFocus
        />
      </div>

      <div className="mb-3">
        <div className="form-check form-switch">
          <input
            className="form-check-input"
            type="checkbox"
            id="exhibition-enabled"
            checked={enabled}
            onChange={(e) => setEnabled(e.target.checked)}
            style={{ width: '3rem', height: '1.5rem' }}
          />
          <label className="form-check-label ms-2" htmlFor="exhibition-enabled">
            <strong>{enabled ? 'Enabled' : 'Disabled'}</strong>
          </label>
        </div>
        <div className="info-box mt-2">
          {enabled
            ? 'Exhibition is active. All artworks and devices will be controlled normally.'
            : 'Exhibition is disabled. All artworks and devices within will be excluded from control and polling.'}
        </div>
      </div>

      {/* Settings Section */}
      <hr />
      <div className="mb-3">
        <label className="form-label d-block mb-2"><strong>Settings</strong></label>
        <div className="form-check">
          <input
            className="form-check-input"
            type="checkbox"
            id="exhibition-schedules-enabled"
            checked={schedulesEnabled}
            onChange={(e) => setSchedulesEnabled(e.target.checked)}
          />
          <label className="form-check-label" htmlFor="exhibition-schedules-enabled">
            Enable Schedules
          </label>
          <div className="small text-muted">
            When enabled, shows the calendar button and allows scheduled on/off actions
          </div>
        </div>
      </div>

      {/* Satellite Section */}
      <div className="mb-3">
        <label className="form-label" htmlFor="exhibition-satellite">
          <strong>Satellite Relay</strong>
        </label>
        <select
          id="exhibition-satellite"
          className="form-select"
          value={satelliteId || ''}
          onChange={(e) => setSatelliteId(e.target.value || null)}
          disabled={loadingSatellites}
        >
          <option value="">No satellite (direct connection)</option>
          {satellites.map((sat) => (
            <option key={sat.id} value={sat.id}>
              {sat.name} {sat.is_connected ? '(online)' : '(offline)'}
            </option>
          ))}
        </select>
        <div className="small text-muted mt-1">
          Assign a satellite relay to route commands for devices in this exhibition
        </div>
        {selectedSatellite && !selectedSatellite.is_connected && (
          <div className="alert alert-warning mt-2 py-2 small">
            <i className="bi bi-exclamation-triangle me-1"></i>
            Selected satellite is currently offline. Commands will fail until it reconnects.
          </div>
        )}
      </div>
    </Modal>
  );
}
