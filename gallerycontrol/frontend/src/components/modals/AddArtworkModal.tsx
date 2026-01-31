// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT
import { useCallback } from 'react';
import { MultiCreateModal } from './MultiCreateModal';

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
  // Wrap onSave to include exhibitionId
  const handleSave = useCallback(
    (name: string) => onSave(exhibitionId, name),
    [exhibitionId, onSave]
  );

  return (
    <MultiCreateModal
      isOpen={isOpen}
      title="Add Artwork"
      itemLabel="Artwork"
      itemLabelPlural="Artworks"
      placeholder="e.g. Raum 1, Raum 2, Raum 3"
      onClose={onClose}
      onSave={handleSave}
      contextInfo={
        <>
          <strong>Adding artwork to:</strong>
          <div className="mt-2">
            Exhibition: <strong>{exhibitionName}</strong>
          </div>
        </>
      }
    />
  );
}
