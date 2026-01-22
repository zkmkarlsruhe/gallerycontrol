import { EditNamedEntityModal } from './EditNamedEntityModal';

interface EditExhibitionModalProps {
  isOpen: boolean;
  exhibition: {
    id: string;
    name: string;
    enabled: boolean;
  } | null;
  onClose: () => void;
  onSave: (id: string, data: { name: string; enabled: boolean }) => Promise<void>;
}

export function EditExhibitionModal({
  isOpen,
  exhibition,
  onClose,
  onSave,
}: EditExhibitionModalProps) {
  return (
    <EditNamedEntityModal
      isOpen={isOpen}
      entity={exhibition}
      entityLabel="Exhibition"
      enabledInfoText="Exhibition is active. All artworks and devices will be controlled normally."
      disabledInfoText="Exhibition is disabled. All artworks and devices within will be excluded from control and polling."
      onClose={onClose}
      onSave={onSave}
    />
  );
}
