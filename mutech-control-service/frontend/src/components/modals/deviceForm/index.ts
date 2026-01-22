/**
 * Device form utilities - shared between AddDeviceModal and EditDeviceModal.
 */

// Types
export type {
  DeviceType,
  PJLinkFormData,
  NetioFormData,
  AnelFormData,
  ShellFormData,
  ShellAction,
  DeviceFormData,
  DeviceFormSlices,
  DeviceFormState,
  DevicePayload,
} from './deviceForm.types';

export {
  defaultPJLinkData,
  defaultNetioData,
  defaultAnelData,
  defaultShellData,
  emptyShellAction,
  getDefaultSlices,
} from './deviceForm.types';

// Payload helpers
export { buildDevicePayload, hydrateFromDevice, computeUsedPorts } from './deviceFormPayload';

// Hook
export { useDeviceFormState } from './useDeviceFormState';
