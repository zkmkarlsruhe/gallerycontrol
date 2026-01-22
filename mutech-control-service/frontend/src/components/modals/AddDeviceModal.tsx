import { useState, useCallback } from 'react';
import type { Credential, ShellTemplate, Device } from '../../types';
import { Modal } from '../ui/Modal';
import { DeviceTypeSelector } from '../forms/DeviceTypeSelector';
import { PJLinkForm } from '../forms/PJLinkForm';
import { NetioForm } from '../forms/NetioForm';
import { AnelForm } from '../forms/AnelForm';
import { ShellForm } from '../forms/ShellForm';
import { useDeviceFormState, buildDevicePayload } from './deviceForm';

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
  const [saving, setSaving] = useState(false);

  // Use shared form state hook
  const {
    deviceType,
    setDeviceType,
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
    reset,
  } = useDeviceFormState({
    mode: 'create',
    existingDevices,
    defaultType: 'pjlink',
  });

  const handleClose = useCallback(() => {
    reset();
    onClose();
  }, [reset, onClose]);

  const handleSave = async () => {
    setSaving(true);
    try {
      // Build payload using shared helper
      const data = buildDevicePayload(deviceType, slices, true);
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
      <DeviceTypeSelector selectedType={deviceType} onSelect={setDeviceType!} />

      {/* Device-specific forms */}
      {deviceType === 'pjlink' && <PJLinkForm data={pjlinkData} onChange={setPjlinkData} credentials={credentials} onReachabilityChange={handleReachabilityChange} />}
      {deviceType === 'netio' && <NetioForm data={netioData} onChange={setNetioData} credentials={credentials} onReachabilityChange={handleReachabilityChange} usedPorts={netioUsedPorts} />}
      {deviceType === 'anel' && <AnelForm data={anelData} onChange={setAnelData} credentials={credentials} onReachabilityChange={handleReachabilityChange} usedPorts={anelUsedPorts} />}
      {deviceType === 'shell' && <ShellForm data={shellData} onChange={setShellData} credentials={credentials} templates={templates} />}
    </Modal>
  );
}
