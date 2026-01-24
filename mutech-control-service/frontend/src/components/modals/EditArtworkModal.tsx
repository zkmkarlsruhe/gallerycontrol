/**
 * Modal for editing artwork properties including protection rules.
 */

import { useState, useEffect } from 'react';
import { Modal } from '../ui/Modal';
import { ProtectionConfigForm } from '../forms/ProtectionConfigForm';
import type { ProtectionConfig } from '../../types';

interface EditArtworkModalProps {
  isOpen: boolean;
  artwork: {
    id: string;
    name: string;
    enabled: boolean;
    protection_config?: ProtectionConfig | null;
  } | null;
  onClose: () => void;
  onSave: (
    id: string,
    data: { name: string; enabled: boolean; protection_config?: ProtectionConfig | null }
  ) => Promise<void>;
}

export function EditArtworkModal({
  isOpen,
  artwork,
  onClose,
  onSave,
}: EditArtworkModalProps) {
  const [name, setName] = useState('');
  const [enabled, setEnabled] = useState(true);
  const [protectionConfig, setProtectionConfig] = useState<ProtectionConfig | null>(
    null
  );
  const [saving, setSaving] = useState(false);
  const [showProtection, setShowProtection] = useState(false);

  useEffect(() => {
    if (artwork) {
      setName(artwork.name);
      setEnabled(artwork.enabled);
      setProtectionConfig(artwork.protection_config || null);
      setShowProtection(!!artwork.protection_config);
    }
  }, [artwork]);

  if (!artwork) return null;

  const handleSave = async () => {
    if (!name.trim()) return;
    setSaving(true);
    try {
      await onSave(artwork.id, {
        name: name.trim(),
        enabled,
        protection_config: protectionConfig,
      });
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
      size="lg"
      footer={
        <>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={onClose}
          >
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
      {/* Basic Info Section */}
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

      {/* Protection Rules Section */}
      <hr />
      <div className="mb-3">
        <button
          type="button"
          className="btn btn-link p-0 text-decoration-none d-flex align-items-center gap-2"
          onClick={() => setShowProtection(!showProtection)}
        >
          <span
            style={{
              transition: 'transform 0.2s',
              transform: showProtection ? 'rotate(90deg)' : 'rotate(0deg)',
            }}
          >
            &#9654;
          </span>
          <strong>Protection Rules</strong>
          {protectionConfig && (
            <span className="badge bg-info ms-2">Active</span>
          )}
        </button>
        <div className="small text-muted">
          Configure runtime limits to prevent overuse
        </div>
      </div>

      {showProtection && (
        <div className="protection-section p-3 bg-light rounded">
          <ProtectionConfigForm
            value={protectionConfig}
            onChange={setProtectionConfig}
          />
        </div>
      )}
    </Modal>
  );
}
