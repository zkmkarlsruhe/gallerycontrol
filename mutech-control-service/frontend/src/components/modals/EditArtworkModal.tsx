/**
 * Modal for editing artwork properties.
 */

import { useState, useEffect } from 'react';
import { Modal } from '../ui/Modal';

interface EditArtworkModalProps {
  isOpen: boolean;
  artwork: {
    id: string;
    name: string;
    enabled: boolean;
    timeslice_enabled: boolean;
    schedules_enabled: boolean;
  } | null;
  onClose: () => void;
  onSave: (
    id: string,
    data: {
      name: string;
      enabled: boolean;
      timeslice_enabled: boolean;
      schedules_enabled: boolean;
    }
  ) => Promise<void>;
}

export function EditArtworkModal({
  isOpen,
  artwork,
  onClose,
  onSave,
}: EditArtworkModalProps) {
  const [name, setName] = useState('');
  const [enabled, setEnabled] = useState(true);
  const [timesliceEnabled, setTimesliceEnabled] = useState(false);
  const [schedulesEnabled, setSchedulesEnabled] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (artwork) {
      setName(artwork.name);
      setEnabled(artwork.enabled);
      setTimesliceEnabled(artwork.timeslice_enabled);
      setSchedulesEnabled(artwork.schedules_enabled);
    }
  }, [artwork]);

  if (!artwork) return null;

  const handleSave = async () => {
    if (!name.trim()) return;
    setSaving(true);
    try {
      await onSave(artwork.id, {
        name: name.trim(),
        enabled,
        timeslice_enabled: timesliceEnabled,
        schedules_enabled: schedulesEnabled,
      });
      onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      title="Edit Artwork"
      onClose={onClose}
      size="lg"
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
      {/* Basic Info Section */}
      <div className="mb-3">
        <label className="form-label">Artwork Name</label>
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
            id="artwork-enabled"
            checked={enabled}
            onChange={(e) => setEnabled(e.target.checked)}
            style={{ width: '3rem', height: '1.5rem' }}
          />
          <label className="form-check-label ms-2" htmlFor="artwork-enabled">
            <strong>{enabled ? 'Enabled' : 'Disabled'}</strong>
          </label>
        </div>
        <div className="info-box mt-2">
          {enabled
            ? 'Artwork is active. All devices will be controlled normally.'
            : 'Artwork is disabled. All devices within will be excluded from control and polling.'}
        </div>
      </div>

      {/* Settings Section */}
      <hr />
      <div className="mb-3">
        <label className="form-label d-block mb-2"><strong>Settings</strong></label>
        <div className="form-check mb-2">
          <input
            className="form-check-input"
            type="checkbox"
            id="artwork-timeslice-enabled"
            checked={timesliceEnabled}
            onChange={(e) => setTimesliceEnabled(e.target.checked)}
          />
          <label className="form-check-label" htmlFor="artwork-timeslice-enabled">
            Enable Time Slice Protection
          </label>
          <div className="small text-muted">
            Shows the shield button to configure time-based runtime limits
          </div>
        </div>
        <div className="form-check">
          <input
            className="form-check-input"
            type="checkbox"
            id="artwork-schedules-enabled"
            checked={schedulesEnabled}
            onChange={(e) => setSchedulesEnabled(e.target.checked)}
          />
          <label className="form-check-label" htmlFor="artwork-schedules-enabled">
            Enable Schedules
          </label>
          <div className="small text-muted">
            When enabled, shows the calendar button and allows scheduled on/off actions
          </div>
        </div>
      </div>

    </Modal>
  );
}
