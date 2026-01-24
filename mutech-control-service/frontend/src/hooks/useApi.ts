import { useState, useCallback } from 'react';
import type {
  Exhibition,
  ControlResult,
  Credential,
  CredentialCreate,
  CredentialUpdate,
  ShellTemplate,
  ShellTemplateCreate,
  ShellTemplateUpdate,
  ServiceHealth,
} from '../types';

const API_BASE = import.meta.env.VITE_API_BASE || '';

export function useApi() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch all exhibitions with state
  const fetchExhibitions = useCallback(async (): Promise<Exhibition[]> => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/api/state/exhibitions`);
      if (!response.ok) throw new Error('Failed to fetch exhibitions');
      const data = await response.json();
      return data;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // Control device (on/off)
  const controlDevice = useCallback(async (
    deviceId: string,
    command: 'on' | 'off'
  ): Promise<ControlResult> => {
    const response = await fetch(
      `${API_BASE}/api/control/device/${deviceId}/${command}`,
      { method: 'POST' }
    );
    return response.json();
  }, []);

  // Execute device action (shell commands like Reboot)
  const executeAction = useCallback(async (
    deviceId: string,
    actionName: string
  ): Promise<ControlResult> => {
    const response = await fetch(
      `${API_BASE}/api/control/device/${deviceId}/action/${encodeURIComponent(actionName)}`,
      { method: 'POST' }
    );
    return response.json();
  }, []);

  // Control artwork (all devices)
  const controlArtwork = useCallback(async (
    artworkId: string,
    command: 'on' | 'off'
  ): Promise<ControlResult> => {
    const response = await fetch(
      `${API_BASE}/api/control/artwork/${artworkId}/${command}`,
      { method: 'POST' }
    );
    return response.json();
  }, []);

  // Control exhibition (all devices)
  const controlExhibition = useCallback(async (
    exhibitionId: string,
    command: 'on' | 'off'
  ): Promise<ControlResult> => {
    const response = await fetch(
      `${API_BASE}/api/control/exhibition/${exhibitionId}/${command}`,
      { method: 'POST' }
    );
    return response.json();
  }, []);

  // CRUD: Create exhibition
  const createExhibition = useCallback(async (name: string): Promise<{ id: string; name: string }> => {
    const response = await fetch(`${API_BASE}/api/admin/exhibitions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, enabled: true }),
    });
    if (!response.ok) throw new Error('Failed to create exhibition');
    return response.json();
  }, []);

  // CRUD: Create artwork
  const createArtwork = useCallback(async (exhibitionId: string, name: string): Promise<{ id: string; name: string }> => {
    const response = await fetch(`${API_BASE}/api/admin/artworks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ exhibition_id: exhibitionId, name, enabled: true }),
    });
    if (!response.ok) throw new Error('Failed to create artwork');
    return response.json();
  }, []);

  // CRUD: Create device
  const createDevice = useCallback(async (
    artworkId: string,
    data: { name: string; device_type: string; host: string; port?: number }
  ): Promise<{ id: string; name: string }> => {
    const response = await fetch(`${API_BASE}/api/admin/devices`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ artwork_id: artworkId, ...data, enabled: true }),
    });
    if (!response.ok) throw new Error('Failed to create device');
    return response.json();
  }, []);

  // CRUD: Update exhibition
  const updateExhibition = useCallback(async (
    id: string,
    data: { name?: string; enabled?: boolean }
  ): Promise<void> => {
    const response = await fetch(`${API_BASE}/api/admin/exhibitions/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error('Failed to update exhibition');
  }, []);

  // CRUD: Update artwork
  const updateArtwork = useCallback(async (
    id: string,
    data: { name?: string; enabled?: boolean }
  ): Promise<void> => {
    const response = await fetch(`${API_BASE}/api/admin/artworks/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error('Failed to update artwork');
  }, []);

  // CRUD: Delete exhibition
  const deleteExhibition = useCallback(async (id: string): Promise<void> => {
    const response = await fetch(`${API_BASE}/api/admin/exhibitions/${id}`, { method: 'DELETE' });
    if (!response.ok) throw new Error('Failed to delete exhibition');
  }, []);

  // CRUD: Delete artwork
  const deleteArtwork = useCallback(async (id: string): Promise<void> => {
    const response = await fetch(`${API_BASE}/api/admin/artworks/${id}`, { method: 'DELETE' });
    if (!response.ok) throw new Error('Failed to delete artwork');
  }, []);

  // CRUD: Update device
  const updateDevice = useCallback(async (
    id: string,
    data: {
      name?: string;
      host?: string;
      port?: number;
      enabled?: boolean;
      automation_enabled?: boolean;
      config?: Record<string, any>;
    }
  ): Promise<void> => {
    const response = await fetch(`${API_BASE}/api/admin/devices/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error('Failed to update device');
  }, []);

  // CRUD: Delete device
  const deleteDevice = useCallback(async (id: string): Promise<void> => {
    const response = await fetch(`${API_BASE}/api/admin/devices/${id}`, { method: 'DELETE' });
    if (!response.ok) throw new Error('Failed to delete device');
  }, []);

  // Credentials: Fetch all
  const fetchCredentials = useCallback(async (type?: string): Promise<Credential[]> => {
    const url = type
      ? `${API_BASE}/api/admin/credentials?type=${encodeURIComponent(type)}`
      : `${API_BASE}/api/admin/credentials`;
    const response = await fetch(url);
    if (!response.ok) throw new Error('Failed to fetch credentials');
    return response.json();
  }, []);

  // Credentials: Create
  const createCredential = useCallback(async (data: CredentialCreate): Promise<Credential> => {
    const response = await fetch(`${API_BASE}/api/admin/credentials`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error('Failed to create credential');
    return response.json();
  }, []);

  // Credentials: Update
  const updateCredential = useCallback(async (id: string, data: CredentialUpdate): Promise<Credential> => {
    const response = await fetch(`${API_BASE}/api/admin/credentials/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error('Failed to update credential');
    return response.json();
  }, []);

  // Credentials: Delete
  const deleteCredential = useCallback(async (id: string): Promise<void> => {
    const response = await fetch(`${API_BASE}/api/admin/credentials/${id}`, { method: 'DELETE' });
    if (!response.ok) throw new Error('Failed to delete credential');
  }, []);

  // Shell Templates: Fetch all
  const fetchShellTemplates = useCallback(async (): Promise<ShellTemplate[]> => {
    const response = await fetch(`${API_BASE}/api/admin/shell-templates`);
    if (!response.ok) throw new Error('Failed to fetch shell templates');
    return response.json();
  }, []);

  // Shell Templates: Create
  const createShellTemplate = useCallback(async (data: ShellTemplateCreate): Promise<ShellTemplate> => {
    const response = await fetch(`${API_BASE}/api/admin/shell-templates`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error('Failed to create shell template');
    return response.json();
  }, []);

  // Shell Templates: Update
  const updateShellTemplate = useCallback(async (id: string, data: ShellTemplateUpdate): Promise<ShellTemplate> => {
    const response = await fetch(`${API_BASE}/api/admin/shell-templates/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error('Failed to update shell template');
    return response.json();
  }, []);

  // Shell Templates: Delete
  const deleteShellTemplate = useCallback(async (id: string): Promise<void> => {
    const response = await fetch(`${API_BASE}/api/admin/shell-templates/${id}`, { method: 'DELETE' });
    if (!response.ok) throw new Error('Failed to delete shell template');
  }, []);

  // Shell Templates: Save device as template
  const saveDeviceAsTemplate = useCallback(async (deviceId: string, name?: string): Promise<ShellTemplate> => {
    const url = name
      ? `${API_BASE}/api/admin/devices/${deviceId}/save-as-template?name=${encodeURIComponent(name)}`
      : `${API_BASE}/api/admin/devices/${deviceId}/save-as-template`;
    const response = await fetch(url, { method: 'POST' });
    if (!response.ok) throw new Error('Failed to save device as template');
    return response.json();
  }, []);

  // Email Inventory: Fetch email config
  const fetchEmailConfig = useCallback(async (): Promise<{
    recipients: string[];
    subject: string;
    from_address: string;
    smtp_configured: boolean;
  }> => {
    const response = await fetch(`${API_BASE}/api/admin/inventory/email-config`);
    if (!response.ok) throw new Error('Failed to fetch email config');
    return response.json();
  }, []);

  // Email Inventory: Fetch preview
  const fetchInventoryPreview = useCallback(async (
    exhibitionIds?: string[],
    includeDisabled?: boolean
  ): Promise<{ content: string; exhibition_count: number; device_count: number }> => {
    const params = new URLSearchParams();
    if (exhibitionIds && exhibitionIds.length > 0) {
      params.set('exhibition_ids', exhibitionIds.join(','));
    }
    if (includeDisabled) {
      params.set('include_disabled', 'true');
    }
    const queryString = params.toString();
    const url = queryString
      ? `${API_BASE}/api/admin/inventory/preview?${queryString}`
      : `${API_BASE}/api/admin/inventory/preview`;
    const response = await fetch(url);
    if (!response.ok) throw new Error('Failed to fetch inventory preview');
    return response.json();
  }, []);

  // Email Inventory: Send email (recipients and subject from config)
  const sendInventoryEmail = useCallback(async (
    exhibitionIds?: string[],
    includeDisabled?: boolean
  ): Promise<{ success: boolean; message: string }> => {
    const response = await fetch(`${API_BASE}/api/admin/inventory/email`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        exhibition_ids: exhibitionIds || null,
        include_disabled: includeDisabled || false,
      }),
    });
    return response.json();
  }, []);

  // Fetch service health status
  const fetchServiceHealth = useCallback(async (): Promise<ServiceHealth[]> => {
    try {
      const response = await fetch(`${API_BASE}/api/state/services`);
      if (!response.ok) return [];
      return response.json();
    } catch {
      return [];
    }
  }, []);

  return {
    loading,
    error,
    fetchExhibitions,
    controlDevice,
    executeAction,
    controlArtwork,
    controlExhibition,
    createExhibition,
    createArtwork,
    createDevice,
    updateExhibition,
    updateArtwork,
    deleteExhibition,
    deleteArtwork,
    updateDevice,
    deleteDevice,
    fetchCredentials,
    createCredential,
    updateCredential,
    deleteCredential,
    fetchShellTemplates,
    createShellTemplate,
    updateShellTemplate,
    deleteShellTemplate,
    saveDeviceAsTemplate,
    fetchEmailConfig,
    fetchInventoryPreview,
    sendInventoryEmail,
    fetchServiceHealth,
  };
}
