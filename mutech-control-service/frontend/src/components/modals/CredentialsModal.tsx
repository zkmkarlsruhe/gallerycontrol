import { useState, useEffect } from 'react';
import type { Credential, CredentialCreate, CredentialUpdate } from '../../types';
import { Modal } from '../ui/Modal';
import { ConfirmButton } from '../ui/ConfirmButton';

interface CredentialsModalProps {
  isOpen: boolean;
  onClose: () => void;
  fetchCredentials: () => Promise<Credential[]>;
  createCredential: (data: CredentialCreate) => Promise<Credential>;
  updateCredential: (id: string, data: CredentialUpdate) => Promise<Credential>;
  deleteCredential: (id: string) => Promise<void>;
  showToast: (message: string, type: 'success' | 'danger' | 'info') => void;
}

const CREDENTIAL_TYPES = ['shell', 'pjlink', 'netio', 'anel'] as const;

export function CredentialsModal({
  isOpen,
  onClose,
  fetchCredentials,
  createCredential,
  updateCredential,
  deleteCredential,
  showToast,
}: CredentialsModalProps) {
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [isAdding, setIsAdding] = useState(false);

  // Form state
  const [formData, setFormData] = useState<CredentialCreate>({
    name: '',
    credential_type: 'shell',
    username: '',
    password: '',
    description: '',
  });

  const loadCredentials = async () => {
    try {
      const data = await fetchCredentials();
      setCredentials(data);
    } catch {
      showToast('Failed to load credentials', 'danger');
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadCredentials();
      resetForm();
    }
  }, [isOpen]);

  const resetForm = () => {
    setFormData({
      name: '',
      credential_type: 'shell',
      username: '',
      password: '',
      description: '',
    });
    setEditingId(null);
    setIsAdding(false);
  };

  const handleAdd = async () => {
    if (!formData.name.trim() || !formData.password.trim()) {
      showToast('Name and password are required', 'danger');
      return;
    }
    try {
      await createCredential(formData);
      showToast(`Credential "${formData.name}" created`, 'success');
      resetForm();
      loadCredentials();
    } catch {
      showToast('Failed to create credential', 'danger');
    }
  };

  const handleUpdate = async () => {
    if (!editingId || !formData.name.trim()) {
      showToast('Name is required', 'danger');
      return;
    }
    try {
      const updateData: CredentialUpdate = {
        name: formData.name,
        credential_type: formData.credential_type,
        username: formData.username || undefined,
        description: formData.description || undefined,
      };
      // Only include password if it was changed (not the masked value)
      if (formData.password && formData.password !== '********') {
        updateData.password = formData.password;
      }
      await updateCredential(editingId, updateData);
      showToast(`Credential "${formData.name}" updated`, 'success');
      resetForm();
      loadCredentials();
    } catch {
      showToast('Failed to update credential', 'danger');
    }
  };

  const handleDelete = async (id: string, name: string) => {
    try {
      await deleteCredential(id);
      showToast(`Credential "${name}" deleted`, 'success');
      loadCredentials();
    } catch {
      showToast('Failed to delete credential', 'danger');
    }
  };

  const startEdit = (credential: Credential) => {
    setFormData({
      name: credential.name,
      credential_type: credential.credential_type,
      username: credential.username || '',
      password: credential.password, // Will be "********"
      description: credential.description || '',
    });
    setEditingId(credential.id);
    setIsAdding(false);
  };

  const startAdd = () => {
    resetForm();
    setIsAdding(true);
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Credentials Store" size="xl">
      {/* Credentials List */}
      <table className="credentials-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Type</th>
            <th>Username</th>
            <th>Description</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {credentials.map(cred => (
            <tr key={cred.id} className={editingId === cred.id ? 'editing' : ''}>
              <td><code>{cred.name}</code></td>
              <td>{cred.credential_type}</td>
              <td>{cred.username || '-'}</td>
              <td>{cred.description || '-'}</td>
              <td>
                <div className="btn-group">
                  <button
                    className="btn btn-edit btn-sm"
                    onClick={() => startEdit(cred)}
                  >
                    Edit
                  </button>
                  <ConfirmButton
                    className="btn btn-delete btn-sm"
                    onConfirm={() => handleDelete(cred.id, cred.name)}
                    confirmText="Sure?"
                  >
                    Delete
                  </ConfirmButton>
                </div>
              </td>
            </tr>
          ))}
          {credentials.length === 0 && (
            <tr>
              <td colSpan={5} className="text-center text-muted">
                No credentials stored
              </td>
            </tr>
          )}
        </tbody>
      </table>

      {/* Add/Edit Form */}
      {(isAdding || editingId) && (
        <div className="credential-form">
          <h6>{editingId ? 'Edit Credential' : 'Add Credential'}</h6>
          <div className="form-row">
            <div className="form-group">
              <label>Name *</label>
              <input
                type="text"
                className="form-control form-control-sm"
                placeholder="e.g., museumstechnik"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label>Type</label>
              <select
                className="form-control form-control-sm"
                value={formData.credential_type}
                onChange={(e) => setFormData({ ...formData, credential_type: e.target.value as any })}
              >
                {CREDENTIAL_TYPES.map(type => (
                  <option key={type} value={type}>{type}</option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label>Username</label>
              <input
                type="text"
                className="form-control form-control-sm"
                placeholder="Optional"
                value={formData.username}
                onChange={(e) => setFormData({ ...formData, username: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label>Password *</label>
              <input
                type="password"
                className="form-control form-control-sm"
                placeholder={editingId ? 'Leave blank to keep current' : 'Required'}
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              />
            </div>
          </div>
          <div className="form-row">
            <div className="form-group flex-grow-1">
              <label>Description</label>
              <input
                type="text"
                className="form-control form-control-sm"
                placeholder="Optional description"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              />
            </div>
          </div>
          <div className="form-actions">
            <button className="btn btn-secondary btn-sm" onClick={resetForm}>
              Cancel
            </button>
            <button
              className="btn btn-add btn-sm"
              onClick={editingId ? handleUpdate : handleAdd}
            >
              {editingId ? 'Update' : 'Create'}
            </button>
          </div>
        </div>
      )}

      {/* Add Button */}
      {!isAdding && !editingId && (
        <button className="btn btn-add btn-sm mt-2" onClick={startAdd}>
          <i className="bi bi-plus"></i> Add Credential
        </button>
      )}

      {/* Usage Hint */}
      <div className="credentials-hint mt-3">
        <small className="text-muted">
          <i className="bi bi-info-circle me-1"></i>
          Use in shell commands: <code>{'{{PASSWORD:name}}'}</code> or <code>{'{{USER:name}}'}</code>
        </small>
      </div>
    </Modal>
  );
}
