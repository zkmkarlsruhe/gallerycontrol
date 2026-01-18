import { useState, useCallback } from 'react';
import type { Credential, ShellTemplate } from '../../types';
import { Modal } from '../ui/Modal';
import { DeviceTypeSelector, type DeviceType } from '../forms/DeviceTypeSelector';
import { PJLinkForm, defaultPJLinkData } from '../forms/PJLinkForm';
import { NetioForm, defaultNetioData } from '../forms/NetioForm';
import { AnelForm, defaultAnelData } from '../forms/AnelForm';
import { ShellForm, defaultShellData } from '../forms/ShellForm';
import type { ReachabilityStatus } from '../../hooks/useHostReachability';

interface AddDeviceModalProps {
  isOpen: boolean;
  exhibitionName: string;
  artworkName: string;
  artworkId: string;
  onClose: () => void;
  onSave: (artworkId: string, data: any) => Promise<void>;
  credentials?: Credential[];
  templates?: ShellTemplate[];
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
}: AddDeviceModalProps) {
  const [deviceType, setDeviceType] = useState<DeviceType>('pjlink');
  const [pjlinkData, setPjlinkData] = useState(defaultPJLinkData);
  const [netioData, setNetioData] = useState(defaultNetioData);
  const [anelData, setAnelData] = useState(defaultAnelData);
  const [shellData, setShellData] = useState(defaultShellData);
  const [saving, setSaving] = useState(false);
  const [reachabilityStatus, setReachabilityStatus] = useState<ReachabilityStatus>('idle');

  const handleReachabilityChange = useCallback((status: ReachabilityStatus) => {
    setReachabilityStatus(status);
  }, []);

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
          data = {
            name: netioData.name,
            device_type: 'netio',
            host: netioData.host,
            port: netioData.port,
            enabled: netioData.enabled,
            automation_enabled: netioData.automation_enabled,
            config: netioData.credential_id
              ? { credential_id: netioData.credential_id }
              : {},
          };
          break;
        case 'anel':
          data = {
            name: anelData.name,
            device_type: 'anel',
            host: anelData.host,
            port: anelData.port,
            enabled: anelData.enabled,
            automation_enabled: anelData.automation_enabled,
          };
          break;
        case 'shell':
          // Build commands object in the format the backend expects
          const shellCommands: Record<string, any> = {};
          if (shellData.onoff_mode) {
            if (shellData.on_cmd) {
              shellCommands.on = { cmd: shellData.on_cmd };
            }
            if (shellData.off_cmd) {
              shellCommands.off = { cmd: shellData.off_cmd };
            }
            if (shellData.status_cmd) {
              shellCommands.status = {
                cmd: shellData.status_cmd,
                onPattern: shellData.on_pattern || undefined,
                offPattern: shellData.off_pattern || undefined,
              };
            }
          } else {
            // Custom actions mode - add each action as a command
            shellData.actions.filter(a => a.name && a.cmd).forEach(action => {
              shellCommands[action.name] = { cmd: action.cmd };
            });
          }
          // Status command for custom mode (no on/off)
          if (!shellData.onoff_mode && shellData.status_cmd) {
            shellCommands.status = { cmd: shellData.status_cmd };
          }
          data = {
            name: shellData.name,
            device_type: 'shell',
            host: '#nohost',
            enabled: shellData.enabled,
            automation_enabled: shellData.onoff_mode ? shellData.automation_enabled : false,
            config: {
              credential_id: shellData.credential_id || undefined,
              commands: shellCommands,
            },
          };
          break;
      }
      await onSave(artworkId, data);
      onClose();
      // Reset forms
      setPjlinkData(defaultPJLinkData);
      setNetioData(defaultNetioData);
      setAnelData(defaultAnelData);
      setShellData(defaultShellData);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      title="Add Device"
      onClose={onClose}
      size="lg"
      footer={
        <>
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleSave}
            disabled={saving || !canSave}
            title={!canSave ? 'Host must be reachable before saving' : ''}
          >
            {saving ? 'Saving...' : !canSave ? 'Host Not Reachable' : 'Save Device'}
          </button>
        </>
      }
    >
      {/* Context Info */}
      <div className="context-info">
        <strong>Adding device to:</strong>
        <div className="mt-2">
          Exhibition: <strong>{exhibitionName}</strong><br />
          Artwork: <strong>{artworkName}</strong>
        </div>
      </div>

      {/* Device Type Selector */}
      <DeviceTypeSelector selectedType={deviceType} onSelect={setDeviceType} />

      {/* Device-specific forms */}
      {deviceType === 'pjlink' && <PJLinkForm data={pjlinkData} onChange={setPjlinkData} credentials={credentials} onReachabilityChange={handleReachabilityChange} />}
      {deviceType === 'netio' && <NetioForm data={netioData} onChange={setNetioData} credentials={credentials} onReachabilityChange={handleReachabilityChange} />}
      {deviceType === 'anel' && <AnelForm data={anelData} onChange={setAnelData} onReachabilityChange={handleReachabilityChange} />}
      {deviceType === 'shell' && <ShellForm data={shellData} onChange={setShellData} credentials={credentials} templates={templates} />}
    </Modal>
  );
}
