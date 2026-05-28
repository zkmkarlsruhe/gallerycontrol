// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT
/**
 * Modal for editing exhibition properties: name/enabled/schedules + the set of
 * satellites available to its devices. Each device then picks one of these
 * satellites (or "Direct connection") in the device modal.
 */

import { useState, useEffect } from 'react';
import { Modal } from '../ui/Modal';
import type { Satellite, SatelliteInfo } from '../../types';

interface EditExhibitionModalProps {
  isOpen: boolean;
  exhibition: {
    id: string;
    name: string;
    enabled: boolean;
    schedules_enabled: boolean;
    satellite_ids?: string[];
    satellites?: SatelliteInfo[];
  } | null;
  onClose: () => void;
  onSave: (
    id: string,
    data: { name: string; enabled: boolean; schedules_enabled: boolean; satellite_ids: string[] }
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
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [satellites, setSatellites] = useState<Satellite[]>([]);
  const [loadingSatellites, setLoadingSatellites] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
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
  }, [isOpen]);

  useEffect(() => {
    if (exhibition) {
      setName(exhibition.name);
      setEnabled(exhibition.enabled);
      setSchedulesEnabled(exhibition.schedules_enabled);
      const ids =
        exhibition.satellite_ids ??
        exhibition.satellites?.map((s) => s.id) ??
        [];
      setSelectedIds(new Set(ids));
    }
  }, [exhibition]);

  if (!exhibition) return null;

  const toggle = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleSave = async () => {
    if (!name.trim()) return;
    setSaving(true);
    try {
      await onSave(exhibition.id, {
        name: name.trim(),
        enabled,
        schedules_enabled: schedulesEnabled,
        satellite_ids: Array.from(selectedIds),
      });
      onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      title="Edit Exhibition"
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn btn-secondary btn-sm" onClick={onClose}>
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

      <div className="mb-3">
        <label className="form-label d-block mb-2"><strong>Satellite Relays</strong></label>
        <div className="small text-muted mb-2">
          Make these satellites available for devices in this exhibition. Each device then picks one (or "Direct connection") in its own edit form.
        </div>
        {loadingSatellites && <div className="small text-muted">Loading satellites...</div>}
        {!loadingSatellites && satellites.length === 0 && (
          <div className="small text-muted">No approved satellites yet. Approve one in Admin → Satellites first.</div>
        )}
        {satellites.map((sat) => (
          <div className="form-check" key={sat.id}>
            <input
              className="form-check-input"
              type="checkbox"
              id={`exhibition-satellite-${sat.id}`}
              checked={selectedIds.has(sat.id)}
              onChange={() => toggle(sat.id)}
            />
            <label className="form-check-label" htmlFor={`exhibition-satellite-${sat.id}`}>
              {sat.name}{' '}
              <span className={`badge ${sat.is_connected ? 'bg-success' : 'bg-secondary'} ms-1`}>
                {sat.is_connected ? 'online' : 'offline'}
              </span>
            </label>
          </div>
        ))}
        <div className="small text-muted mt-2">
          Removing a satellite that's still used by a device in this exhibition will clear that device's routing back to direct.
        </div>
      </div>
    </Modal>
  );
}
