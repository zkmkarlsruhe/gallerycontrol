// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT
import { MultiCreateModal } from './MultiCreateModal';

interface AddExhibitionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (name: string) => Promise<void>;
}

export function AddExhibitionModal({ isOpen, onClose, onSave }: AddExhibitionModalProps) {
  return (
    <MultiCreateModal
      isOpen={isOpen}
      title="Add Exhibition"
      itemLabel="Exhibition"
      itemLabelPlural="Exhibitions"
      placeholder="e.g. Exhibition 1, Exhibition 2, Exhibition 3"
      onClose={onClose}
      onSave={onSave}
    />
  );
}
