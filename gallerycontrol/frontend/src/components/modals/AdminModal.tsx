// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT
import { useState, useEffect, useCallback } from 'react';
import { Modal } from '../ui/Modal';
import { formatTimeAgo, formatTimeUntil } from '../../utils/dateFormat';
import type { Satellite, PendingSatellite } from '../../types';

const API_BASE = import.meta.env.VITE_API_BASE || '';

interface TaskStatus {
  enabled: boolean;
  interval_seconds: number;
  last_run_at: string | null;
  next_run_at: string;
  fail_count: number;
  circuit_open: boolean;
  is_running: boolean;
  last_error: string | null;
  last_result: Record<string, unknown> | null;
}

interface SchedulerStatus {
  enabled: boolean;
  running: boolean;
  check_interval_seconds: number;
  tasks: Record<string, TaskStatus>;
}

interface AdminModalProps {
  isOpen: boolean;
  onClose: () => void;
  showToast: (message: string, type: 'success' | 'danger' | 'info') => void;
}

export function AdminModal({ isOpen, onClose, showToast }: AdminModalProps) {
  const [status, setStatus] = useState<SchedulerStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [triggeringAll, setTriggeringAll] = useState(false);
  const [triggeringTask, setTriggeringTask] = useState<string | null>(null);
  const [resettingTask, setResettingTask] = useState<string | null>(null);

  // Satellite state
  const [satellites, setSatellites] = useState<Satellite[]>([]);
  const [pendingSatellites, setPendingSatellites] = useState<PendingSatellite[]>([]);
  const [approvingHash, setApprovingHash] = useState<string | null>(null);
  const [approvalName, setApprovalName] = useState('');
  const [rejectingHash, setRejectingHash] = useState<string | null>(null);
  const [revokingId, setRevokingId] = useState<string | null>(null);

  const fetchSatellites = useCallback(async () => {
    try {
      const [satellitesRes, pendingRes] = await Promise.all([
        fetch(`${API_BASE}/api/admin/satellites`),
        fetch(`${API_BASE}/api/admin/satellites/pending`),
      ]);
      if (satellitesRes.ok) {
        setSatellites(await satellitesRes.json());
      }
      if (pendingRes.ok) {
        setPendingSatellites(await pendingRes.json());
      }
    } catch (err) {
      console.error('Failed to fetch satellites:', err);
    }
  }, []);

  const handleApproveSatellite = async (apiKeyHash: string, name: string) => {
    if (!name.trim()) {
      showToast('Please enter a name for the satellite', 'danger');
      return;
    }
    setApprovingHash(apiKeyHash);
    try {
      const response = await fetch(`${API_BASE}/api/admin/satellites/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key_hash: apiKeyHash, name: name.trim() }),
      });
      if (!response.ok) throw new Error('Failed to approve satellite');
      showToast(`Satellite "${name}" approved`, 'success');
      setApprovalName('');
      fetchSatellites();
    } catch {
      showToast('Failed to approve satellite', 'danger');
    } finally {
      setApprovingHash(null);
    }
  };

  const handleRejectSatellite = async (apiKeyHash: string) => {
    setRejectingHash(apiKeyHash);
    try {
      const response = await fetch(`${API_BASE}/api/admin/satellites/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key_hash: apiKeyHash }),
      });
      if (!response.ok) throw new Error('Failed to reject satellite');
      showToast('Satellite rejected', 'success');
      fetchSatellites();
    } catch {
      showToast('Failed to reject satellite', 'danger');
    } finally {
      setRejectingHash(null);
    }
  };

  const handleRevokeSatellite = async (id: string, name: string) => {
    setRevokingId(id);
    try {
      const response = await fetch(`${API_BASE}/api/admin/satellites/${id}`, {
        method: 'DELETE',
      });
      if (!response.ok) throw new Error('Failed to revoke satellite');
      showToast(`Satellite "${name}" revoked`, 'success');
      fetchSatellites();
    } catch {
      showToast('Failed to revoke satellite', 'danger');
    } finally {
      setRevokingId(null);
    }
  };

  const fetchStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/admin/scheduler/status`);
      if (!response.ok) throw new Error('Failed to fetch status');
      const data = await response.json();
      setStatus(data);
    } catch (err) {
      console.error('Failed to fetch scheduler status:', err);
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      setLoading(true);
      Promise.all([fetchStatus(), fetchSatellites()]).finally(() => setLoading(false));

      // Auto-refresh every 5 seconds while open
      const interval = setInterval(() => {
        fetchStatus();
        fetchSatellites();
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [isOpen, fetchStatus, fetchSatellites]);

  const handleTriggerAll = async () => {
    setTriggeringAll(true);
    try {
      const response = await fetch(`${API_BASE}/api/admin/scheduler/trigger-all`, {
        method: 'POST',
      });
      if (!response.ok) throw new Error('Failed to trigger tasks');
      const data = await response.json();

      if (data.triggered.length > 0) {
        showToast(`Triggered: ${data.triggered.join(', ')}`, 'success');
      }
      if (data.skipped.length > 0) {
        showToast(`Skipped (running/circuit open): ${data.skipped.join(', ')}`, 'info');
      }

      // Refresh status
      setTimeout(fetchStatus, 500);
    } catch {
      showToast('Failed to trigger tasks', 'danger');
    } finally {
      setTriggeringAll(false);
    }
  };

  const handleTriggerTask = async (taskName: string) => {
    setTriggeringTask(taskName);
    try {
      const response = await fetch(`${API_BASE}/api/admin/scheduler/trigger/${taskName}`, {
        method: 'POST',
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to trigger task');
      }
      showToast(`Triggered: ${taskName}`, 'success');
      setTimeout(fetchStatus, 500);
    } catch (error) {
      showToast(error instanceof Error ? error.message : 'Failed to trigger task', 'danger');
    } finally {
      setTriggeringTask(null);
    }
  };

  const handleResetCircuit = async (taskName: string) => {
    setResettingTask(taskName);
    try {
      const response = await fetch(`${API_BASE}/api/admin/scheduler/reset/${taskName}`, {
        method: 'POST',
      });
      if (!response.ok) throw new Error('Failed to reset circuit');
      showToast(`Reset circuit breaker for: ${taskName}`, 'success');
      setTimeout(fetchStatus, 500);
    } catch {
      showToast('Failed to reset circuit', 'danger');
    } finally {
      setResettingTask(null);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      title="Admin Panel"
      onClose={onClose}
      size="lg"
      footer={
        <button className="btn btn-secondary btn-sm" onClick={onClose}>
          Close
        </button>
      }
    >
      <div className="admin-modal">
        {/* Satellites Section */}
        <div className="admin-section mb-4">
          <h6 className="admin-section-title">
            <i className="bi bi-broadcast me-2"></i>
            Satellites
            {pendingSatellites.length > 0 && (
              <span className="badge bg-warning text-dark ms-2">{pendingSatellites.length} pending</span>
            )}
          </h6>

          {/* Pending Satellites */}
          {pendingSatellites.length > 0 && (
            <div className="mb-3">
              <small className="text-muted d-block mb-2">Pending Approval</small>
              {pendingSatellites.map((pending) => (
                <div key={pending.api_key_hash} className="admin-task-card border-warning">
                  <div className="d-flex align-items-center justify-content-between mb-2">
                    <div>
                      <strong>{pending.hostname || 'Unknown'}</strong>
                      <small className="text-muted ms-2">v{pending.version}</small>
                    </div>
                    <span className="badge bg-warning text-dark">Pending</span>
                  </div>
                  <div className="d-flex gap-2 align-items-center">
                    <input
                      type="text"
                      className="form-control form-control-sm"
                      placeholder="Enter satellite name..."
                      value={approvingHash === pending.api_key_hash ? approvalName : ''}
                      onChange={(e) => {
                        setApprovingHash(pending.api_key_hash);
                        setApprovalName(e.target.value);
                      }}
                      onFocus={() => setApprovingHash(pending.api_key_hash)}
                    />
                    <button
                      className="btn btn-success btn-sm"
                      onClick={() => handleApproveSatellite(pending.api_key_hash, approvalName)}
                      disabled={approvingHash === pending.api_key_hash && !approvalName.trim()}
                    >
                      <i className="bi bi-check-lg"></i>
                    </button>
                    <button
                      className="btn btn-outline-danger btn-sm"
                      onClick={() => handleRejectSatellite(pending.api_key_hash)}
                      disabled={rejectingHash === pending.api_key_hash}
                    >
                      {rejectingHash === pending.api_key_hash ? (
                        <span className="spinner-border spinner-border-sm"></span>
                      ) : (
                        <i className="bi bi-x-lg"></i>
                      )}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Approved Satellites */}
          {satellites.length > 0 ? (
            <div>
              <small className="text-muted d-block mb-2">Approved Satellites</small>
              {satellites.map((satellite) => (
                <div key={satellite.id} className="admin-task-card">
                  <div className="d-flex align-items-center justify-content-between">
                    <div>
                      <strong>{satellite.name}</strong>
                      <small className="text-muted ms-2">({satellite.hostname})</small>
                    </div>
                    <div className="d-flex align-items-center gap-2">
                      <span className={`badge ${satellite.is_connected ? 'bg-success' : 'bg-secondary'}`}>
                        {satellite.is_connected ? 'Connected' : 'Offline'}
                      </span>
                      <button
                        className="btn btn-outline-danger btn-sm"
                        onClick={() => handleRevokeSatellite(satellite.id, satellite.name)}
                        disabled={revokingId === satellite.id}
                        title="Revoke satellite"
                      >
                        {revokingId === satellite.id ? (
                          <span className="spinner-border spinner-border-sm"></span>
                        ) : (
                          <i className="bi bi-trash"></i>
                        )}
                      </button>
                    </div>
                  </div>
                  <div className="admin-task-details mt-2">
                    <div className="admin-task-detail">
                      <span className="text-muted">Version:</span>
                      <span>{satellite.version || 'Unknown'}</span>
                    </div>
                    <div className="admin-task-detail">
                      <span className="text-muted">Last seen:</span>
                      <span>{satellite.last_seen_at ? formatTimeAgo(satellite.last_seen_at) : 'Never'}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : pendingSatellites.length === 0 ? (
            <div className="text-muted text-center py-3">
              <i className="bi bi-broadcast me-2"></i>
              No satellites configured
            </div>
          ) : null}
        </div>

        {/* Trigger All Section */}
        <div className="admin-section">
          <h6 className="admin-section-title">
            <i className="bi bi-lightning-charge me-2"></i>
            Quick Actions
          </h6>
          <button
            className="btn btn-primary w-100"
            onClick={handleTriggerAll}
            disabled={triggeringAll || !status?.running}
          >
            {triggeringAll ? (
              <>
                <span className="spinner-border spinner-border-sm me-2"></span>
                Triggering...
              </>
            ) : (
              <>
                <i className="bi bi-play-fill me-2"></i>
                Run All Scheduled Tasks Now
              </>
            )}
          </button>
          <small className="text-muted d-block mt-1">
            Immediately runs asset linking and log cleanup tasks
          </small>
        </div>

        {/* Scheduler Status */}
        <div className="admin-section mt-4">
          <h6 className="admin-section-title">
            <i className="bi bi-clock-history me-2"></i>
            Task Scheduler Status
          </h6>

          {loading && !status ? (
            <div className="text-center py-3">
              <span className="spinner-border spinner-border-sm"></span>
              <span className="ms-2">Loading...</span>
            </div>
          ) : status ? (
            <>
              <div className="d-flex align-items-center gap-2 mb-3">
                <span className={`badge ${status.running ? 'bg-success' : 'bg-secondary'}`}>
                  {status.running ? 'Running' : 'Stopped'}
                </span>
                <small className="text-muted">
                  Check interval: {status.check_interval_seconds}s
                </small>
              </div>

              {Object.entries(status.tasks).map(([taskName, task]) => (
                <div key={taskName} className="admin-task-card">
                  <div className="admin-task-header">
                    <div className="admin-task-name">
                      <strong>{taskName}</strong>
                      {task.is_running && (
                        <span className="badge bg-info ms-2">
                          <span className="spinner-border spinner-border-sm me-1" style={{ width: '0.7em', height: '0.7em' }}></span>
                          Running
                        </span>
                      )}
                      {task.circuit_open && (
                        <span className="badge bg-danger ms-2">Circuit Open</span>
                      )}
                    </div>
                    <div className="admin-task-actions">
                      {task.circuit_open ? (
                        <button
                          className="btn btn-sm btn-warning"
                          onClick={() => handleResetCircuit(taskName)}
                          disabled={resettingTask === taskName}
                        >
                          {resettingTask === taskName ? (
                            <span className="spinner-border spinner-border-sm"></span>
                          ) : (
                            <>
                              <i className="bi bi-arrow-counterclockwise me-1"></i>
                              Reset
                            </>
                          )}
                        </button>
                      ) : (
                        <button
                          className="btn btn-sm btn-outline-primary"
                          onClick={() => handleTriggerTask(taskName)}
                          disabled={triggeringTask === taskName || task.is_running}
                        >
                          {triggeringTask === taskName ? (
                            <span className="spinner-border spinner-border-sm"></span>
                          ) : (
                            <>
                              <i className="bi bi-play me-1"></i>
                              Run
                            </>
                          )}
                        </button>
                      )}
                    </div>
                  </div>

                  <div className="admin-task-details">
                    <div className="admin-task-detail">
                      <span className="text-muted">Last run:</span>
                      <span>{formatTimeAgo(task.last_run_at)}</span>
                    </div>
                    <div className="admin-task-detail">
                      <span className="text-muted">Next run:</span>
                      <span>{formatTimeUntil(task.next_run_at)}</span>
                    </div>
                    <div className="admin-task-detail">
                      <span className="text-muted">Interval:</span>
                      <span>{Math.round(task.interval_seconds / 60)}m</span>
                    </div>
                    {task.fail_count > 0 && (
                      <div className="admin-task-detail">
                        <span className="text-muted">Failures:</span>
                        <span className="text-danger">{task.fail_count}</span>
                      </div>
                    )}
                  </div>

                  {/* Last Result or Error */}
                  {task.last_error && (
                    <div className="admin-task-error mt-2">
                      <i className="bi bi-exclamation-triangle text-danger me-1"></i>
                      <small className="text-danger">{task.last_error}</small>
                    </div>
                  )}
                  {task.last_result && !task.last_error && (
                    <div className="admin-task-result mt-2">
                      <small className="text-muted">
                        Last result: {JSON.stringify(task.last_result)}
                      </small>
                    </div>
                  )}
                </div>
              ))}
            </>
          ) : (
            <div className="text-muted">Scheduler not available</div>
          )}
        </div>
      </div>
    </Modal>
  );
}
