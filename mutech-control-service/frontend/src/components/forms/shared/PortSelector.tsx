/**
 * Port/outlet selector for NETIO and ANEL devices.
 */

interface PortSelectorProps {
  maxPorts: number;
  selectedPort: number;
  usedPorts: number[];
  onChange: (port: number) => void;
  label?: string;
}

export function PortSelector({
  maxPorts,
  selectedPort,
  usedPorts,
  onChange,
  label,
}: PortSelectorProps) {
  const ports = Array.from({ length: maxPorts }, (_, i) => i + 1);

  return (
    <div className="mb-3">
      <label className="form-label">{label || `Port Number (1-${maxPorts})`}</label>
      <div className="port-selector">
        {ports.map(portNum => {
          const isUsed = usedPorts.includes(portNum);
          return (
            <div
              key={portNum}
              className={`port-btn ${selectedPort === portNum ? 'active' : ''} ${isUsed ? 'used' : ''}`}
              onClick={() => !isUsed && onChange(portNum)}
              title={isUsed ? 'Port already in use' : ''}
            >
              {portNum}
            </div>
          );
        })}
      </div>
      {usedPorts.length > 0 && (
        <small className="form-text text-muted">
          Grayed out ports are already in use on this host
        </small>
      )}
    </div>
  );
}
