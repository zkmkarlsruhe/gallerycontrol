// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT
import { useState, useEffect, useCallback } from 'react';
import type { Exhibition } from '../../types';
import { Modal } from '../ui/Modal';

interface EmailConfig {
  recipients: string[];
  subject: string;
  from_address: string;
  smtp_configured: boolean;
}

interface InventoryPreview {
  content: string;
  exhibition_count: number;
  device_count: number;
}

interface EmailInventoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  exhibitions: Exhibition[];
  fetchEmailConfig: () => Promise<EmailConfig>;
  fetchInventoryPreview: (exhibitionIds?: string[], includeDisabled?: boolean) => Promise<InventoryPreview>;
  sendInventoryEmail: (exhibitionIds?: string[], includeDisabled?: boolean) => Promise<{ success: boolean; message: string }>;
  showToast: (message: string, type: 'success' | 'danger' | 'info') => void;
}

export function EmailInventoryModal({
  isOpen,
  onClose,
  exhibitions,
  fetchEmailConfig,
  fetchInventoryPreview,
  sendInventoryEmail,
  showToast,
}: EmailInventoryModalProps) {
  const [config, setConfig] = useState<EmailConfig | null>(null);
  const [selectedExhibitionId, setSelectedExhibitionId] = useState<string>('all');
  const [includeDisabled, setIncludeDisabled] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [preview, setPreview] = useState<InventoryPreview | null>(null);
  const [sending, setSending] = useState(false);
  const [loadingPreview, setLoadingPreview] = useState(false);

  const loadEmailConfig = useCallback(async () => {
    try {
      const data = await fetchEmailConfig();
      setConfig(data);
    } catch {
      showToast('Failed to load email config', 'danger');
    }
  }, [fetchEmailConfig, showToast]);

  // Load email config when modal opens
  useEffect(() => {
    if (isOpen) {
      loadEmailConfig();
      // Reset state
      setShowPreview(false);
      setPreview(null);
      setSelectedExhibitionId('all');
      setIncludeDisabled(false);
    }
  }, [isOpen, loadEmailConfig]);

  const loadPreview = async () => {
    setLoadingPreview(true);
    try {
      const exhibitionIds = selectedExhibitionId === 'all'
        ? undefined
        : [selectedExhibitionId];
      const data = await fetchInventoryPreview(exhibitionIds, includeDisabled);
      setPreview(data);
      setShowPreview(true);
    } catch {
      showToast('Failed to load preview', 'danger');
    } finally {
      setLoadingPreview(false);
    }
  };

  const handleSend = async () => {
    setSending(true);
    try {
      const exhibitionIds = selectedExhibitionId === 'all'
        ? undefined
        : [selectedExhibitionId];
      const result = await sendInventoryEmail(exhibitionIds, includeDisabled);

      if (result.success) {
        showToast(result.message, 'success');
        onClose();
      } else {
        showToast(result.message, 'danger');
      }
    } catch {
      showToast('Failed to send email', 'danger');
    } finally {
      setSending(false);
    }
  };

  // Get enabled exhibitions for the dropdown
  const enabledExhibitions = exhibitions.filter(ex => ex.enabled);

  const smtpConfigured = config?.smtp_configured ?? false;
  const recipients = config?.recipients ?? [];
  const subject = config?.subject ?? '';

  return (
    <Modal
      isOpen={isOpen}
      title="Send Device Inventory"
      onClose={onClose}
      size="lg"
      footer={
        <>
          <button type="button" className="btn btn-secondary btn-sm" onClick={onClose}>
            Close
          </button>
          <button
            type="button"
            className="btn btn-primary btn-sm"
            onClick={handleSend}
            disabled={sending || !smtpConfigured || recipients.length === 0}
          >
            {sending ? 'Sending...' : 'Send Email'}
          </button>
        </>
      }
    >
      {!smtpConfigured && (
        <div className="alert alert-warning mb-3">
          <strong>SMTP not configured.</strong> Set SMTP_HOST environment variable to enable email sending.
        </div>
      )}

      <div className="mb-3">
        <div className="d-flex justify-content-between">
          <span className="text-muted">To:</span>
          <span>{recipients.join(', ') || '(none configured)'}</span>
        </div>
        <div className="d-flex justify-content-between">
          <span className="text-muted">Subject:</span>
          <span>{subject || '(none configured)'}</span>
        </div>
      </div>

      <hr />

      <div className="mb-3">
        <label className="form-label">Exhibitions</label>
        <select
          className="form-select"
          value={selectedExhibitionId}
          onChange={(e) => {
            setSelectedExhibitionId(e.target.value);
            setShowPreview(false);
            setPreview(null);
          }}
        >
          <option value="all">All {includeDisabled ? '' : 'Enabled '}({includeDisabled ? exhibitions.length : enabledExhibitions.length})</option>
          {(includeDisabled ? exhibitions : enabledExhibitions).map(ex => (
            <option key={ex.id} value={ex.id}>{ex.name}{!ex.enabled ? ' (disabled)' : ''}</option>
          ))}
        </select>
      </div>

      <div className="mb-3 form-check">
        <input
          type="checkbox"
          className="form-check-input"
          id="includeDisabled"
          checked={includeDisabled}
          onChange={(e) => {
            setIncludeDisabled(e.target.checked);
            setShowPreview(false);
            setPreview(null);
          }}
        />
        <label className="form-check-label" htmlFor="includeDisabled">
          Include disabled items
        </label>
      </div>

      <div className="mb-3">
        <button
          type="button"
          className="btn btn-outline-secondary btn-sm"
          onClick={() => showPreview ? setShowPreview(false) : loadPreview()}
          disabled={loadingPreview}
        >
          {loadingPreview ? (
            'Loading...'
          ) : showPreview ? (
            <>
              <i className="bi bi-chevron-up me-1"></i>
              Hide Preview
            </>
          ) : (
            <>
              <i className="bi bi-chevron-down me-1"></i>
              Show Preview
            </>
          )}
        </button>
        {preview && showPreview && (
          <span className="ms-2 text-muted small">
            {preview.exhibition_count} exhibition(s), {preview.device_count} device(s)
          </span>
        )}
      </div>

      {showPreview && preview && (
        <div className="preview-container">
          <pre className="preview-content">{preview.content}</pre>
        </div>
      )}

      <style>{`
        .preview-container {
          border: 1px solid #dee2e6;
          border-radius: 4px;
          max-height: 300px;
          overflow-y: auto;
          background: #f8f9fa;
        }
        .preview-content {
          margin: 0;
          padding: 12px;
          font-size: 12px;
          white-space: pre-wrap;
          word-wrap: break-word;
        }
      `}</style>
    </Modal>
  );
}
