// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT
import { Modal } from '../ui/Modal';
import { InputWithCopyButton } from '../ui/InputWithCopyButton';

interface DisplayLinksModalProps {
  isOpen: boolean;
  onClose: () => void;
  artworkId: string;
  artworkName: string;
  baseUrl?: string;
}

// Generate a URL-safe slug from artwork name
function generateSlug(name: string): string {
  return name
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '') // Remove diacritics
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
}

export function DisplayLinksModal({
  isOpen,
  onClose,
  artworkId,
  artworkName,
  baseUrl = window.location.origin,
}: DisplayLinksModalProps) {
  const suggestedSlug = generateSlug(artworkName);
  const displayUrl = `${baseUrl}/display/${suggestedSlug}`;
  const statusUrl = `${baseUrl}/display/${suggestedSlug}/status`;

  return (
    <Modal
      isOpen={isOpen}
      title="Display Links"
      onClose={onClose}
      size="lg"
    >
      <div className="display-links-content">
        <p className="text-muted mb-4">
          Configure kiosk displays for <strong>{artworkName}</strong>.
        </p>

        <div className="alert alert-warning small mb-4">
          <i className="bi bi-exclamation-triangle me-2"></i>
          <strong>Setup required:</strong> Create the config folder before these URLs will work.
        </div>

        <div className="mb-4">
          <InputWithCopyButton
            label="Display Page URL (example)"
            value={displayUrl}
          />
          <small className="text-muted">
            Full-screen HTML page for visitor kiosks. The slug (<code>{suggestedSlug}</code>) must match your config folder name.
          </small>
        </div>

        <div className="mb-4">
          <InputWithCopyButton
            label="Status API URL (example)"
            value={statusUrl}
          />
          <small className="text-muted">
            JSON endpoint for custom integrations (polled every 2 seconds).
          </small>
        </div>

        <hr />

        <div className="mb-3">
          <h6 className="text-muted">Setup Instructions</h6>
          <ol className="small text-muted mb-2">
            <li>Create a folder: <code>display_assets/artworks/{suggestedSlug}/</code></li>
            <li>Create <code>config.yaml</code> in that folder</li>
            <li>Set <code>artwork_uuid</code> in the config to link it to this artwork</li>
          </ol>
        </div>

        <div className="mb-3">
          <h6 className="text-muted">Artwork UUID</h6>
          <InputWithCopyButton
            label=""
            value={artworkId}
          />
          <small className="text-muted">
            Use this UUID in your <code>config.yaml</code> file.
          </small>
        </div>

        <div className="mb-3">
          <h6 className="text-muted">Example config.yaml</h6>
          <pre className="bg-dark text-light p-2 rounded small" style={{ fontSize: '0.75rem' }}>
{`artwork_uuid: "${artworkId}"
template: mack-style
chart_type: donut
texts:
  artwork_name: "${artworkName}"
  info_de: "Information auf Deutsch"
  info_en: "Information in English"
  warning_de: "Pause - bitte warten"
  warning_en: "Break - please wait"`}
          </pre>
        </div>

        <div className="alert alert-info small mb-0">
          <i className="bi bi-info-circle me-2"></i>
          Templates: <code>mack-style</code>, <code>chart-only</code>,{' '}
          <code>fullscreen-countdown</code>, <code>progress-bar</code>,{' '}
          <code>info-panel</code>, <code>gauge</code>
        </div>
      </div>
    </Modal>
  );
}
