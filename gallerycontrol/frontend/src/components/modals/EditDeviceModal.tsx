// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT
import { useState, useEffect } from 'react';
import type { Device, Credential, ShellTemplate } from '../../types';
import { Modal } from '../ui/Modal';
import { PJLinkForm } from '../forms/PJLinkForm';
import { NetioForm } from '../forms/NetioForm';
import { AnelForm } from '../forms/AnelForm';
import { ShellForm } from '../forms/ShellForm';
import { useDeviceFormState, buildDevicePayload } from './deviceForm';
import type { DevicePayload } from './deviceForm/deviceForm.types';

interface EditDeviceModalProps {
  isOpen: boolean;
  device: Device | null;
  onClose: () => void;
  onSave: (id: string, data: DevicePayload) => Promise<void>;
  onDelete?: (id: string, name: string) => Promise<void>;
  credentials?: Credential[];
  templates?: ShellTemplate[];
  onSaveAsTemplate?: (deviceId: string, name: string) => Promise<void>;
  existingDevices?: Device[];
  satelliteName?: string | null; // Name of exhibition's satellite (if assigned)
}

export function EditDeviceModal({
  isOpen,
  device,
  onClose,
  onSave,
  onDelete,
  credentials = [],
  templates = [],
  onSaveAsTemplate,
  existingDevices = [],
  satelliteName = null,
}: EditDeviceModalProps) {
  const [saving, setSaving] = useState(false);
  const [showTemplatePrompt, setShowTemplatePrompt] = useState(false);
  const [templateName, setTemplateName] = useState('');
  const [savingTemplate, setSavingTemplate] = useState(false);
  const [schedulesEnabled, setSchedulesEnabled] = useState(device?.schedules_enabled ?? false);
  const [useSatellite, setUseSatellite] = useState(device?.use_satellite ?? false);

  // Sync state when device changes
  useEffect(() => {
    if (device) {
      setSchedulesEnabled(device.schedules_enabled ?? false);
      setUseSatellite(device.use_satellite ?? false);
    }
  }, [device]);

  // Use shared form state hook
  const {
    deviceType,
    slices,
    pjlinkData,
    netioData,
    anelData,
    shellData,
    setPjlinkData,
    setNetioData,
    setAnelData,
    setShellData,
    handleReachabilityChange,
    netioUsedPorts,
    anelUsedPorts,
    canSave,
  } = useDeviceFormState({
    mode: 'edit',
    initialDevice: device,
    existingDevices,
  });

  const handleSave = async () => {
    if (!device) return;
    setSaving(true);
    try {
      // Build payload using shared helper (don't include device_type for updates)
      const data = buildDevicePayload(deviceType, slices, false);
      // Add feature flags
      data.schedules_enabled = schedulesEnabled;
      data.use_satellite = useSatellite;
      await onSave(device.id, data);
      onClose();
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!device || !onDelete) return;
    if (confirm(`Delete device "${device.name}"? This cannot be undone.`)) {
      await onDelete(device.id, device.name);
      onClose();
    }
  };

  const handleSaveAsTemplate = async () => {
    if (!device || !onSaveAsTemplate || !templateName.trim()) return;
    setSavingTemplate(true);
    try {
      await onSaveAsTemplate(device.id, templateName.trim());
      setShowTemplatePrompt(false);
      setTemplateName('');
    } finally {
      setSavingTemplate(false);
    }
  };

  if (!device) return null;

  const getDeviceTypeName = (type: string) => {
    switch (type) {
      case 'pjlink': return 'PJLink Projector';
      case 'netio': return 'NETIO Power Socket';
      case 'anel': return 'ANEL Power Socket';
      case 'shell': return 'Shell Command';
      default: return type;
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      title={`Edit Device: ${device.name}`}
      onClose={onClose}
      size="lg"
      footer={
        <div className="d-flex justify-content-between w-100">
          <div className="d-flex gap-2">
            {onDelete && (
              <button type="button" className="btn btn-delete btn-sm" onClick={handleDelete} title="Delete Device">
                <i className="bi bi-trash"></i>
              </button>
            )}
            {device.device_type === 'shell' && onSaveAsTemplate && (
              <button
                type="button"
                className="btn btn-outline-secondary btn-sm"
                onClick={() => {
                  setTemplateName(`Template from ${device.name}`);
                  setShowTemplatePrompt(true);
                }}
              >
                <i className="bi bi-bookmark-plus me-1"></i>
                Save to Library
              </button>
            )}
          </div>
          <div className="d-flex gap-2">
            <button type="button" className="btn btn-secondary btn-sm" onClick={onClose}>
              Close
            </button>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={handleSave}
              disabled={saving || !canSave}
              title={!canSave ? 'Host must be reachable before saving' : ''}
            >
              {saving ? 'Saving...' : !canSave ? 'Host Not Reachable' : 'Save'}
            </button>
          </div>
        </div>
      }
    >
      {/* Device Type Info */}
      <div className="context-info-compact">
        <span className="context-label">Device Type:</span>
        <span className="context-path">{getDeviceTypeName(device.device_type)}</span>
        <span className="text-muted small ms-2">(cannot be changed)</span>
      </div>

      {/* Device-specific forms */}
      {deviceType === 'pjlink' && <PJLinkForm data={pjlinkData} onChange={setPjlinkData} credentials={credentials} onReachabilityChange={handleReachabilityChange} />}
      {deviceType === 'netio' && <NetioForm data={netioData} onChange={setNetioData} credentials={credentials} onReachabilityChange={handleReachabilityChange} usedPorts={netioUsedPorts} />}
      {deviceType === 'anel' && <AnelForm data={anelData} onChange={setAnelData} credentials={credentials} onReachabilityChange={handleReachabilityChange} usedPorts={anelUsedPorts} />}
      {deviceType === 'shell' && <ShellForm data={shellData} onChange={setShellData} credentials={credentials} templates={templates} />}

      {/* Settings Section */}
      <div className="form-section">
        <div className="section-title">Settings</div>
        <div className="form-check">
          <input
            className="form-check-input"
            type="checkbox"
            id="device-schedules-enabled"
            checked={schedulesEnabled}
            onChange={(e) => setSchedulesEnabled(e.target.checked)}
          />
          <label className="form-check-label" htmlFor="device-schedules-enabled">
            Enable Schedules
          </label>
          <div className="small text-muted">
            Shows the calendar button to configure scheduled on/off actions
          </div>
        </div>

        {/* Satellite routing - only show if exhibition has satellite assigned */}
        {satelliteName && (
          <div className="form-check mt-3">
            <input
              className="form-check-input"
              type="checkbox"
              id="device-use-satellite"
              checked={useSatellite}
              onChange={(e) => setUseSatellite(e.target.checked)}
            />
            <label className="form-check-label" htmlFor="device-use-satellite">
              Route via Satellite ({satelliteName})
            </label>
            <div className="small text-muted">
              Commands will be sent through the satellite relay instead of direct connection
            </div>
          </div>
        )}
      </div>

      {/* Template Name Prompt */}
      {showTemplatePrompt && (
        <div className="template-prompt mt-3 p-3 border rounded bg-light">
          <label className="form-label small"><strong>Save as Template</strong></label>
          <div className="input-group input-group-sm">
            <input
              type="text"
              className="form-control"
              placeholder="Template name"
              value={templateName}
              onChange={(e) => setTemplateName(e.target.value)}
              autoFocus
            />
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                setShowTemplatePrompt(false);
                setTemplateName('');
              }}
              disabled={savingTemplate}
            >
              Cancel
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleSaveAsTemplate}
              disabled={savingTemplate || !templateName.trim()}
            >
              {savingTemplate ? 'Saving...' : 'Save'}
            </button>
          </div>
          <small className="text-muted">This will save the current device configuration as a reusable template.</small>
        </div>
      )}
    </Modal>
  );
}
