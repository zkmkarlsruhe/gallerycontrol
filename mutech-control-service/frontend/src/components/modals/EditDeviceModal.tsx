import { useState, useEffect, useCallback, useMemo } from 'react';
import type { Device, Credential, ShellTemplate } from '../../types';
import { Modal } from '../ui/Modal';
import { PJLinkForm, defaultPJLinkData } from '../forms/PJLinkForm';
import { NetioForm, defaultNetioData } from '../forms/NetioForm';
import { AnelForm, defaultAnelData } from '../forms/AnelForm';
import { ShellForm, defaultShellData } from '../forms/ShellForm';
import type { ReachabilityStatus } from '../../hooks/useHostReachability';
import { portUtils } from '../../utils/portUtils';

interface EditDeviceModalProps {
  isOpen: boolean;
  device: Device | null;
  onClose: () => void;
  onSave: (id: string, data: any) => Promise<void>;
  onDelete?: (id: string, name: string) => Promise<void>;
  credentials?: Credential[];
  templates?: ShellTemplate[];
  onSaveAsTemplate?: (deviceId: string, name: string) => Promise<void>;
  existingDevices?: Device[];
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
}: EditDeviceModalProps) {
  const [pjlinkData, setPjlinkData] = useState(defaultPJLinkData);
  const [netioData, setNetioData] = useState(defaultNetioData);
  const [anelData, setAnelData] = useState(defaultAnelData);
  const [shellData, setShellData] = useState(defaultShellData);
  const [saving, setSaving] = useState(false);
  const [showTemplatePrompt, setShowTemplatePrompt] = useState(false);
  const [templateName, setTemplateName] = useState('');
  const [savingTemplate, setSavingTemplate] = useState(false);
  const [reachabilityStatus, setReachabilityStatus] = useState<ReachabilityStatus>('idle');

  const handleReachabilityChange = useCallback((status: ReachabilityStatus) => {
    setReachabilityStatus(status);
  }, []);

  // Get used ports for NETIO/ANEL (excluding current device)
  // Both stored 0-indexed in DB, UI displays 1-indexed
  const netioUsedPorts = useMemo(() => {
    if (!netioData.host || !device) return [];
    return existingDevices
      .filter(d => d.device_type === 'netio' && d.host === netioData.host && d.port !== null && d.id !== device.id)
      .map(d => portUtils.dbToUI(d.port));
  }, [existingDevices, netioData.host, device]);

  const anelUsedPorts = useMemo(() => {
    if (!anelData.host || !device) return [];
    return existingDevices
      .filter(d => d.device_type === 'anel' && d.host === anelData.host && d.port !== null && d.id !== device.id)
      .map(d => portUtils.dbToUI(d.port));
  }, [existingDevices, anelData.host, device]);

  // For network devices, require reachability before saving
  const isNetworkDevice = device?.device_type === 'pjlink' || device?.device_type === 'netio' || device?.device_type === 'anel';
  const canSave = !isNetworkDevice || reachabilityStatus === 'reachable';

  // Load device data into the appropriate form when device changes
  useEffect(() => {
    if (!device) return;

    switch (device.device_type) {
      case 'pjlink':
        setPjlinkData({
          name: device.name,
          host: device.host,
          port: device.port || 4352,
          credential_id: device.config?.credential_id || '',
          enabled: device.enabled,
          automation_enabled: device.automation_enabled,
        });
        break;
      case 'netio':
        // NETIO ports: convert 0-indexed DB to 1-indexed UI
        setNetioData({
          name: device.name,
          host: device.host,
          port: portUtils.dbToUI(device.port),
          credential_id: device.config?.credential_id || '',
          enabled: device.enabled,
          automation_enabled: device.automation_enabled,
        });
        break;
      case 'anel':
        // ANEL ports: convert 0-indexed DB to 1-indexed UI
        setAnelData({
          name: device.name,
          host: device.host,
          port: portUtils.dbToUI(device.port),
          credential_id: device.config?.credential_id || '',
          enabled: device.enabled,
          automation_enabled: device.automation_enabled,
        });
        break;
      case 'shell':
        // Extract commands from config.commands structure
        const commands = device.config?.commands || {};
        const hasOnOff = !!(commands.on?.cmd && commands.off?.cmd);

        // Extract custom actions from:
        // 1. New format: config.actions array
        // 2. Old format: commands that are not on/off/status (for backwards compatibility)
        let customActions: Array<{name: string, cmd: string}> = [];

        // Check new actions array first
        if (device.config?.actions && Array.isArray(device.config.actions)) {
          customActions = device.config.actions
            .filter((a: any) => a.name && a.cmd)
            .map((a: any) => ({ name: a.name, cmd: a.cmd }));
        }

        // Fall back to old format if no actions array
        if (customActions.length === 0) {
          customActions = Object.entries(commands || {})
            .filter(([key]) => !['on', 'off', 'status'].includes(key))
            .map(([name, cfg]: [string, any]) => ({ name, cmd: cfg?.cmd || '' }));
        }

        setShellData({
          name: device.name,
          credential_id: device.config?.credential_id || '',
          onoff_mode: hasOnOff,
          automation_enabled: device.automation_enabled,
          status_cmd: commands.status?.cmd || '',
          on_pattern: commands.status?.onPattern || '',
          off_pattern: commands.status?.offPattern || '',
          on_cmd: commands.on?.cmd || '',
          off_cmd: commands.off?.cmd || '',
          actions: customActions.length > 0 ? customActions : [{ name: '', cmd: '' }],
          enabled: device.enabled,
        });
        break;
    }
  }, [device]);

  const handleSave = async () => {
    if (!device) return;
    setSaving(true);
    try {
      let data: any;
      switch (device.device_type) {
        case 'pjlink':
          data = {
            name: pjlinkData.name,
            host: pjlinkData.host,
            port: pjlinkData.port,
            enabled: pjlinkData.enabled,
            automation_enabled: pjlinkData.automation_enabled,
            config: pjlinkData.credential_id
              ? { credential_id: pjlinkData.credential_id }
              : {},
          };
          break;
        case 'netio':
          // NETIO ports: convert 1-indexed UI to 0-indexed DB
          data = {
            name: netioData.name,
            host: netioData.host,
            port: portUtils.uiToDB(netioData.port),
            enabled: netioData.enabled,
            automation_enabled: netioData.automation_enabled,
            config: netioData.credential_id
              ? { credential_id: netioData.credential_id }
              : {},
          };
          break;
        case 'anel':
          // ANEL ports: convert 1-indexed UI to 0-indexed DB
          data = {
            name: anelData.name,
            host: anelData.host,
            port: portUtils.uiToDB(anelData.port),
            enabled: anelData.enabled,
            automation_enabled: anelData.automation_enabled,
            config: anelData.credential_id
              ? { credential_id: anelData.credential_id }
              : {},
          };
          break;
        case 'shell':
          // Build commands object - combined mode supports both ON/OFF and actions
          const shellCommands: Record<string, any> = {};

          // Status command (always included if set)
          if (shellData.status_cmd) {
            shellCommands.status = {
              cmd: shellData.status_cmd,
              onPattern: shellData.on_pattern || undefined,
              offPattern: shellData.off_pattern || undefined,
            };
          }

          // ON/OFF commands (optional)
          if (shellData.on_cmd) {
            shellCommands.on = { cmd: shellData.on_cmd };
          }
          if (shellData.off_cmd) {
            shellCommands.off = { cmd: shellData.off_cmd };
          }

          // Custom actions - stored in separate actions array
          const shellActions = shellData.actions
            .filter(a => a.name && a.cmd)
            .map(a => ({ name: a.name, cmd: a.cmd }));

          // Determine if automation should be enabled:
          // - Must have both ON and OFF commands
          // - User must have checked the automation checkbox
          const hasOnOff = !!(shellData.on_cmd && shellData.off_cmd);

          data = {
            name: shellData.name,
            host: '#nohost',
            enabled: shellData.enabled,
            automation_enabled: hasOnOff && shellData.automation_enabled,
            config: {
              credential_id: shellData.credential_id || undefined,
              commands: shellCommands,
              actions: shellActions.length > 0 ? shellActions : undefined,
            },
          };
          break;
      }
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
              <button type="button" className="btn btn-delete btn-sm" onClick={handleDelete}>
                Delete Device
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
              Cancel
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
      {device.device_type === 'pjlink' && <PJLinkForm data={pjlinkData} onChange={setPjlinkData} credentials={credentials} onReachabilityChange={handleReachabilityChange} />}
      {device.device_type === 'netio' && <NetioForm data={netioData} onChange={setNetioData} credentials={credentials} onReachabilityChange={handleReachabilityChange} usedPorts={netioUsedPorts} />}
      {device.device_type === 'anel' && <AnelForm data={anelData} onChange={setAnelData} credentials={credentials} onReachabilityChange={handleReachabilityChange} usedPorts={anelUsedPorts} />}
      {device.device_type === 'shell' && <ShellForm data={shellData} onChange={setShellData} credentials={credentials} templates={templates} />}

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
