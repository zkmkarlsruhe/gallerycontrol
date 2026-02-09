// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT

import { useState, useEffect, useCallback } from 'react';
import type { Exhibition, ControlResult } from '../types';

type PendingCommand = 'on' | 'off';

interface UseDeviceControlOptions {
  exhibitions: Exhibition[];
  controlDevice: (id: string, cmd: 'on' | 'off') => Promise<ControlResult>;
  controlArtwork: (id: string, cmd: 'on' | 'off') => Promise<ControlResult>;
  controlExhibition: (id: string, cmd: 'on' | 'off') => Promise<ControlResult>;
  executeAction: (id: string, action: string) => Promise<ControlResult>;
  showToast: (message: string, type: 'success' | 'danger' | 'info') => void;
  loadData: () => void;
}

interface UseDeviceControlReturn {
  pendingStates: Map<string, PendingCommand>;
  handleDeviceControl: (deviceId: string, command: PendingCommand, deviceName: string) => Promise<void>;
  handleArtworkControl: (artworkId: string, command: PendingCommand, artworkName: string) => Promise<void>;
  handleExhibitionControl: (exhibitionId: string, command: PendingCommand, exhibitionName: string) => Promise<void>;
  handleAllControl: (command: PendingCommand) => Promise<void>;
  handleAction: (deviceId: string, actionName: string, deviceName: string) => Promise<void>;
}

/**
 * Custom hook for device control operations with pending state management.
 * Handles device, artwork, and exhibition control with optimistic UI updates.
 */
export function useDeviceControl({
  exhibitions,
  controlDevice,
  controlArtwork,
  controlExhibition,
  executeAction,
  showToast,
  loadData,
}: UseDeviceControlOptions): UseDeviceControlReturn {
  const [pendingStates, setPendingStates] = useState<Map<string, PendingCommand>>(new Map());

  // Clear pending states when device states match targets AND not in fast polling
  useEffect(() => {
    if (pendingStates.size === 0) return;

    const deviceInfoMap = new Map<string, { state: number; isVerifying: boolean }>();
    for (const exhibition of exhibitions) {
      for (const artwork of exhibition.artworks) {
        for (const device of artwork.devices) {
          deviceInfoMap.set(device.id, {
            state: device.state,
            isVerifying: device.poll_status?.is_verifying || false,
          });
        }
      }
    }

    const toRemove: string[] = [];
    pendingStates.forEach((targetCommand, deviceId) => {
      const deviceInfo = deviceInfoMap.get(deviceId);
      if (deviceInfo !== undefined) {
        // Don't clear while device is verifying (fast polling in progress)
        if (deviceInfo.isVerifying) return;

        // State 1 = on, State 0 = off
        const targetState = targetCommand === 'on' ? 1 : 0;
        if (deviceInfo.state === targetState) {
          toRemove.push(deviceId);
        }
      }
    });

    if (toRemove.length > 0) {
      setPendingStates(prev => {
        const next = new Map(prev);
        toRemove.forEach(id => next.delete(id));
        return next;
      });
    }
  }, [exhibitions, pendingStates]);

  const handleDeviceControl = useCallback(async (
    deviceId: string,
    command: PendingCommand,
    deviceName: string
  ) => {
    // Set pending state immediately for visual feedback
    setPendingStates(prev => new Map(prev).set(deviceId, command));

    try {
      const result = await controlDevice(deviceId, command);
      if (result.success) {
        showToast(`${command.toUpperCase()} sent to ${deviceName}`, 'success');
        setTimeout(loadData, 1000);
      } else {
        showToast(`Failed: ${result.error || 'Unknown error'}`, 'danger');
        // Clear pending state on failure
        setPendingStates(prev => {
          const next = new Map(prev);
          next.delete(deviceId);
          return next;
        });
      }
    } catch {
      showToast('Network error', 'danger');
      // Clear pending state on error
      setPendingStates(prev => {
        const next = new Map(prev);
        next.delete(deviceId);
        return next;
      });
    }
  }, [controlDevice, showToast, loadData]);

  const handleArtworkControl = useCallback(async (
    artworkId: string,
    command: PendingCommand,
    artworkName: string
  ) => {
    // Set pending state for all automation-enabled devices in this artwork
    const artwork = exhibitions.flatMap(e => e.artworks).find(a => a.id === artworkId);
    if (artwork) {
      setPendingStates(prev => {
        const next = new Map(prev);
        artwork.devices.filter(d => d.automation_enabled && d.enabled).forEach(d => next.set(d.id, command));
        return next;
      });
    }

    try {
      const result = await controlArtwork(artworkId, command);
      if (result.success) {
        showToast(`${command.toUpperCase()} sent to ${artworkName}`, 'success');
        setTimeout(loadData, 1000);
      } else {
        showToast(`Failed: ${result.error || 'Unknown error'}`, 'danger');
      }
    } catch {
      showToast('Network error', 'danger');
    }
  }, [exhibitions, controlArtwork, showToast, loadData]);

  const handleExhibitionControl = useCallback(async (
    exhibitionId: string,
    command: PendingCommand,
    exhibitionName: string
  ) => {
    // Set pending state for all automation-enabled devices in this exhibition
    const exhibition = exhibitions.find(e => e.id === exhibitionId);
    if (exhibition) {
      setPendingStates(prev => {
        const next = new Map(prev);
        exhibition.artworks.flatMap(a => a.devices).filter(d => d.automation_enabled && d.enabled).forEach(d => next.set(d.id, command));
        return next;
      });
    }

    try {
      const result = await controlExhibition(exhibitionId, command);
      if (result.success) {
        showToast(`${command.toUpperCase()} sent to ${exhibitionName}`, 'success');
        setTimeout(loadData, 2000);
      } else {
        showToast(`Failed: ${result.error || 'Unknown error'}`, 'danger');
      }
    } catch {
      showToast('Network error', 'danger');
    }
  }, [exhibitions, controlExhibition, showToast, loadData]);

  const handleAllControl = useCallback(async (command: PendingCommand) => {
    const enabledExhibitions = exhibitions.filter(e => e.enabled);
    if (enabledExhibitions.length === 0) {
      showToast('No enabled exhibitions to control', 'info');
      return;
    }

    // Set pending state for all automation-enabled devices in all exhibitions
    setPendingStates(prev => {
      const next = new Map(prev);
      enabledExhibitions.flatMap(e => e.artworks).flatMap(a => a.devices).filter(d => d.automation_enabled && d.enabled).forEach(d => next.set(d.id, command));
      return next;
    });

    showToast(`Sending ${command.toUpperCase()} to all exhibitions...`, 'info');

    // Send commands to all enabled exhibitions in parallel
    const results = await Promise.allSettled(
      enabledExhibitions.map(e => controlExhibition(e.id, command))
    );

    const successful = results.filter(r => r.status === 'fulfilled' && r.value.success).length;
    const failed = enabledExhibitions.length - successful;

    if (failed === 0) {
      showToast(`${command.toUpperCase()} sent to all ${successful} exhibitions`, 'success');
    } else {
      showToast(`${command.toUpperCase()}: ${successful} succeeded, ${failed} failed`, 'danger');
    }

    setTimeout(loadData, 2000);
  }, [exhibitions, controlExhibition, showToast, loadData]);

  const handleAction = useCallback(async (
    deviceId: string,
    actionName: string,
    deviceName: string
  ) => {
    try {
      showToast(`Executing ${actionName}...`, 'info');
      const result = await executeAction(deviceId, actionName);
      if (result.success) {
        showToast(`${actionName} executed on ${deviceName}`, 'success');
      } else {
        showToast(`${actionName} failed: ${result.error || 'Unknown error'}`, 'danger');
      }
    } catch {
      showToast('Network error', 'danger');
    }
  }, [executeAction, showToast]);

  return {
    pendingStates,
    handleDeviceControl,
    handleArtworkControl,
    handleExhibitionControl,
    handleAllControl,
    handleAction,
  };
}
