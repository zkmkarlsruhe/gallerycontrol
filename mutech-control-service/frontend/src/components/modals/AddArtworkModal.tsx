import { useState } from 'react';
import { Modal } from '../ui/Modal';

interface AddArtworkModalProps {
  isOpen: boolean;
  exhibitionName: string;
  exhibitionId: string;
  onClose: () => void;
  onSave: (exhibitionId: string, name: string) => Promise<void>;
}

export function AddArtworkModal({
  isOpen,
  exhibitionName,
  exhibitionId,
  onClose,
  onSave,
}: AddArtworkModalProps) {
  const [names, setNames] = useState('');
  const [saving, setSaving] = useState(false);

  const getNames = () => names.split(',').map(n => n.trim()).filter(n => n.length > 0);

  const handleSave = async () => {
    const nameList = getNames();
    if (nameList.length === 0) return;
    setSaving(true);
    try {
      for (const name of nameList) {
        await onSave(exhibitionId, name);
      }
      setNames('');
      onClose();
    } finally {
      setSaving(false);
    }
  };

  const nameCount = getNames().length;

  return (
    <Modal
      isOpen={isOpen}
      title="Add Artwork"
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleSave}
            disabled={saving || nameCount === 0}
          >
            {saving ? 'Saving...' : nameCount > 1 ? `Add ${nameCount} Artworks` : 'Add Artwork'}
          </button>
        </>
      }
    >
      <div className="context-info mb-3">
        <strong>Adding artwork to:</strong>
        <div className="mt-2">
          Exhibition: <strong>{exhibitionName}</strong>
        </div>
      </div>
      <div className="mb-3">
        <label className="form-label">Artwork Name(s)</label>
        <input
          type="text"
          className="form-control"
          placeholder="e.g. Raum 1, Raum 2, Raum 3"
          value={names}
          onChange={(e) => setNames(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSave()}
          autoFocus
        />
        <small className="form-text text-muted">Separate multiple names with commas</small>
      </div>
    </Modal>
  );
}
