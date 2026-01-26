/**
 * Modal for editing exhibition properties including schedules feature toggle.
 */

import { useState, useEffect } from 'react';
import { Modal } from '../ui/Modal';

interface EditExhibitionModalProps {
  isOpen: boolean;
  exhibition: {
    id: string;
    name: string;
    enabled: boolean;
    schedules_enabled: boolean;
  } | null;
  onClose: () => void;
  onSave: (
    id: string,
    data: { name: string; enabled: boolean; schedules_enabled: boolean }
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
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (exhibition) {
      setName(exhibition.name);
      setEnabled(exhibition.enabled);
      setSchedulesEnabled(exhibition.schedules_enabled);
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
    </Modal>
  );
}
