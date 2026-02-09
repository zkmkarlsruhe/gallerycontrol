// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT
import { useState, useEffect, useCallback } from 'react';
import type { ShellTemplate, ShellTemplateCreate, ShellTemplateUpdate, ShellTemplateAction } from '../../types';
import { Modal } from '../ui/Modal';
import { ConfirmButton } from '../ui/ConfirmButton';

interface ShellTemplatesModalProps {
  isOpen: boolean;
  onClose: () => void;
  fetchShellTemplates: () => Promise<ShellTemplate[]>;
  createShellTemplate: (data: ShellTemplateCreate) => Promise<ShellTemplate>;
  updateShellTemplate: (id: string, data: ShellTemplateUpdate) => Promise<ShellTemplate>;
  deleteShellTemplate: (id: string) => Promise<void>;
  showToast: (message: string, type: 'success' | 'danger' | 'info') => void;
}

interface TestResult {
  success: boolean;
  exit_code: number | null;
  stdout: string;
  stderr: string;
  duration_ms: number;
  error: string | null;
  commandLabel: string;
}

interface FormData {
  name: string;
  description: string;
  onoff_mode: boolean;
  status_command: string;
  status_on_pattern: string;
  status_off_pattern: string;
  on_command: string;
  off_command: string;
  actions: ShellTemplateAction[];
}

const emptyFormData: FormData = {
  name: '',
  description: '',
  onoff_mode: true,
  status_command: '',
  status_on_pattern: '',
  status_off_pattern: '',
  on_command: '',
  off_command: '',
  actions: [{ name: '', cmd: '' }],
};

export function ShellTemplatesModal({
  isOpen,
  onClose,
  fetchShellTemplates,
  createShellTemplate,
  updateShellTemplate,
  deleteShellTemplate,
  showToast,
}: ShellTemplatesModalProps) {
  const [templates, setTemplates] = useState<ShellTemplate[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [isAdding, setIsAdding] = useState(false);
  const [formData, setFormData] = useState<FormData>(emptyFormData);
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [testingCommand, setTestingCommand] = useState<string | null>(null);

  const loadTemplates = useCallback(async () => {
    try {
      const data = await fetchShellTemplates();
      setTemplates(data);
    } catch {
      showToast('Failed to load shell templates', 'danger');
    }
  }, [fetchShellTemplates, showToast]);

  const resetForm = useCallback(() => {
    setFormData(emptyFormData);
    setEditingId(null);
    setIsAdding(false);
    setTestResult(null);
  }, []);

  useEffect(() => {
    if (isOpen) {
      loadTemplates();
      resetForm();
    }
  }, [isOpen, loadTemplates, resetForm]);

  const update = (field: keyof FormData, value: string | boolean | ShellTemplateAction[]) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const updateAction = (index: number, field: 'name' | 'cmd', value: string) => {
    const newActions = [...formData.actions];
    newActions[index] = { ...newActions[index], [field]: value };
    update('actions', newActions);
  };

  const addAction = () => {
    update('actions', [...formData.actions, { name: '', cmd: '' }]);
  };

  const removeAction = (index: number) => {
    update('actions', formData.actions.filter((_, i) => i !== index));
  };

  const testCommand = async (command: string, label: string) => {
    if (!command.trim()) return;
    setTestingCommand(label);
    setTestResult(null);

    try {
      const response = await fetch('/api/admin/shell/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command, timeout: 5 }),
      });
      const result = await response.json();
      setTestResult({ ...result, commandLabel: label });
    } catch (err) {
      setTestResult({
        success: false,
        exit_code: null,
        stdout: '',
        stderr: '',
        duration_ms: 0,
        error: err instanceof Error ? err.message : 'Unknown error',
        commandLabel: label,
      });
    } finally {
      setTestingCommand(null);
    }
  };

  const handleSave = async () => {
    if (!formData.name.trim()) {
      showToast('Template name is required', 'danger');
      return;
    }

    const templateData: ShellTemplateCreate = {
      name: formData.name,
      description: formData.description || undefined,
      onoff_mode: formData.onoff_mode,
      status_command: formData.status_command || undefined,
      status_on_pattern: formData.status_on_pattern || undefined,
      status_off_pattern: formData.status_off_pattern || undefined,
      on_command: formData.onoff_mode ? formData.on_command || undefined : undefined,
      off_command: formData.onoff_mode ? formData.off_command || undefined : undefined,
      actions: !formData.onoff_mode ? formData.actions.filter(a => a.name && a.cmd) : undefined,
    };

    try {
      if (editingId) {
        await updateShellTemplate(editingId, templateData);
        showToast(`Template "${formData.name}" updated`, 'success');
      } else {
        await createShellTemplate(templateData);
        showToast(`Template "${formData.name}" created`, 'success');
      }
      resetForm();
      loadTemplates();
    } catch {
      showToast(`Failed to ${editingId ? 'update' : 'create'} template`, 'danger');
    }
  };

  const handleDelete = async (id: string, name: string) => {
    try {
      await deleteShellTemplate(id);
      showToast(`Template "${name}" deleted`, 'success');
      if (editingId === id) resetForm();
      loadTemplates();
    } catch {
      showToast('Failed to delete template', 'danger');
    }
  };

  const startEdit = (template: ShellTemplate) => {
    setFormData({
      name: template.name,
      description: template.description || '',
      onoff_mode: template.onoff_mode,
      status_command: template.status_command || '',
      status_on_pattern: template.status_on_pattern || '',
      status_off_pattern: template.status_off_pattern || '',
      on_command: template.on_command || '',
      off_command: template.off_command || '',
      actions: template.actions?.length ? template.actions : [{ name: '', cmd: '' }],
    });
    setEditingId(template.id);
    setIsAdding(false);
    setTestResult(null);
  };

  const startAdd = () => {
    resetForm();
    setIsAdding(true);
  };

  const TestButton = ({ command, label }: { command: string; label: string }) => (
    <button
      type="button"
      className="btn btn-outline-secondary btn-sm"
      onClick={() => testCommand(command, label)}
      disabled={!command.trim() || testingCommand !== null}
      title={command.trim() ? `Test ${label}` : 'Enter a command first'}
    >
      {testingCommand === label ? (
        <><i className="bi bi-hourglass-split"></i></>
      ) : (
        <><i className="bi bi-play-fill"></i></>
      )}
    </button>
  );

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Shell Templates Library"
      size="xl"
      footer={
        <>
          <button className="btn btn-secondary btn-sm" onClick={isAdding || editingId ? resetForm : onClose}>
            Close
          </button>
          {isAdding || editingId ? (
            <button className="btn btn-primary btn-sm" onClick={handleSave}>
              {editingId ? 'Update Template' : 'Create Template'}
            </button>
          ) : (
            <button className="btn btn-primary btn-sm" onClick={startAdd}>
              <i className="bi bi-plus"></i> Add Template
            </button>
          )}
        </>
      }
    >
      {/* Templates List */}
      <table className="credentials-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Mode</th>
            <th>Description</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {templates.map(tmpl => (
            <tr key={tmpl.id} className={editingId === tmpl.id ? 'editing' : ''}>
              <td><code>{tmpl.name}</code></td>
              <td>
                <span className={`badge ${tmpl.onoff_mode ? 'bg-primary' : 'bg-secondary'}`}>
                  {tmpl.onoff_mode ? 'ON/OFF' : 'Custom'}
                </span>
              </td>
              <td>{tmpl.description || '-'}</td>
              <td>
                <div className="btn-group">
                  <button className="btn btn-edit btn-sm" onClick={() => startEdit(tmpl)} title="Edit">
                    <i className="bi bi-pencil"></i>
                  </button>
                  <ConfirmButton
                    className="btn btn-delete btn-sm"
                    onConfirm={() => handleDelete(tmpl.id, tmpl.name)}
                    confirmText="Sure?"
                    title="Delete"
                  >
                    <i className="bi bi-trash"></i>
                  </ConfirmButton>
                </div>
              </td>
            </tr>
          ))}
          {templates.length === 0 && (
            <tr>
              <td colSpan={4} className="text-center text-muted">
                No templates saved. Create a shell device and save it as a template, or add one manually.
              </td>
            </tr>
          )}
        </tbody>
      </table>

      {/* Add/Edit Form */}
      {(isAdding || editingId) && (
        <div className="credential-form mt-3">
          <h6>{editingId ? 'Edit Template' : 'Add Template'}</h6>

          {/* Basic Info */}
          <div className="form-row">
            <div className="form-group">
              <label>Name *</label>
              <input
                type="text"
                className="form-control form-control-sm"
                placeholder="e.g., Media Server Template"
                value={formData.name}
                onChange={(e) => update('name', e.target.value)}
              />
            </div>
            <div className="form-group flex-grow-1">
              <label>Description</label>
              <input
                type="text"
                className="form-control form-control-sm"
                placeholder="Optional description"
                value={formData.description}
                onChange={(e) => update('description', e.target.value)}
              />
            </div>
          </div>

          {/* Mode Toggle */}
          <div className="form-check form-switch my-3">
            <input
              className="form-check-input"
              type="checkbox"
              id="template-onoff-mode"
              checked={formData.onoff_mode}
              onChange={(e) => update('onoff_mode', e.target.checked)}
            />
            <label className="form-check-label" htmlFor="template-onoff-mode">
              <strong>ON/OFF Control Mode</strong>
              <small className="text-muted ms-2">
                {formData.onoff_mode ? '(with ON/OFF commands)' : '(custom commands only)'}
              </small>
            </label>
          </div>

          {/* Status Command (both modes) */}
          <div className="mb-3">
            <label className="form-label small"><strong>Status Command</strong></label>
            <div className="input-group input-group-sm">
              <input
                type="text"
                className="form-control"
                placeholder="Command to check device state"
                value={formData.status_command}
                onChange={(e) => update('status_command', e.target.value)}
              />
              <TestButton command={formData.status_command} label="Status" />
            </div>
            <div className="row mt-2">
              <div className="col-6">
                <input
                  type="text"
                  className="form-control form-control-sm"
                  placeholder="ON Pattern (regex)"
                  value={formData.status_on_pattern}
                  onChange={(e) => update('status_on_pattern', e.target.value)}
                />
              </div>
              <div className="col-6">
                <input
                  type="text"
                  className="form-control form-control-sm"
                  placeholder="OFF Pattern (regex)"
                  value={formData.status_off_pattern}
                  onChange={(e) => update('status_off_pattern', e.target.value)}
                />
              </div>
            </div>
          </div>

          {/* ON/OFF Mode Commands */}
          {formData.onoff_mode && (
            <div className="row mb-3">
              <div className="col-6">
                <label className="form-label small"><strong>ON Command</strong></label>
                <div className="input-group input-group-sm">
                  <input
                    type="text"
                    className="form-control"
                    placeholder="Command to turn ON"
                    value={formData.on_command}
                    onChange={(e) => update('on_command', e.target.value)}
                  />
                  <TestButton command={formData.on_command} label="ON" />
                </div>
              </div>
              <div className="col-6">
                <label className="form-label small"><strong>OFF Command</strong></label>
                <div className="input-group input-group-sm">
                  <input
                    type="text"
                    className="form-control"
                    placeholder="Command to turn OFF"
                    value={formData.off_command}
                    onChange={(e) => update('off_command', e.target.value)}
                  />
                  <TestButton command={formData.off_command} label="OFF" />
                </div>
              </div>
            </div>
          )}

          {/* Custom Actions Mode */}
          {!formData.onoff_mode && (
            <div className="mb-3">
              <label className="form-label small"><strong>Custom Actions</strong></label>
              {formData.actions.map((action, index) => (
                <div key={index} className="input-group input-group-sm mb-2">
                  <input
                    type="text"
                    className="form-control"
                    placeholder="Button label"
                    value={action.name}
                    onChange={(e) => updateAction(index, 'name', e.target.value)}
                    style={{ maxWidth: '150px' }}
                  />
                  <input
                    type="text"
                    className="form-control"
                    placeholder="Command"
                    value={action.cmd}
                    onChange={(e) => updateAction(index, 'cmd', e.target.value)}
                  />
                  <TestButton command={action.cmd} label={action.name || `Action ${index + 1}`} />
                  {formData.actions.length > 1 && (
                    <button
                      type="button"
                      className="btn btn-outline-danger btn-sm"
                      onClick={() => removeAction(index)}
                    >
                      <i className="bi bi-x"></i>
                    </button>
                  )}
                </div>
              ))}
              <button type="button" className="btn btn-add btn-sm" onClick={addAction}>
                <i className="bi bi-plus"></i> Add Action
              </button>
            </div>
          )}

          {/* Test Result */}
          {testResult && (
            <div className={`alert alert-${testResult.success ? 'success' : 'danger'} py-2 mb-3`}>
              <strong>{testResult.commandLabel}:</strong>{' '}
              {testResult.success ? 'Success' : 'Failed'}
              {testResult.exit_code !== null && <span> (exit {testResult.exit_code})</span>}
              {testResult.stdout && <pre className="mb-0 mt-1 small">{testResult.stdout.slice(0, 200)}</pre>}
              {testResult.error && <pre className="mb-0 mt-1 small text-danger">{testResult.error}</pre>}
            </div>
          )}

        </div>
      )}

      {/* Usage Hint */}
      <div className="credentials-hint mt-3">
        <small className="text-muted">
          <i className="bi bi-info-circle me-1"></i>
          Templates pre-fill shell device forms. Save a working device as template from the Edit Device modal.
        </small>
      </div>
    </Modal>
  );
}
