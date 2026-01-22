import { useState, useEffect } from 'react';
import { Modal } from '../ui/Modal';

interface EditArtworkModalProps {
  isOpen: boolean;
  artwork: {
    id: string;
    name: string;
    enabled: boolean;
  } | null;
  onClose: () => void;
  onSave: (id: string, data: { name: string; enabled: boolean }) => Promise<void>;
}

export function EditArtworkModal({
  isOpen,
  artwork,
  onClose,
  onSave,
}: EditArtworkModalProps) {
  const [name, setName] = useState('');
  const [enabled, setEnabled] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (artwork) {
      setName(artwork.name);
      setEnabled(artwork.enabled);
    }
  }, [artwork]);

  if (!artwork) return null;

  const handleSave = async () => {
    if (!name.trim()) return;
    setSaving(true);
    try {
      await onSave(artwork.id, { name: name.trim(), enabled });
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
    </Modal>
  );
}
