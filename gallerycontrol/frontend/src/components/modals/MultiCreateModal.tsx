// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT
/**
 * Reusable modal for creating multiple items from comma-separated input.
 * Used by AddExhibitionModal and AddArtworkModal.
 */

import { useState } from 'react';
import { Modal } from '../ui/Modal';

interface MultiCreateModalProps {
  isOpen: boolean;
  title: string;
  itemLabel: string; // e.g. "Exhibition" or "Artwork"
  itemLabelPlural: string; // e.g. "Exhibitions" or "Artworks"
  placeholder: string;
  onClose: () => void;
  onSave: (name: string) => Promise<void>;
  contextInfo?: React.ReactNode;
}

export function MultiCreateModal({
  isOpen,
  title,
  itemLabel,
  itemLabelPlural,
  placeholder,
  onClose,
  onSave,
  contextInfo,
}: MultiCreateModalProps) {
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
      title={title}
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
            {saving ? 'Saving...' : nameCount > 1 ? `Add ${nameCount} ${itemLabelPlural}` : `Add ${itemLabel}`}
          </button>
        </>
      }
    >
      {contextInfo && <div className="context-info mb-3">{contextInfo}</div>}
      <div className="mb-3">
        <label className="form-label">{itemLabel} Name(s)</label>
        <input
          type="text"
          className="form-control"
          placeholder={placeholder}
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
