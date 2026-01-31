// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT
/**
 * Reusable modal for editing named entities with enabled toggle.
 * Used by EditExhibitionModal and EditArtworkModal.
 */

import { useState, useEffect } from 'react';
import { Modal } from '../ui/Modal';

interface Entity {
  id: string;
  name: string;
  enabled: boolean;
}

interface EditNamedEntityModalProps {
  isOpen: boolean;
  entity: Entity | null;
  entityLabel: string; // e.g. "Exhibition" or "Artwork"
  enabledInfoText: string;
  disabledInfoText: string;
  onClose: () => void;
  onSave: (id: string, data: { name: string; enabled: boolean }) => Promise<void>;
}

export function EditNamedEntityModal({
  isOpen,
  entity,
  entityLabel,
  enabledInfoText,
  disabledInfoText,
  onClose,
  onSave,
}: EditNamedEntityModalProps) {
  const [name, setName] = useState('');
  const [enabled, setEnabled] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (entity) {
      setName(entity.name);
      setEnabled(entity.enabled);
    }
  }, [entity]);

  if (!entity) return null;

  const handleSave = async () => {
    if (!name.trim()) return;
    setSaving(true);
    try {
      await onSave(entity.id, { name: name.trim(), enabled });
      onClose();
    } finally {
      setSaving(false);
    }
  };

  const checkboxId = `${entityLabel.toLowerCase()}-enabled`;

  return (
    <Modal
      isOpen={isOpen}
      title={`Edit ${entityLabel}`}
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
        <label className="form-label">{entityLabel} Name</label>
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
            id={checkboxId}
            checked={enabled}
            onChange={(e) => setEnabled(e.target.checked)}
            style={{ width: '3rem', height: '1.5rem' }}
          />
          <label className="form-check-label ms-2" htmlFor={checkboxId}>
            <strong>{enabled ? 'Enabled' : 'Disabled'}</strong>
          </label>
        </div>
        <div className="info-box mt-2">
          {enabled ? enabledInfoText : disabledInfoText}
        </div>
      </div>
    </Modal>
  );
}
