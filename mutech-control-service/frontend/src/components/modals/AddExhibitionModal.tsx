import { useState } from 'react';
import { Modal } from '../ui/Modal';

interface AddExhibitionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (name: string) => Promise<void>;
}

export function AddExhibitionModal({ isOpen, onClose, onSave }: AddExhibitionModalProps) {
  const [names, setNames] = useState('');
  const [saving, setSaving] = useState(false);

  const getNames = () => names.split(',').map(n => n.trim()).filter(n => n.length > 0);

  const handleSave = async () => {
    const nameList = getNames();
    if (nameList.length === 0) return;
    setSaving(true);
    try {
      for (const name of nameList) {
        await onSave(name);
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
      title="Add Exhibition"
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
            disabled={saving || nameCount === 0}
          >
            {saving ? 'Saving...' : nameCount > 1 ? `Add ${nameCount} Exhibitions` : 'Add Exhibition'}
          </button>
        </>
      }
    >
      <div className="mb-3">
        <label className="form-label">Exhibition Name(s)</label>
        <input
          type="text"
          className="form-control"
          placeholder="e.g. Exhibition 1, Exhibition 2, Exhibition 3"
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
