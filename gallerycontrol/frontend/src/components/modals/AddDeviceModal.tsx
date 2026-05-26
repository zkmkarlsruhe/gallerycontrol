// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT
import { useState, useCallback } from 'react';
import type { Credential, ShellTemplate, Device, SatelliteInfo } from '../../types';
import { Modal } from '../ui/Modal';
import { DeviceTypeSelector } from '../forms/DeviceTypeSelector';
import { PJLinkForm } from '../forms/PJLinkForm';
import { NetioForm } from '../forms/NetioForm';
import { AnelForm } from '../forms/AnelForm';
import { ShellForm } from '../forms/ShellForm';
import { useDeviceFormState, buildDevicePayload } from './deviceForm';
import type { DevicePayload } from './deviceForm/deviceForm.types';

interface AddDeviceModalProps {
  isOpen: boolean;
  exhibitionName: string;
  artworkName: string;
  artworkId: string;
  onClose: () => void;
  onSave: (artworkId: string, data: DevicePayload) => Promise<void>;
  credentials?: Credential[];
  templates?: ShellTemplate[];
  existingDevices?: Device[];
  availableSatellites?: SatelliteInfo[];
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
  availableSatellites = [],
}: AddDeviceModalProps) {
  const [saving, setSaving] = useState(false);
  const [satelliteId, setSatelliteId] = useState<string | null>(null);

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
    setSatelliteId(null);
    onClose();
  }, [reset, onClose]);

  const handleSave = async () => {
    setSaving(true);
    try {
      // Build payload using shared helper
      const data = buildDevicePayload(deviceType, slices, true);
      data.satellite_id = satelliteId;
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
      {deviceType === 'pjlink' && <PJLinkForm data={pjlinkData} onChange={setPjlinkData} credentials={credentials} onReachabilityChange={handleReachabilityChange} satelliteId={satelliteId} />}
      {deviceType === 'netio' && <NetioForm data={netioData} onChange={setNetioData} credentials={credentials} onReachabilityChange={handleReachabilityChange} usedPorts={netioUsedPorts} satelliteId={satelliteId} />}
      {deviceType === 'anel' && <AnelForm data={anelData} onChange={setAnelData} credentials={credentials} onReachabilityChange={handleReachabilityChange} usedPorts={anelUsedPorts} satelliteId={satelliteId} />}
      {deviceType === 'shell' && <ShellForm data={shellData} onChange={setShellData} credentials={credentials} templates={templates} />}

      {availableSatellites.length > 0 && (
        <div className="mt-3">
          <label className="form-label" htmlFor="add-device-satellite">
            Satellite Relay
          </label>
          <select
            id="add-device-satellite"
            className="form-select form-select-sm"
            value={satelliteId ?? ''}
            onChange={(e) => setSatelliteId(e.target.value || null)}
          >
            <option value="">Direct connection (default)</option>
            {availableSatellites.map((sat) => (
              <option key={sat.id} value={sat.id}>
                {sat.name} {sat.is_connected ? '(online)' : '(offline)'}
              </option>
            ))}
          </select>
          <div className="small text-muted mt-1">
            Choose from the satellites assigned to this exhibition
          </div>
        </div>
      )}
    </Modal>
  );
}
