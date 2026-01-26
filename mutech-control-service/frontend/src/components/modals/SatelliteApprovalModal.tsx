/**
 * Modal for approving or rejecting pending satellite connections.
 */

import { useState, useEffect } from 'react';
import { Modal } from '../ui/Modal';
import type { PendingSatellite, Satellite } from '../../types';

interface SatelliteApprovalModalProps {
  isOpen: boolean;
  onClose: () => void;
  onApprove: (apiKeyHash: string, name: string) => Promise<void>;
  onReject: (apiKeyHash: string) => Promise<void>;
}

export function SatelliteApprovalModal({
  isOpen,
  onClose,
  onApprove,
  onReject,
}: SatelliteApprovalModalProps) {
  const [pendingSatellites, setPendingSatellites] = useState<PendingSatellite[]>([]);
  const [approvedSatellites, setApprovedSatellites] = useState<Satellite[]>([]);
  const [loading, setLoading] = useState(false);
  const [names, setNames] = useState<Record<string, string>>({});
  const [processing, setProcessing] = useState<string | null>(null);

  // Load satellites when modal opens
  useEffect(() => {
    if (isOpen) {
      loadSatellites();
    }
  }, [isOpen]);

  const loadSatellites = async () => {
    setLoading(true);
    try {
      const [pendingRes, allRes] = await Promise.all([
        fetch('/api/admin/satellites/pending'),
        fetch('/api/admin/satellites'),
      ]);
      const pending = await pendingRes.json();
      const all = await allRes.json();
      setPendingSatellites(pending);
      setApprovedSatellites(all.filter((s: Satellite) => s.status === 'approved'));

      // Initialize names for pending satellites
      const initialNames: Record<string, string> = {};
      pending.forEach((p: PendingSatellite) => {
        initialNames[p.api_key_hash] = p.hostname || 'Satellite';
      });
      setNames(initialNames);
    } catch (err) {
      console.error('Failed to load satellites:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (apiKeyHash: string) => {
    const name = names[apiKeyHash]?.trim();
    if (!name) return;

    setProcessing(apiKeyHash);
    try {
      await onApprove(apiKeyHash, name);
      await loadSatellites();
    } finally {
      setProcessing(null);
    }
  };

  const handleReject = async (apiKeyHash: string) => {
    setProcessing(apiKeyHash);
    try {
      await onReject(apiKeyHash);
      await loadSatellites();
    } finally {
      setProcessing(null);
    }
  };

  const handleRevoke = async (satelliteId: string) => {
    if (!confirm('Revoke this satellite? It will need to be re-approved to connect again.')) {
      return;
    }

    setProcessing(satelliteId);
    try {
      await fetch(`/api/admin/satellites/${satelliteId}`, { method: 'DELETE' });
      await loadSatellites();
    } finally {
      setProcessing(null);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      title="Satellite Management"
      onClose={onClose}
      size="lg"
      footer={
        <button type="button" className="btn btn-secondary btn-sm" onClick={onClose}>
          Close
        </button>
      }
    >
      {loading ? (
        <div className="text-center py-4">
          <div className="spinner-border spinner-border-sm me-2" role="status" />
          Loading satellites...
        </div>
      ) : (
        <>
          {/* Pending Satellites */}
          {pendingSatellites.length > 0 && (
            <div className="mb-4">
              <h6 className="text-warning">
                <i className="bi bi-hourglass-split me-2"></i>
                Pending Approval ({pendingSatellites.length})
              </h6>
              <div className="list-group">
                {pendingSatellites.map((sat) => (
                  <div key={sat.api_key_hash} className="list-group-item">
                    <div className="d-flex justify-content-between align-items-start">
                      <div className="flex-grow-1 me-3">
                        <div className="mb-2">
                          <input
                            type="text"
                            className="form-control form-control-sm"
                            placeholder="Satellite name"
                            value={names[sat.api_key_hash] || ''}
                            onChange={(e) =>
                              setNames({ ...names, [sat.api_key_hash]: e.target.value })
                            }
                            disabled={processing === sat.api_key_hash}
                          />
                        </div>
                        <div className="small text-muted">
                          <span className="me-3">
                            <i className="bi bi-pc-display me-1"></i>
                            {sat.hostname || 'Unknown host'}
                          </span>
                          {sat.version && (
                            <span className="me-3">
                              <i className="bi bi-tag me-1"></i>
                              v{sat.version}
                            </span>
                          )}
                          <span>
                            <i className="bi bi-clock me-1"></i>
                            Connected {new Date(sat.connected_at).toLocaleTimeString()}
                          </span>
                        </div>
                      </div>
                      <div className="d-flex gap-2">
                        <button
                          type="button"
                          className="btn btn-success btn-sm"
                          onClick={() => handleApprove(sat.api_key_hash)}
                          disabled={processing === sat.api_key_hash || !names[sat.api_key_hash]?.trim()}
                        >
                          {processing === sat.api_key_hash ? (
                            <span className="spinner-border spinner-border-sm" />
                          ) : (
                            <>
                              <i className="bi bi-check-lg me-1"></i>
                              Approve
                            </>
                          )}
                        </button>
                        <button
                          type="button"
                          className="btn btn-outline-danger btn-sm"
                          onClick={() => handleReject(sat.api_key_hash)}
                          disabled={processing === sat.api_key_hash}
                        >
                          <i className="bi bi-x-lg"></i>
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Approved Satellites */}
          <div>
            <h6>
              <i className="bi bi-broadcast me-2"></i>
              Approved Satellites ({approvedSatellites.length})
            </h6>
            {approvedSatellites.length === 0 ? (
              <div className="text-muted small py-3">
                No satellites have been approved yet. When a satellite connects, it will appear
                in the pending section above.
              </div>
            ) : (
              <div className="list-group">
                {approvedSatellites.map((sat) => (
                  <div key={sat.id} className="list-group-item">
                    <div className="d-flex justify-content-between align-items-center">
                      <div>
                        <div className="d-flex align-items-center">
                          <span
                            className={`badge me-2 ${
                              sat.is_connected ? 'bg-success' : 'bg-secondary'
                            }`}
                          >
                            {sat.is_connected ? 'Online' : 'Offline'}
                          </span>
                          <strong>{sat.name}</strong>
                        </div>
                        <div className="small text-muted mt-1">
                          {sat.hostname && (
                            <span className="me-3">
                              <i className="bi bi-pc-display me-1"></i>
                              {sat.hostname}
                            </span>
                          )}
                          {sat.version && (
                            <span className="me-3">
                              <i className="bi bi-tag me-1"></i>
                              v{sat.version}
                            </span>
                          )}
                          {sat.last_seen_at && (
                            <span>
                              <i className="bi bi-clock me-1"></i>
                              Last seen {new Date(sat.last_seen_at).toLocaleString()}
                            </span>
                          )}
                        </div>
                      </div>
                      <button
                        type="button"
                        className="btn btn-outline-danger btn-sm"
                        onClick={() => handleRevoke(sat.id)}
                        disabled={processing === sat.id}
                        title="Revoke satellite"
                      >
                        {processing === sat.id ? (
                          <span className="spinner-border spinner-border-sm" />
                        ) : (
                          <i className="bi bi-trash"></i>
                        )}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </Modal>
  );
}
