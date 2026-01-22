import { useState, useEffect, useCallback } from 'react';
import { Modal } from '../ui/Modal';

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

function formatTimeAgo(isoString: string | null): string {
  if (!isoString) return 'Never';
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);

  if (diffSec < 60) return `${diffSec}s ago`;
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  return date.toLocaleDateString();
}

function formatTimeUntil(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = date.getTime() - now.getTime();
  const diffSec = Math.floor(diffMs / 1000);

  if (diffSec <= 0) return 'now';
  if (diffSec < 60) return `in ${diffSec}s`;
  if (diffSec < 3600) return `in ${Math.floor(diffSec / 60)}m`;
  return `in ${Math.floor(diffSec / 3600)}h`;
}

export function AdminModal({ isOpen, onClose, showToast }: AdminModalProps) {
  const [status, setStatus] = useState<SchedulerStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [triggeringAll, setTriggeringAll] = useState(false);
  const [triggeringTask, setTriggeringTask] = useState<string | null>(null);
  const [resettingTask, setResettingTask] = useState<string | null>(null);

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
      fetchStatus().finally(() => setLoading(false));

      // Auto-refresh every 5 seconds while open
      const interval = setInterval(fetchStatus, 5000);
      return () => clearInterval(interval);
    }
  }, [isOpen, fetchStatus]);

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
    } catch (err) {
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
        const error = await response.json();
        throw new Error(error.detail || 'Failed to trigger task');
      }
      showToast(`Triggered: ${taskName}`, 'success');
      setTimeout(fetchStatus, 500);
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Failed to trigger task', 'danger');
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
    } catch (err) {
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
