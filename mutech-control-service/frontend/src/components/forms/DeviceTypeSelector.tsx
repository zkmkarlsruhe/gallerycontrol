// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT
export type DeviceType = 'pjlink' | 'netio' | 'anel' | 'shell';

interface DeviceTypeSelectorProps {
  selectedType: DeviceType;
  onSelect: (type: DeviceType) => void;
}

const deviceTypes: { type: DeviceType; icon: string; label: string }[] = [
  { type: 'pjlink', icon: 'bi-projector', label: 'PJLink' },
  { type: 'netio', icon: 'bi-plug', label: 'NETIO' },
  { type: 'anel', icon: 'bi-outlet', label: 'ANEL' },
  { type: 'shell', icon: 'bi-terminal', label: 'Shell' },
];

export function DeviceTypeSelector({ selectedType, onSelect }: DeviceTypeSelectorProps) {
  return (
    <div className="device-type-selector">
      {deviceTypes.map(({ type, icon, label }) => (
        <div
          key={type}
          className={`device-type-btn ${selectedType === type ? 'active' : ''}`}
          onClick={() => onSelect(type)}
        >
          <i className={`bi ${icon}`}></i>
          <div>{label}</div>
        </div>
      ))}
    </div>
  );
}
