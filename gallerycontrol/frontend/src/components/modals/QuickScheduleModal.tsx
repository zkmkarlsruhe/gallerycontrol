// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT
import { useState, useEffect, useCallback, useMemo } from 'react';
import { Modal } from '../ui/Modal';
import { ConfirmButton } from '../ui/ConfirmButton';
import { formatShortDateTime, formatShortDate } from '../../utils/dateFormat';
import type { Exhibition } from '../../types';

const API_BASE = import.meta.env.VITE_API_BASE || '';

interface ScheduledJob {
  id: string;
  name: string;
  job_type: string;
  run_once: boolean;
  target_type: string;
  target_id: string | null;
  action_type: string | null;
  enabled: boolean;
  next_run_at: string | null;
  executed_at: string | null;
}

interface QuickScheduleModalProps {
  isOpen: boolean;
  onClose: () => void;
  exhibitions: Exhibition[];
  showToast: (message: string, type: 'success' | 'danger' | 'info') => void;
}

function getNextFiveDays(): Date[] {
  const days: Date[] = [];
  for (let i = 0; i < 5; i++) {
    const date = new Date();
    date.setDate(date.getDate() + i);
    date.setHours(0, 0, 0, 0);
    days.push(date);
  }
  return days;
}

function isSameDay(date1: Date, date2: Date): boolean {
  return date1.toDateString() === date2.toDateString();
}

export function QuickScheduleModal({
  isOpen,
  onClose,
  exhibitions,
  showToast,
}: QuickScheduleModalProps) {
  // Filter to only schedulable exhibitions
  const schedulableExhibitions = exhibitions.filter(e => e.enabled && e.schedules_enabled);

  const [selectedExhibitionId, setSelectedExhibitionId] = useState<string>('');
  const [selectedDate, setSelectedDate] = useState<Date>(() => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return today;
  });
  const [actionType, setActionType] = useState<'on' | 'off'>('off');
  const [runAtTime, setRunAtTime] = useState('18:00');
  const [allJobs, setAllJobs] = useState<ScheduledJob[]>([]);
  const [loadingAll, setLoadingAll] = useState(false);
  const [saving, setSaving] = useState(false);

  const availableDays = getNextFiveDays();

  // Create exhibition name lookup
  const exhibitionNames = useMemo(
    () => new Map(schedulableExhibitions.map(e => [e.id, e.name])),
    [schedulableExhibitions]
  );

  // Reset state when modal opens
  useEffect(() => {
    if (isOpen) {
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      setSelectedDate(today);
      setActionType('off');
      setRunAtTime('18:00');
      // Auto-select first exhibition if available
      if (schedulableExhibitions.length > 0 && !selectedExhibitionId) {
        setSelectedExhibitionId(schedulableExhibitions[0].id);
      }
    }
  }, [isOpen, schedulableExhibitions, selectedExhibitionId]);

  // Fetch all exhibition one-shot jobs
  const fetchAllJobs = useCallback(async () => {
    if (schedulableExhibitions.length === 0) {
      setAllJobs([]);
      return;
    }
    setLoadingAll(true);
    try {
      const url = `${API_BASE}/api/admin/scheduled-jobs?target_type=exhibition`;
      const response = await fetch(url);
      if (!response.ok) throw new Error('Failed to fetch schedules');
      const data = await response.json();
      // Filter to only pending one-shot jobs within next 5 days
      const maxDate = new Date();
      maxDate.setDate(maxDate.getDate() + 5);
      const filtered = data.filter((job: ScheduledJob) => {
        if (!job.run_once || job.executed_at) return false;
        if (!job.next_run_at) return false;
        // Only include jobs for schedulable exhibitions
        if (!job.target_id || !exhibitionNames.has(job.target_id)) return false;
        const jobDate = new Date(job.next_run_at.endsWith('Z') ? job.next_run_at : job.next_run_at + 'Z');
        return jobDate <= maxDate;
      });
      // Sort by next_run_at
      filtered.sort((a: ScheduledJob, b: ScheduledJob) => {
        const dateA = new Date(a.next_run_at!);
        const dateB = new Date(b.next_run_at!);
        return dateA.getTime() - dateB.getTime();
      });
      setAllJobs(filtered);
    } catch (err) {
      console.error('Failed to fetch schedules:', err);
      showToast('Failed to load schedules', 'danger');
    } finally {
      setLoadingAll(false);
    }
  }, [schedulableExhibitions, exhibitionNames, showToast]);

  useEffect(() => {
    if (isOpen) {
      fetchAllJobs();
    }
  }, [isOpen, fetchAllJobs]);

  const handleCreate = async () => {
    if (!selectedExhibitionId) {
      showToast('Please select an exhibition', 'danger');
      return;
    }

    const exhibition = schedulableExhibitions.find(e => e.id === selectedExhibitionId);
    if (!exhibition) return;

    setSaving(true);
    try {
      // Build datetime string in local time format (backend expects local time)
      const dateStr = selectedDate.toISOString().split('T')[0];
      const runAt = `${dateStr}T${runAtTime}:00`;

      const name = `${actionType.toUpperCase()} ${exhibition.name}`;

      const response = await fetch(`${API_BASE}/api/admin/scheduled-jobs/once`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          run_at: runAt,
          target_type: 'exhibition',
          target_id: selectedExhibitionId,
          action_type: actionType,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to create schedule');
      }

      showToast('Schedule created', 'success');
      fetchAllJobs();
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Failed to create schedule', 'danger');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (jobId: string) => {
    try {
      const response = await fetch(`${API_BASE}/api/admin/scheduled-jobs/${jobId}`, {
        method: 'DELETE',
      });
      if (!response.ok) throw new Error('Failed to delete');
      showToast('Schedule deleted', 'success');
      fetchAllJobs();
    } catch {
      showToast('Failed to delete schedule', 'danger');
    }
  };

  // Get jobs for selected exhibition
  const selectedExhibitionJobs = allJobs.filter(j => j.target_id === selectedExhibitionId);
  const selectedExhibition = schedulableExhibitions.find(e => e.id === selectedExhibitionId);

  // Check if form is valid for adding
  const canAdd = selectedExhibitionId && runAtTime;

  return (
    <Modal
      isOpen={isOpen}
      title="Quick Schedule"
      onClose={onClose}
      size="lg"
      footer={
        <>
          <button className="btn btn-secondary btn-sm" onClick={onClose}>
            Close
          </button>
          {schedulableExhibitions.length > 0 && (
            <button
              className="btn btn-primary btn-sm"
              onClick={handleCreate}
              disabled={saving || !canAdd}
            >
              {saving ? (
                <>
                  <span className="spinner-border spinner-border-sm me-1"></span>
                  Adding...
                </>
              ) : (
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
      <div className="quick-schedule-modal">
        {schedulableExhibitions.length === 0 ? (
          <div className="text-center text-muted py-4">
            <i className="bi bi-calendar-x fs-1 d-block mb-3"></i>
            No exhibitions available for scheduling.
            <br />
            <small>Exhibitions must be enabled and have scheduling enabled.</small>
          </div>
        ) : (
          <>
            {/* Overview Section - All Schedules */}
            <div className="quick-schedule-overview mb-4">
              <h6 className="schedule-section-title">
                <i className="bi bi-calendar-week me-2"></i>
                All Scheduled (Next 5 Days)
              </h6>

              {loadingAll ? (
                <div className="text-center py-3">
                  <span className="spinner-border spinner-border-sm"></span>
                  <span className="ms-2">Loading...</span>
                </div>
              ) : allJobs.length === 0 ? (
                <div className="text-muted text-center py-3 bg-light rounded">
                  No scheduled jobs for the next 5 days
                </div>
              ) : (
                <div className="table-responsive">
                  <table className="table table-sm table-hover mb-0">
                    <thead className="table-light">
                      <tr>
                        <th>When</th>
                        <th>Exhibition</th>
                        <th>Action</th>
                        <th className="text-end"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {allJobs.map(job => (
                        <tr key={job.id}>
                          <td>{formatShortDateTime(job.next_run_at)}</td>
                          <td>{job.target_id ? exhibitionNames.get(job.target_id) || 'Unknown' : 'Unknown'}</td>
                          <td>
                            <span className={`badge ${job.action_type === 'on' ? 'bg-success' : 'bg-secondary'}`}>
                              {job.action_type?.toUpperCase()}
                            </span>
                          </td>
                          <td className="text-end">
                            <ConfirmButton
                              className="btn btn-sm btn-outline-danger py-0 px-1"
                              onConfirm={() => handleDelete(job.id)}
                              confirmText="Delete?"
                            >
                              <i className="bi bi-trash"></i>
                            </ConfirmButton>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <hr />

            {/* Add New Schedule Section */}
            <h6 className="schedule-section-title">
              <i className="bi bi-plus-circle me-2"></i>
              Add Schedule
            </h6>

            {/* Exhibition Selector */}
            <div className="mb-3">
              <label className="form-label">Exhibition</label>
              <select
                className="form-select form-select-sm"
                value={selectedExhibitionId}
                onChange={(e) => setSelectedExhibitionId(e.target.value)}
              >
                <option value="">Select an exhibition...</option>
                {schedulableExhibitions.map(ex => (
                  <option key={ex.id} value={ex.id}>{ex.name}</option>
                ))}
              </select>
            </div>

            {selectedExhibitionId && (
              <>
                {/* Date Selector */}
                <div className="mb-3">
                  <label className="form-label">Date</label>
                  <div className="btn-group w-100 quick-schedule-days">
                    {availableDays.map((day, idx) => (
                      <button
                        key={idx}
                        className={`btn btn-sm ${isSameDay(day, selectedDate) ? 'btn-primary' : 'btn-outline-primary'}`}
                        onClick={() => setSelectedDate(day)}
                      >
                        {idx === 0 ? 'Today' : idx === 1 ? 'Tomorrow' : formatShortDate(day)}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Action & Time */}
                <div className="mb-3">
                  <label className="form-label">Action & Time</label>
                  <div className="d-flex gap-2 align-items-center flex-wrap">
                    <select
                      className="form-select form-select-sm w-auto"
                      value={actionType}
                      onChange={(e) => setActionType(e.target.value as 'on' | 'off')}
                    >
                      <option value="off">OFF</option>
                      <option value="on">ON</option>
                    </select>
                    <span className="text-muted">at</span>
                    <input
                      type="time"
                      className="form-control form-control-sm w-auto"
                      value={runAtTime}
                      onChange={(e) => setRunAtTime(e.target.value)}
                    />
                  </div>
                </div>

                {/* Selected Exhibition Jobs */}
                {selectedExhibitionJobs.length > 0 && (
                  <div className="mt-3 p-3 bg-light rounded">
                    <small className="text-muted d-block mb-2">
                      <i className="bi bi-info-circle me-1"></i>
                      Existing schedules for {selectedExhibition?.name}:
                    </small>
                    <div className="d-flex flex-wrap gap-2">
                      {selectedExhibitionJobs.map(job => (
                        <span key={job.id} className={`badge ${job.action_type === 'on' ? 'bg-success' : 'bg-secondary'}`}>
                          {job.action_type?.toUpperCase()} @ {formatShortDateTime(job.next_run_at)}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </>
        )}
      </div>
    </Modal>
  );
}
