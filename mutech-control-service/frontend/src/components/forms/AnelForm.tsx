import { useState, useEffect } from 'react';
import { useHostReachability, type ReachabilityStatus } from '../../hooks/useHostReachability';

// Generate ANEL hostname from number: 21 -> netzwerksteckdose21.zkm.de
function generateAnelHostname(num: string): string {
  const n = parseInt(num, 10);
  if (isNaN(n) || n < 1) return '';
  return `netzwerksteckdose${n}.zkm.de`;
}

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
  const [quickNum, setQuickNum] = useState('');

  const update = (field: keyof AnelFormData, value: string | number | boolean) => {
    onChange({ ...data, [field]: value });
  };

  const handleQuickHostname = () => {
    const hostname = generateAnelHostname(quickNum);
    if (hostname) {
      update('host', hostname);
      setQuickNum('');
    }
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
          <div className="hostname-quick-entry">
            <input
              type="text"
              className="form-control form-control-sm quick-num-input"
              placeholder="21"
              value={quickNum}
              onChange={(e) => setQuickNum(e.target.value.replace(/\D/g, ''))}
              onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), handleQuickHostname())}
              maxLength={2}
            />
            <button
              type="button"
              className="btn btn-sm btn-outline-secondary"
              onClick={handleQuickHostname}
              disabled={!quickNum}
              title="Generate hostname from number"
            >
              <i className="bi bi-arrow-right"></i>
            </button>
            <span className="quick-hint">anel-{quickNum || '__'}</span>
          </div>
          <div className="host-input-wrapper">
            <input
              type="text"
              className={`form-control ${reachabilityStatus === 'unreachable' ? 'is-invalid' : reachabilityStatus === 'reachable' ? 'is-valid' : ''}`}
              placeholder="netzwerksteckdose21.zkm.de"
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
