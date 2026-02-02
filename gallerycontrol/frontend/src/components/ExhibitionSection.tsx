// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT
import type { Exhibition, Device, Artwork } from '../types';
import { ArtworkRow } from './ArtworkRow';
import { ConfirmButton } from './ui/ConfirmButton';
import { TouchSafeButton } from './ui/TouchSafeButton';

interface ExhibitionSectionProps {
  exhibition: Exhibition;
  editMode: boolean;
  expandedDevice: string | null;
  pendingStates: Map<string, 'on' | 'off'>;
  onToggleDevice: (deviceId: string) => void;
  onExhibitionControl: (exhibitionId: string, command: 'on' | 'off', exhibitionName: string) => void;
  onArtworkControl: (artworkId: string, command: 'on' | 'off', artworkName: string) => void;
  onDeviceControl: (deviceId: string, command: 'on' | 'off', deviceName: string) => void;
  onDeviceAction: (deviceId: string, actionName: string, deviceName: string) => void;
  onAddArtwork?: () => void;
  onEditExhibition?: (exhibition: Exhibition) => void;
  onDeleteExhibition?: (exhibitionId: string, exhibitionName: string) => void;
  onDeleteArtwork?: (artworkId: string, artworkName: string) => void;
  onEditArtwork?: (artwork: {
    id: string;
    name: string;
    enabled: boolean;
    timeslice_enabled: boolean;
    schedules_enabled: boolean;
    protection_config?: import('../types').ProtectionConfig | null;
  }) => void;
  onAddDevice?: (artworkId: string) => void;
  onEditDevice?: (device: Device) => void;
  onDeleteDevice?: (deviceId: string, deviceName: string) => void;
  onViewDeviceLogs?: (deviceId: string) => void;
  onOpenSchedules?: (id: string, type: 'exhibition' | 'artwork' | 'device', name: string) => void;
  onEditProtection?: (artwork: Artwork) => void;
  onOpenDisplayLinks?: (artwork: Artwork) => void;
}

export function ExhibitionSection({
  exhibition,
  editMode,
  expandedDevice,
  pendingStates,
  onToggleDevice,
  onExhibitionControl,
  onArtworkControl,
  onDeviceControl,
  onDeviceAction,
  onAddArtwork,
  onEditExhibition,
  onDeleteExhibition,
  onDeleteArtwork,
  onEditArtwork,
  onAddDevice,
  onEditDevice,
  onDeleteDevice,
  onViewDeviceLogs,
  onOpenSchedules,
  onEditProtection,
  onOpenDisplayLinks,
}: ExhibitionSectionProps) {
  const isDisabled = !exhibition.enabled;
  const visibleArtworks = (editMode ? exhibition.artworks : exhibition.artworks.filter(a => a.enabled))
    .slice()
    .sort((a, b) => a.name.localeCompare(b.name));

  return (
    <div className={`exhibition-section ${isDisabled ? 'disabled' : ''}`} id={`exhibition-${exhibition.id}`}>
      <div className="exhibition-header">
        <span>
          <a
            className="api-link"
            href={`/api/control/exhibition/${exhibition.id}/on`}
          >#</a>
          {isDisabled && <span className="disabled-badge">DISABLED</span>}
          {exhibition.name}
        </span>
        <div className="exhibition-header-controls">
          {editMode && (
            <>
              <button className="btn btn-add btn-sm me-2" onClick={onAddArtwork}>+ Artwork</button>
              {exhibition.schedules_enabled && (
                <button
                  className="btn btn-schedule btn-sm me-2"
                  onClick={() => onOpenSchedules?.(exhibition.id, 'exhibition', exhibition.name)}
                  title="Manage schedules"
                >
                  <i className="bi bi-calendar-event"></i>
                </button>
              )}
              <div className="btn-group me-2">
                <button className="btn btn-edit btn-sm" onClick={() => onEditExhibition?.(exhibition)} title="Edit"><i className="bi bi-pencil"></i></button>
                <ConfirmButton className="btn btn-delete btn-sm" onConfirm={() => onDeleteExhibition?.(exhibition.id, exhibition.name)} confirmText="Sure?" title="Delete"><i className="bi bi-trash"></i></ConfirmButton>
              </div>
            </>
          )}
          <div className="btn-group">
            <TouchSafeButton
              className="btn btn-on btn-sm"
              onClick={() => onExhibitionControl(exhibition.id, 'on', exhibition.name)}
            >
              ON
            </TouchSafeButton>
            <TouchSafeButton
              className="btn btn-off btn-sm"
              onClick={() => onExhibitionControl(exhibition.id, 'off', exhibition.name)}
            >
              OFF
            </TouchSafeButton>
          </div>
        </div>
      </div>

      <div className="artwork-table">
        {visibleArtworks.map((artwork, artworkIndex) => (
          <ArtworkRow
            key={artwork.id}
            artwork={artwork}
            isAlternate={artworkIndex % 2 === 1}
            editMode={editMode}
            expandedDevice={expandedDevice}
            pendingStates={pendingStates}
            onToggleDevice={onToggleDevice}
            onArtworkControl={onArtworkControl}
            onDeviceControl={onDeviceControl}
            onDeviceAction={onDeviceAction}
            onAddDevice={onAddDevice ? () => onAddDevice(artwork.id) : undefined}
            onDeleteArtwork={onDeleteArtwork}
            onEditArtwork={onEditArtwork ? () => onEditArtwork({
              id: artwork.id,
              name: artwork.name,
              enabled: artwork.enabled,
              timeslice_enabled: artwork.timeslice_enabled,
              schedules_enabled: artwork.schedules_enabled,
              protection_config: artwork.protection_config,
            }) : undefined}
            onEditDevice={onEditDevice}
            onDeleteDevice={onDeleteDevice}
            onViewDeviceLogs={onViewDeviceLogs}
            onOpenSchedules={onOpenSchedules}
            onEditProtection={onEditProtection}
            onOpenDisplayLinks={onOpenDisplayLinks}
          />
        ))}
      </div>
    </div>
  );
}
