// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT
/**
 * Shared hook for device form state management.
 * Used by both AddDeviceModal and EditDeviceModal.
 */

import { useState, useCallback, useMemo, useEffect } from 'react';
import type { Device } from '../../../types';
import type { ReachabilityStatus } from '../../../hooks/useHostReachability';
import type {
  DeviceType,
  DeviceFormSlices,
  PJLinkFormData,
  NetioFormData,
  AnelFormData,
  ShellFormData,
} from './deviceForm.types';
import { getDefaultSlices } from './deviceForm.types';
import { hydrateFromDevice, computeUsedPorts } from './deviceFormPayload';

interface UseDeviceFormStateProps {
  mode: 'create' | 'edit';
  initialDevice?: Device | null;
  existingDevices?: Device[];
  defaultType?: DeviceType;
}

interface UseDeviceFormStateReturn {
  // Device type (locked in edit mode)
  deviceType: DeviceType;
  setDeviceType: ((type: DeviceType) => void) | undefined;

  // Form slices
  slices: DeviceFormSlices;
  pjlinkData: PJLinkFormData;
  netioData: NetioFormData;
  anelData: AnelFormData;
  shellData: ShellFormData;

  // Slice setters
  setPjlinkData: (data: PJLinkFormData) => void;
  setNetioData: (data: NetioFormData) => void;
  setAnelData: (data: AnelFormData) => void;
  setShellData: (data: ShellFormData) => void;

  // Reachability
  reachabilityStatus: ReachabilityStatus;
  handleReachabilityChange: (status: ReachabilityStatus) => void;

  // Used ports for NETIO/ANEL
  netioUsedPorts: number[];
  anelUsedPorts: number[];

  // Derived state
  isNetworkDevice: boolean;
  canSave: boolean;

  // Reset function (for modal close)
  reset: () => void;
}

export function useDeviceFormState({
  mode,
  initialDevice,
  existingDevices = [],
  defaultType = 'pjlink',
}: UseDeviceFormStateProps): UseDeviceFormStateReturn {
  // Device type state
  const [deviceType, setDeviceTypeInternal] = useState<DeviceType>(defaultType);

  // Form slices state
  const [slices, setSlices] = useState<DeviceFormSlices>(getDefaultSlices);

  // Reachability state
  const [reachabilityStatus, setReachabilityStatus] = useState<ReachabilityStatus>('idle');

  // Hydrate from device in edit mode
  useEffect(() => {
    if (mode === 'edit' && initialDevice) {
      const hydrated = hydrateFromDevice(initialDevice);
      setDeviceTypeInternal(hydrated.deviceType);
      setSlices(hydrated.slices);
      // Reset reachability when device changes
      setReachabilityStatus('idle');
    }
  }, [mode, initialDevice]);

  // Handle device type change (only in create mode)
  const setDeviceType = useCallback((type: DeviceType) => {
    if (mode === 'create') {
      setDeviceTypeInternal(type);
      // Reset reachability when type changes
      setReachabilityStatus('idle');
    }
  }, [mode]);

  // Individual slice setters
  const setPjlinkData = useCallback((data: PJLinkFormData) => {
    setSlices(prev => ({ ...prev, pjlink: data }));
  }, []);

  const setNetioData = useCallback((data: NetioFormData) => {
    setSlices(prev => ({ ...prev, netio: data }));
  }, []);

  const setAnelData = useCallback((data: AnelFormData) => {
    setSlices(prev => ({ ...prev, anel: data }));
  }, []);

  const setShellData = useCallback((data: ShellFormData) => {
    setSlices(prev => ({ ...prev, shell: data }));
  }, []);

  // Reachability handler
  const handleReachabilityChange = useCallback((status: ReachabilityStatus) => {
    setReachabilityStatus(status);
  }, []);

  // Compute used ports for NETIO devices
  const netioUsedPorts = useMemo(() => {
    return computeUsedPorts(
      'netio',
      slices.netio.host,
      existingDevices,
      mode === 'edit' ? initialDevice?.id : undefined
    );
  }, [existingDevices, slices.netio.host, mode, initialDevice?.id]);

  // Compute used ports for ANEL devices
  const anelUsedPorts = useMemo(() => {
    return computeUsedPorts(
      'anel',
      slices.anel.host,
      existingDevices,
      mode === 'edit' ? initialDevice?.id : undefined
    );
  }, [existingDevices, slices.anel.host, mode, initialDevice?.id]);

  // Derived: is this a network device?
  const isNetworkDevice = deviceType === 'pjlink' || deviceType === 'netio' || deviceType === 'anel';

  // Derived: can save? (network devices require reachability)
  const canSave = !isNetworkDevice || reachabilityStatus === 'reachable';

  // Reset all state to defaults
  const reset = useCallback(() => {
    setDeviceTypeInternal(defaultType);
    setSlices(getDefaultSlices());
    setReachabilityStatus('idle');
  }, [defaultType]);

  return {
    // Device type
    deviceType,
    setDeviceType: mode === 'create' ? setDeviceType : undefined,

    // Slices
    slices,
    pjlinkData: slices.pjlink,
    netioData: slices.netio,
    anelData: slices.anel,
    shellData: slices.shell,

    // Setters
    setPjlinkData,
    setNetioData,
    setAnelData,
    setShellData,

    // Reachability
    reachabilityStatus,
    handleReachabilityChange,

    // Used ports
    netioUsedPorts,
    anelUsedPorts,

    // Derived
    isNetworkDevice,
    canSave,

    // Reset
    reset,
  };
}
