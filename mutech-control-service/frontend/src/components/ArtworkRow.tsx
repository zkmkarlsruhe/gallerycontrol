import type { Artwork, Device } from '../types';
import { DeviceBadge } from './DeviceBadge';
import { DeviceAccordion } from './DeviceAccordion';
import { ConfirmButton } from './ui/ConfirmButton';
import { TouchSafeButton } from './ui/TouchSafeButton';

interface ArtworkRowProps {
  artwork: Artwork;
  isAlternate: boolean;
  editMode: boolean;
  expandedDevice: string | null;
  onToggleDevice: (deviceId: string) => void;
  onArtworkControl: (artworkId: string, command: 'on' | 'off', artworkName: string) => void;
  onDeviceControl: (deviceId: string, command: 'on' | 'off', deviceName: string) => void;
  onDeviceAction: (deviceId: string, actionName: string, deviceName: string) => void;
  onAddDevice?: () => void;
  onEditArtwork?: () => void;
  onDeleteArtwork?: (artworkId: string, artworkName: string) => void;
  onEditDevice?: (device: Device) => void;
  onDeleteDevice?: (deviceId: string, deviceName: string) => void;
  onViewDeviceLogs?: (deviceId: string) => void;
}

function getDeviceStateLabel(state: number): string {
  switch (state) {
    case 1: return 'ON';
    case 0: return 'OFF';
    case 2: return 'COOLING';
    case 3: return 'WARMING';
    default: return 'ERROR';
  }
}

function getDeviceStateClass(state: number): string {
  switch (state) {
    case 1: return 'state-on';
    case 0: return 'state-off';
    case 2: case 3: return 'state-cooling';
    default: return 'state-error';
  }
}

export function ArtworkRow({
  artwork,
  isAlternate,
  editMode,
  expandedDevice,
  onToggleDevice,
  onArtworkControl,
  onDeviceControl,
  onDeviceAction,
  onAddDevice,
  onEditArtwork,
  onDeleteArtwork,
  onEditDevice,
  onDeleteDevice,
  onViewDeviceLogs,
}: ArtworkRowProps) {
  const isDisabled = !artwork.enabled;

  // Sort devices: automation devices first, manual (non-automation) at bottom
  const sortedDevices = [...artwork.devices].sort((a, b) => {
    if (a.automation_enabled === b.automation_enabled) return 0;
    return a.automation_enabled ? -1 : 1;
  });

  const automationDevices = sortedDevices.filter(d => d.automation_enabled);
  const manualDevices = sortedDevices.filter(d => !d.automation_enabled);

  return (
    <div>
      <div className={`artwork-row ${isAlternate ? 'alt' : ''} ${isDisabled ? 'disabled' : ''}`}>
        {/* Edit Mode: Traditional layout with table */}
        {editMode ? (
          <>
            <div className="artwork-header-row">
              <div className="artwork-name">
                <a className="api-link" href={`/api/control/artwork/${artwork.id}/on`}>#</a>
                {isDisabled && <span className="disabled-badge">DISABLED</span>}
                {artwork.name}
              </div>
              <div className="artwork-controls">
                <button className="btn btn-add btn-sm me-2" onClick={onAddDevice}>+ Device</button>
                <div className="btn-group me-2">
                  <button className="btn btn-edit btn-sm" onClick={onEditArtwork}>Edit</button>
                  <ConfirmButton className="btn btn-delete btn-sm" onConfirm={() => onDeleteArtwork?.(artwork.id, artwork.name)} confirmText="Sure?">Delete</ConfirmButton>
                </div>
                <div className="btn-group">
                  <button className="btn btn-on btn-sm" onClick={() => onArtworkControl(artwork.id, 'on', artwork.name)}>ON</button>
                  <button className="btn btn-off btn-sm" onClick={() => onArtworkControl(artwork.id, 'off', artwork.name)}>OFF</button>
                </div>
              </div>
            </div>
            <div className="devices-table">
              {sortedDevices.map(device => (
                <div key={device.id} className={`device-table-row ${!device.enabled ? 'disabled' : ''} ${!device.automation_enabled ? 'manual-device' : ''}`}>
                  <div className="device-table-info" onClick={() => onToggleDevice(device.id)}>
                    <span className={`device-state-dot ${getDeviceStateClass(device.state)}`}></span>
                    <span className="device-table-name">{device.name}</span>
                    <span className="device-table-meta">{device.device_type} · {device.host}</span>
                    <span className="device-table-state">{getDeviceStateLabel(device.state)}</span>
                    {!device.automation_enabled && <span className="manual-badge">MANUAL</span>}
                  </div>
                  <div className="device-table-actions">
                    <button
                      className="btn btn-device-logs"
                      onClick={() => onViewDeviceLogs?.(device.id)}
                      title="View logs for this device"
                    >
                      <i className="bi bi-terminal"></i>
                    </button>
                    <div className="btn-group">
                      <button className="btn btn-edit btn-sm" onClick={() => onEditDevice?.(device)}>Edit</button>
                      <ConfirmButton className="btn btn-delete btn-sm" onConfirm={() => onDeleteDevice?.(device.id, device.name)} confirmText="Delete?">Delete</ConfirmButton>
                    </div>
                    {device.actions && device.actions.length > 0 && (
                      <div className="btn-group">
                        {device.actions.map((action, idx) => (
                          <ConfirmButton key={action.name} className={`btn btn-action btn-action-${idx + 1} btn-sm`} onConfirm={() => onDeviceAction(device.id, action.name, device.name)} confirmText="Run?">{action.name}</ConfirmButton>
                        ))}
                      </div>
                    )}
                    {device.device_type !== 'shell' && (
                      <div className="btn-group">
                        <ConfirmButton className="btn btn-on btn-sm" onConfirm={() => onDeviceControl(device.id, 'on', device.name)} confirmText="ON?">ON</ConfirmButton>
                        <ConfirmButton className="btn btn-off btn-sm" onConfirm={() => onDeviceControl(device.id, 'off', device.name)} confirmText="OFF?">OFF</ConfirmButton>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </>
        ) : (
          /* Normal Mode: Horizontal layout - # | Name | Units | Buttons */
          <>
            {/* Automation devices row - only show artwork ON/OFF if there are automation devices */}
            {automationDevices.length > 0 && (
              <div className="artwork-inline-layout">
                <a className="api-link" href={`/api/control/artwork/${artwork.id}/on`}>#</a>
                <div className="artwork-name-inline">
                  {isDisabled && <span className="disabled-badge">DISABLED</span>}
                  {artwork.name}
                </div>
                <div className="artwork-devices-inline">
                  {automationDevices.map(device => (
                    <DeviceBadge
                      key={device.id}
                      device={device}
                      isExpanded={expandedDevice === device.id}
                      onClick={() => onToggleDevice(device.id)}
                    />
                  ))}
                </div>
                <div className="artwork-buttons-inline">
                  <div className="btn-group">
                    <TouchSafeButton className="btn btn-on btn-sm" onClick={() => onArtworkControl(artwork.id, 'on', artwork.name)}>ON</TouchSafeButton>
                    <TouchSafeButton className="btn btn-off btn-sm" onClick={() => onArtworkControl(artwork.id, 'off', artwork.name)}>OFF</TouchSafeButton>
                  </div>
                </div>
              </div>
            )}

            {/* Manual devices - same inline layout with colored backgrounds on device section only */}
            {/* No artwork ON/OFF for manual-only artworks */}
            {manualDevices.map((device, index) => (
              <div key={device.id} className="artwork-inline-layout manual-row">
                {/* Show # and name only if no automation devices (first manual is the header) */}
                {automationDevices.length === 0 && index === 0 ? (
                  <>
                    <a className="api-link" href={`/api/control/artwork/${artwork.id}/on`}>#</a>
                    <div className="artwork-name-inline">
                      {isDisabled && <span className="disabled-badge">DISABLED</span>}
                      {artwork.name}
                    </div>
                  </>
                ) : (
                  <>
                    <div className="manual-indent"></div>
                    <div className="manual-indent"></div>
                  </>
                )}
                <div className={`manual-device-content ${index % 2 === 0 ? 'bg-even' : 'bg-odd'}`}>
                  <DeviceBadge
                    device={device}
                    isExpanded={expandedDevice === device.id}
                    onClick={() => onToggleDevice(device.id)}
                  />
                  <div className="manual-device-buttons">
                    {device.actions && device.actions.map((action, idx) => (
                      <ConfirmButton key={action.name} className={`btn btn-action btn-action-${idx + 1} btn-sm`} onConfirm={() => onDeviceAction(device.id, action.name, device.name)} confirmText="Run?">{action.name}</ConfirmButton>
                    ))}
                    {device.device_type !== 'shell' && (
                      <div className="btn-group">
                        <ConfirmButton className="btn btn-on btn-sm" onConfirm={() => onDeviceControl(device.id, 'on', device.name)} confirmText="ON?">ON</ConfirmButton>
                        <ConfirmButton className="btn btn-off btn-sm" onConfirm={() => onDeviceControl(device.id, 'off', device.name)} confirmText="OFF?">OFF</ConfirmButton>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}

            {/* If no devices at all, show artwork name only (no ON/OFF buttons) */}
            {automationDevices.length === 0 && manualDevices.length === 0 && (
              <div className="artwork-inline-layout">
                <a className="api-link" href={`/api/control/artwork/${artwork.id}/on`}>#</a>
                <div className="artwork-name-inline">
                  {isDisabled && <span className="disabled-badge">DISABLED</span>}
                  {artwork.name}
                </div>
                <div className="artwork-devices-inline">
                  <span className="no-devices-label">No devices</span>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Device Accordions */}
      {sortedDevices.map(device => (
        <DeviceAccordion
          key={`accordion-${device.id}`}
          device={device}
          isOpen={expandedDevice === device.id}
          editMode={editMode}
          onControl={onDeviceControl}
          onAction={onDeviceAction}
          onEdit={onEditDevice}
          onDelete={onDeleteDevice}
        />
      ))}
    </div>
  );
}
