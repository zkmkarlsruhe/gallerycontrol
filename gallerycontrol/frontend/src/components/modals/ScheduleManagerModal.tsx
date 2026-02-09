// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT
import { useState, useEffect, useCallback } from 'react';
import { Modal } from '../ui/Modal';
import { ConfirmButton } from '../ui/ConfirmButton';
import { formatDateTime, formatCronExpression } from '../../utils/dateFormat';

const API_BASE = import.meta.env.VITE_API_BASE || '';

interface ScheduledJob {
  id: string;
  name: string;
  job_type: string;
  cron_expression: string | null;
  run_once: boolean;
  target_type: string;
  target_id: string | null;
  target_device_id: string | null;
  target_device_name: string | null;
  action_type: string | null;
  action_name: string | null;
  enabled: boolean;
  last_run_at: string | null;
  last_success: boolean | null;
  last_error: string | null;
  next_run_at: string | null;
  executed_at: string | null;
}

interface DeviceAction {
  name: string;
}

interface ScheduleManagerModalProps {
  isOpen: boolean;
  onClose: () => void;
  targetType: 'device' | 'artwork' | 'exhibition' | 'all';
  targetId: string;
  targetName: string;
  availableActions?: DeviceAction[];
  showToast: (message: string, type: 'success' | 'danger' | 'info') => void;
}

export function ScheduleManagerModal({
  isOpen,
  onClose,
  targetType,
  targetId,
  targetName,
  availableActions = [],
  showToast,
}: ScheduleManagerModalProps) {
  const [jobs, setJobs] = useState<ScheduledJob[]>([]);
  const [loading, setLoading] = useState(false);
  const [editingJob, setEditingJob] = useState<ScheduledJob | null>(null);

  // New schedule form state
  const [scheduleType, setScheduleType] = useState<'cron' | 'once'>('cron');
  const [actionType, setActionType] = useState<'on' | 'off' | 'action'>('off');
  const [actionName, setActionName] = useState('');
  const [cronExpression, setCronExpression] = useState('0 18 * * *');
  const [cronPreview, setCronPreview] = useState<string[]>([]);
  const [runAtDate, setRunAtDate] = useState('');
  const [runAtTime, setRunAtTime] = useState('18:00');
  const [scheduleName, setScheduleName] = useState('');
  const [saving, setSaving] = useState(false);

  const fetchJobs = useCallback(async () => {
    setLoading(true);
    try {
      // Build query params based on target type
      let url = `${API_BASE}/api/admin/scheduled-jobs?target_type=${targetType}`;
      if (targetType === 'device') {
        url += `&target_device_id=${targetId}`;
      } else if (targetType !== 'all') {
        url += `&target_id=${targetId}`;
      }

      const response = await fetch(url);
      if (!response.ok) throw new Error('Failed to fetch schedules');
      const data = await response.json();
      setJobs(data);
    } catch (err) {
      console.error('Failed to fetch schedules:', err);
      showToast('Failed to load schedules', 'danger');
    } finally {
      setLoading(false);
    }
  }, [targetType, targetId, showToast]);

  const fetchCronPreview = useCallback(async () => {
    if (!cronExpression.trim()) {
      setCronPreview([]);
      return;
    }
    try {
      const response = await fetch(
        `${API_BASE}/api/admin/scheduled-jobs/cron/preview?cron_expression=${encodeURIComponent(cronExpression)}&count=3`
      );
      if (response.ok) {
        const data = await response.json();
        setCronPreview(data.next_runs || []);
      } else {
        setCronPreview([]);
      }
    } catch {
      setCronPreview([]);
    }
  }, [cronExpression]);

  useEffect(() => {
    if (isOpen) {
      fetchJobs();
      // Set default date to tomorrow
      const tomorrow = new Date();
      tomorrow.setDate(tomorrow.getDate() + 1);
      setRunAtDate(tomorrow.toISOString().split('T')[0]);
    }
  }, [isOpen, fetchJobs]);

  useEffect(() => {
    if (scheduleType === 'cron') {
      const timer = setTimeout(fetchCronPreview, 500);
      return () => clearTimeout(timer);
    }
  }, [cronExpression, scheduleType, fetchCronPreview]);

  const handleDeleteJob = async (jobId: string) => {
    try {
      const response = await fetch(`${API_BASE}/api/admin/scheduled-jobs/${jobId}`, {
        method: 'DELETE',
      });
      if (!response.ok) throw new Error('Failed to delete');
      showToast('Schedule deleted', 'success');
      fetchJobs();
    } catch (err) {
      showToast('Failed to delete schedule', 'danger');
    }
  };

  const handleToggleJob = async (job: ScheduledJob) => {
    try {
      const response = await fetch(`${API_BASE}/api/admin/scheduled-jobs/${job.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !job.enabled }),
      });
      if (!response.ok) throw new Error('Failed to update');
      showToast(`Schedule ${job.enabled ? 'disabled' : 'enabled'}`, 'success');
      fetchJobs();
    } catch (err) {
      showToast('Failed to update schedule', 'danger');
    }
  };

  const handleSaveSchedule = async () => {
    setSaving(true);
    try {
      // Generate a name if not provided
      const name = scheduleName.trim() || `${actionType.toUpperCase()} ${targetName}`;

      if (scheduleType === 'once') {
        // One-shot job
        if (!runAtDate || !runAtTime) {
          showToast('Please select date and time', 'danger');
          setSaving(false);
          return;
        }
        const runAt = `${runAtDate}T${runAtTime}:00`;

        const response = await fetch(`${API_BASE}/api/admin/scheduled-jobs/once`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name,
            run_at: runAt,
            target_type: targetType,
            target_id: targetType === 'all' ? '' : targetId,
            action_type: actionType === 'action' ? 'action' : actionType,
          }),
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail || 'Failed to create schedule');
        }
      } else {
        // Recurring job (cron)
        if (!cronExpression.trim()) {
          showToast('Please enter a cron expression', 'danger');
          setSaving(false);
          return;
        }

        const payload: Record<string, unknown> = {
          name,
          cron_expression: cronExpression,
          job_type: 'device',
          target_type: targetType,
          action_type: actionType === 'action' ? 'action' : actionType,
          enabled: true,
        };

        if (targetType === 'device') {
          payload.target_device_id = targetId;
        } else if (targetType !== 'all') {
          payload.target_id = targetId;
        }

        if (actionType === 'action' && actionName) {
          payload.action_name = actionName;
        }

        const response = await fetch(`${API_BASE}/api/admin/scheduled-jobs`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail || 'Failed to create schedule');
        }
      }

      showToast('Schedule created', 'success');
      setScheduleName('');
      fetchJobs();
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Failed to create schedule', 'danger');
    } finally {
      setSaving(false);
    }
  };

  const handleUpdateJob = async () => {
    if (!editingJob) return;
    setSaving(true);
    try {
      const payload: Record<string, unknown> = {
        name: scheduleName.trim() || editingJob.name,
        enabled: editingJob.enabled,
      };

      if (!editingJob.run_once) {
        payload.cron_expression = cronExpression;
        payload.action_type = actionType === 'action' ? 'action' : actionType;
        if (actionType === 'action' && actionName) {
          payload.action_name = actionName;
        }
      }

      const response = await fetch(`${API_BASE}/api/admin/scheduled-jobs/${editingJob.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to update schedule');
      }

      showToast('Schedule updated', 'success');
      setEditingJob(null);
      setScheduleName('');
      setCronExpression('0 18 * * *');
      setActionType('off');
      fetchJobs();
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Failed to update schedule', 'danger');
    } finally {
      setSaving(false);
    }
  };

  const startEditing = (job: ScheduledJob) => {
    setEditingJob(job);
    setScheduleName(job.name);
    if (job.cron_expression) {
      setCronExpression(job.cron_expression);
    }
    if (job.action_type) {
      setActionType(job.action_type as 'on' | 'off' | 'action');
    }
    if (job.action_name) {
      setActionName(job.action_name);
    }
  };

  const cancelEditing = () => {
    setEditingJob(null);
    setScheduleName('');
    setCronExpression('0 18 * * *');
    setActionType('off');
    setActionName('');
  };

  // Filter to only show device jobs (not system jobs)
  const deviceJobs = jobs.filter(j => j.job_type === 'device');
  const cronJobs = deviceJobs.filter(j => !j.run_once);
  const onceJobs = deviceJobs.filter(j => j.run_once);

  return (
    <Modal
      isOpen={isOpen}
      title={`Schedules for "${targetName}"`}
      onClose={onClose}
      size="lg"
      footer={
        <>
          <button className="btn btn-secondary btn-sm" onClick={editingJob ? cancelEditing : onClose}>
            Close
          </button>
          {editingJob ? (
            <button
              className="btn btn-primary btn-sm"
              onClick={handleUpdateJob}
              disabled={saving}
            >
              {saving ? 'Saving...' : 'Save Changes'}
            </button>
          ) : (
            <button
              className="btn btn-primary btn-sm"
              onClick={handleSaveSchedule}
              disabled={saving}
            >
              {saving ? 'Creating...' : (
                <>
                  <i className="bi bi-plus-lg me-1"></i>
                  Add Schedule
                </>
              )}
            </button>
          )}
        </>
      }
    >
      <div className="schedule-manager-modal">
        {/* Existing Schedules */}
        <div className="schedule-section">
          <h6 className="schedule-section-title">
            <i className="bi bi-clock-history me-2"></i>
            Existing Schedules
          </h6>

          {loading ? (
            <div className="text-center py-3">
              <span className="spinner-border spinner-border-sm"></span>
              <span className="ms-2">Loading...</span>
            </div>
          ) : deviceJobs.length === 0 ? (
            <div className="text-muted text-center py-3">
              No schedules configured
            </div>
          ) : (
            <div className="schedule-list">
              {/* Recurring jobs */}
              {cronJobs.map(job => (
                <div key={job.id} className={`schedule-card ${!job.enabled ? 'disabled' : ''}`}>
                  <div className="schedule-card-header">
                    <div className="schedule-card-info">
                      <span className="schedule-icon">
                        <i className="bi bi-arrow-repeat"></i>
                      </span>
                      <div className="schedule-details">
                        <span className="schedule-name">{job.name}</span>
                        <span className="schedule-meta">
                          {formatCronExpression(job.cron_expression || '')}
                          <code className="ms-2">{job.cron_expression}</code>
                        </span>
                      </div>
                    </div>
                    <div className="schedule-card-actions">
                      <button
                        className={`btn btn-sm ${job.enabled ? 'btn-outline-secondary' : 'btn-outline-success'}`}
                        onClick={() => handleToggleJob(job)}
                        title={job.enabled ? 'Disable' : 'Enable'}
                      >
                        <i className={`bi ${job.enabled ? 'bi-pause' : 'bi-play'}`}></i>
                      </button>
                      {!job.run_once && (
                        <button
                          className="btn btn-sm btn-outline-primary"
                          onClick={() => startEditing(job)}
                          title="Edit"
                        >
                          <i className="bi bi-pencil"></i>
                        </button>
                      )}
                      <ConfirmButton
                        className="btn btn-sm btn-outline-danger"
                        onConfirm={() => handleDeleteJob(job.id)}
                        confirmText="Delete?"
                      >
                        <i className="bi bi-trash"></i>
                      </ConfirmButton>
                    </div>
                  </div>
                  {job.next_run_at && (
                    <div className="schedule-next-run">
                      Next: {formatDateTime(job.next_run_at)}
                    </div>
                  )}
                </div>
              ))}

              {/* One-shot jobs */}
              {onceJobs.map(job => (
                <div key={job.id} className={`schedule-card one-shot ${!job.enabled ? 'disabled' : ''} ${job.executed_at ? 'executed' : ''}`}>
                  <div className="schedule-card-header">
                    <div className="schedule-card-info">
                      <span className="schedule-icon">
                        <i className="bi bi-calendar-event"></i>
                      </span>
                      <div className="schedule-details">
                        <span className="schedule-name">{job.name}</span>
                        <span className="schedule-meta">
                          {job.executed_at ? (
                            <>Executed: {formatDateTime(job.executed_at)}</>
                          ) : (
                            <>Scheduled: {formatDateTime(job.next_run_at)}</>
                          )}
                        </span>
                      </div>
                    </div>
                    <div className="schedule-card-actions">
                      <ConfirmButton
                        className="btn btn-sm btn-outline-danger"
                        onConfirm={() => handleDeleteJob(job.id)}
                        confirmText="Delete?"
                      >
                        <i className="bi bi-trash"></i>
                      </ConfirmButton>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <hr />

        {/* Add/Edit Schedule Form */}
        <div className="schedule-section">
          <h6 className="schedule-section-title">
            <i className={`bi ${editingJob ? 'bi-pencil-square' : 'bi-plus-circle'} me-2`}></i>
            {editingJob ? 'Edit Schedule' : 'Add New Schedule'}
          </h6>

          {/* Name */}
          <div className="mb-3">
            <label className="form-label">Name (optional)</label>
            <input
              type="text"
              className="form-control"
              placeholder={`e.g., Daily OFF at 6pm`}
              value={scheduleName}
              onChange={(e) => setScheduleName(e.target.value)}
            />
          </div>

          {/* Type toggle (only for new schedules) */}
          {!editingJob && (
            <div className="mb-3">
              <label className="form-label">Type</label>
              <div className="btn-group w-100">
                <button
                  className={`btn ${scheduleType === 'cron' ? 'btn-primary' : 'btn-outline-primary'}`}
                  onClick={() => setScheduleType('cron')}
                >
                  <i className="bi bi-arrow-repeat me-1"></i>
                  Recurring
                </button>
                <button
                  className={`btn ${scheduleType === 'once' ? 'btn-primary' : 'btn-outline-primary'}`}
                  onClick={() => setScheduleType('once')}
                >
                  <i className="bi bi-calendar-event me-1"></i>
                  One-time
                </button>
              </div>
            </div>
          )}

          {/* Action */}
          <div className="mb-3">
            <label className="form-label">Action</label>
            <select
              className="form-select"
              value={actionType}
              onChange={(e) => setActionType(e.target.value as 'on' | 'off' | 'action')}
            >
              <option value="off">OFF</option>
              <option value="on">ON</option>
              {availableActions.length > 0 && (
                <option value="action">Custom Action...</option>
              )}
            </select>
          </div>

          {/* Custom action select */}
          {actionType === 'action' && availableActions.length > 0 && (
            <div className="mb-3">
              <label className="form-label">Custom Action</label>
              <select
                className="form-select"
                value={actionName}
                onChange={(e) => setActionName(e.target.value)}
              >
                <option value="">Select action...</option>
                {availableActions.map(action => (
                  <option key={action.name} value={action.name}>{action.name}</option>
                ))}
              </select>
            </div>
          )}

          {/* Cron expression (for recurring) */}
          {(scheduleType === 'cron' || editingJob?.cron_expression) && (
            <div className="mb-3">
              <label className="form-label">Cron Expression</label>
              <input
                type="text"
                className="form-control font-monospace"
                placeholder="0 18 * * *"
                value={cronExpression}
                onChange={(e) => setCronExpression(e.target.value)}
              />
              <div className="form-text">
                Format: minute hour day month weekday (e.g., "0 18 * * *" = daily at 6pm)
              </div>
              {cronPreview.length > 0 && (
                <div className="cron-preview mt-2">
                  <small className="text-muted">Next runs:</small>
                  <ul className="mb-0 ps-3">
                    {cronPreview.map((run, i) => (
                      <li key={i}><small>{formatDateTime(run)}</small></li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Date/time picker (for one-time) */}
          {scheduleType === 'once' && !editingJob && (
            <div className="mb-3">
              <label className="form-label">Date & Time</label>
              <div className="d-flex gap-2">
                <input
                  type="date"
                  className="form-control"
                  value={runAtDate}
                  onChange={(e) => setRunAtDate(e.target.value)}
                />
                <input
                  type="time"
                  className="form-control"
                  value={runAtTime}
                  onChange={(e) => setRunAtTime(e.target.value)}
                />
              </div>
            </div>
          )}

        </div>
      </div>
    </Modal>
  );
}
