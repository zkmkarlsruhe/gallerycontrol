import { useEffect } from 'react';
import { useHostReachability, type ReachabilityStatus } from '../../hooks/useHostReachability';

interface AnelFormData {
  name: string;
  host: string;
  port: number;
  enabled: boolean;
  automation_enabled: boolean;
}

interface AnelFormProps {
  data: AnelFormData;
  onChange: (data: AnelFormData) => void;
  onReachabilityChange?: (status: ReachabilityStatus) => void;
}

export function AnelForm({ data, onChange, onReachabilityChange }: AnelFormProps) {
  const update = (field: keyof AnelFormData, value: string | number | boolean) => {
    onChange({ ...data, [field]: value });
  };

  // Check host reachability (port 80 for HTTP API)
  const { status: reachabilityStatus, error: reachabilityError } = useHostReachability(
    data.host,
    80,
    'anel'
  );

  // Notify parent of reachability changes
  useEffect(() => {
    onReachabilityChange?.(reachabilityStatus);
  }, [reachabilityStatus, onReachabilityChange]);

  return (
    <div className="device-form">
      <div className="form-section">
        <div className="section-title">Basic Information</div>
        <div className="mb-3">
          <label className="form-label">Device Name</label>
          <input
            type="text"
            className="form-control"
            placeholder="e.g. LED Panel 1"
            value={data.name}
            onChange={(e) => update('name', e.target.value)}
          />
        </div>
      </div>

      <div className="form-section">
        <div className="section-title">Connection</div>
        <div className="mb-3">
          <label className="form-label">Host / IP Address</label>
          <div className="host-input-wrapper">
            <input
              type="text"
              className={`form-control ${reachabilityStatus === 'unreachable' ? 'is-invalid' : reachabilityStatus === 'reachable' ? 'is-valid' : ''}`}
              placeholder="192.168.50.20"
              value={data.host}
              onChange={(e) => update('host', e.target.value)}
            />
            <span className={`reachability-indicator status-${reachabilityStatus}`} title={reachabilityError || ''}>
              {reachabilityStatus === 'checking' && <i className="bi bi-arrow-repeat spin"></i>}
              {reachabilityStatus === 'reachable' && <i className="bi bi-check-circle-fill"></i>}
              {reachabilityStatus === 'unreachable' && <i className="bi bi-x-circle-fill"></i>}
            </span>
          </div>
          {reachabilityStatus === 'unreachable' && reachabilityError ? (
            <small className="text-danger">{reachabilityError}</small>
          ) : (
            <small className="form-text text-muted">ANEL device on control network</small>
          )}
        </div>
        <div className="mb-3">
          <label className="form-label">Port Number (1-8)</label>
          <div className="port-selector">
            {[1, 2, 3, 4, 5, 6, 7, 8].map(portNum => (
              <div
                key={portNum}
                className={`port-btn ${data.port === portNum ? 'active' : ''}`}
                onClick={() => update('port', portNum)}
              >
                {portNum}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="form-section">
        <div className="section-title">Settings</div>
        <div className="form-check mb-3">
          <input
            className="form-check-input"
            type="checkbox"
            id="anel-enabled"
            checked={data.enabled}
            onChange={(e) => update('enabled', e.target.checked)}
          />
          <label className="form-check-label" htmlFor="anel-enabled">
            <strong>Device Enabled</strong>
          </label>
          <small className="d-block text-muted">When disabled, device is ignored by the system</small>
        </div>
        <div className="form-check mb-3">
          <input
            className="form-check-input"
            type="checkbox"
            id="anel-automation"
            checked={data.automation_enabled}
            onChange={(e) => update('automation_enabled', e.target.checked)}
          />
          <label className="form-check-label" htmlFor="anel-automation">
            <strong>Include in Automation</strong>
          </label>
          <small className="d-block text-muted">Included in bulk ON/OFF operations for artwork/exhibition</small>
        </div>
      </div>
    </div>
  );
}

export const defaultAnelData: AnelFormData = {
  name: '',
  host: '',
  port: 1,
  enabled: true,
  automation_enabled: true,
};
