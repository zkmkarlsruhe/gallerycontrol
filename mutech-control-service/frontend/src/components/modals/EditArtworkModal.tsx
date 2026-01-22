import { EditNamedEntityModal } from './EditNamedEntityModal';

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
  return (
    <EditNamedEntityModal
      isOpen={isOpen}
      entity={artwork}
      entityLabel="Artwork"
      enabledInfoText="Artwork is active. All devices will be controlled normally."
      disabledInfoText="Artwork is disabled. All devices within will be excluded from control and polling."
      onClose={onClose}
      onSave={onSave}
    />
  );
}
