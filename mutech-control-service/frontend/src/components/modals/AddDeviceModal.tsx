import { useState, useCallback, useMemo } from 'react';
import type { Credential, ShellTemplate, Device } from '../../types';
import { Modal } from '../ui/Modal';
import { DeviceTypeSelector, type DeviceType } from '../forms/DeviceTypeSelector';
import { PJLinkForm, defaultPJLinkData } from '../forms/PJLinkForm';
import { NetioForm, defaultNetioData } from '../forms/NetioForm';
import { AnelForm, defaultAnelData } from '../forms/AnelForm';
import { ShellForm, defaultShellData } from '../forms/ShellForm';
import type { ReachabilityStatus } from '../../hooks/useHostReachability';
import { portUtils } from '../../utils/portUtils';

interface AddDeviceModalProps {
  isOpen: boolean;
  exhibitionName: string;
  artworkName: string;
  artworkId: string;
  onClose: () => void;
  onSave: (artworkId: string, data: any) => Promise<void>;
  credentials?: Credential[];
  templates?: ShellTemplate[];
  existingDevices?: Device[];
}

export function AddDeviceModal({
  isOpen,
  exhibitionName,
  artworkName,
  artworkId,
  onClose,
  onSave,
  credentials = [],
  templates = [],
  existingDevices = [],
}: AddDeviceModalProps) {
  const [deviceType, setDeviceType] = useState<DeviceType>('pjlink');
  const [pjlinkData, setPjlinkData] = useState(defaultPJLinkData);
  const [netioData, setNetioData] = useState(defaultNetioData);
  const [anelData, setAnelData] = useState(defaultAnelData);
  const [shellData, setShellData] = useState(defaultShellData);
  const [saving, setSaving] = useState(false);
  const [reachabilityStatus, setReachabilityStatus] = useState<ReachabilityStatus>('idle');

  // Get used ports for NETIO and ANEL devices by host
  // Both stored 0-indexed in DB, UI displays 1-indexed
  const netioUsedPorts = useMemo(() => {
    if (!netioData.host) return [];
    return existingDevices
      .filter(d => d.device_type === 'netio' && d.host === netioData.host && d.port !== null)
      .map(d => portUtils.dbToUI(d.port));
  }, [existingDevices, netioData.host]);

  const anelUsedPorts = useMemo(() => {
    if (!anelData.host) return [];
    return existingDevices
      .filter(d => d.device_type === 'anel' && d.host === anelData.host && d.port !== null)
      .map(d => portUtils.dbToUI(d.port));
  }, [existingDevices, anelData.host]);

  const handleReachabilityChange = useCallback((status: ReachabilityStatus) => {
    setReachabilityStatus(status);
  }, []);

  // Reset all form state when closing (cancel or after save)
  const resetForms = useCallback(() => {
    setDeviceType('pjlink');
    setPjlinkData(defaultPJLinkData);
    setNetioData(defaultNetioData);
    setAnelData(defaultAnelData);
    setShellData(defaultShellData);
    setReachabilityStatus('idle');
  }, []);

  const handleClose = useCallback(() => {
    resetForms();
    onClose();
  }, [resetForms, onClose]);

  // For network devices, require reachability before saving
  const isNetworkDevice = deviceType === 'pjlink' || deviceType === 'netio' || deviceType === 'anel';
  const canSave = !isNetworkDevice || reachabilityStatus === 'reachable';

  const handleSave = async () => {
    setSaving(true);
    try {
      let data: any;
      switch (deviceType) {
        case 'pjlink':
          data = {
            name: pjlinkData.name,
            device_type: 'pjlink',
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
            device_type: 'netio',
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
            device_type: 'anel',
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
            device_type: 'shell',
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
      await onSave(artworkId, data);
      handleClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      title="Add Device"
      onClose={handleClose}
      size="lg"
      footer={
        <>
          <button type="button" className="btn btn-secondary btn-sm" onClick={handleClose}>
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
        </>
      }
    >
      {/* Context Info - compact single line */}
      <div className="context-info-compact">
        <span className="context-label">Adding to:</span>
        <span className="context-path">{exhibitionName} <i className="bi bi-chevron-right"></i> {artworkName}</span>
      </div>

      {/* Device Type Selector */}
      <DeviceTypeSelector selectedType={deviceType} onSelect={setDeviceType} />

      {/* Device-specific forms */}
      {deviceType === 'pjlink' && <PJLinkForm data={pjlinkData} onChange={setPjlinkData} credentials={credentials} onReachabilityChange={handleReachabilityChange} />}
      {deviceType === 'netio' && <NetioForm data={netioData} onChange={setNetioData} credentials={credentials} onReachabilityChange={handleReachabilityChange} usedPorts={netioUsedPorts} />}
      {deviceType === 'anel' && <AnelForm data={anelData} onChange={setAnelData} credentials={credentials} onReachabilityChange={handleReachabilityChange} usedPorts={anelUsedPorts} />}
      {deviceType === 'shell' && <ShellForm data={shellData} onChange={setShellData} credentials={credentials} templates={templates} />}
    </Modal>
  );
}
