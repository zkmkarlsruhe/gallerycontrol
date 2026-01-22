import { useState, useEffect } from 'react';
import type { Credential } from '../../types';
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
  credential_id: string;
  enabled: boolean;
  automation_enabled: boolean;
}

interface AnelFormProps {
  data: AnelFormData;
  onChange: (data: AnelFormData) => void;
  credentials?: Credential[];
  onReachabilityChange?: (status: ReachabilityStatus) => void;
  usedPorts?: number[];
}

export function AnelForm({ data, onChange, credentials = [], onReachabilityChange, usedPorts = [] }: AnelFormProps) {
  const [quickNum, setQuickNum] = useState('');

  // Filter credentials by anel type
  const anelCredentials = credentials.filter(c => c.credential_type === 'anel');

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
          <div className="hostname-inline-entry">
            <input
              type="text"
              className="form-control form-control-sm quick-num-input"
              placeholder="21"
              value={quickNum}
              onChange={(e) => setQuickNum(e.target.value.replace(/\D/g, ''))}
              onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), handleQuickHostname())}
              maxLength={2}
              title="Enter device number"
            />
            <button
              type="button"
              className="btn btn-sm btn-outline-secondary quick-apply-btn"
              onClick={handleQuickHostname}
              disabled={!quickNum}
              title={quickNum ? `Generate netzwerksteckdose${quickNum}.zkm.de` : 'Enter a number first'}
            >
              <i className="bi bi-arrow-right"></i>
            </button>
            <div className="host-input-wrapper flex-grow-1">
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
            {[1, 2, 3, 4, 5, 6, 7, 8].map(portNum => {
              const isUsed = usedPorts.includes(portNum);
              return (
                <div
                  key={portNum}
                  className={`port-btn ${data.port === portNum ? 'active' : ''} ${isUsed ? 'used' : ''}`}
                  onClick={() => !isUsed && update('port', portNum)}
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
        <div className="mb-3">
          <label className="form-label">Credentials</label>
          <select
            className="form-select"
            value={data.credential_id}
            onChange={(e) => update('credential_id', e.target.value)}
          >
            <option value="">Default (admin/anel)</option>
            {anelCredentials.map(cred => (
              <option key={cred.id} value={cred.id}>
                {cred.name} ({cred.username})
              </option>
            ))}
          </select>
          {anelCredentials.length === 0 ? (
            <small className="form-text text-muted">
              Add ANEL credentials in the Credentials Store if needed
            </small>
          ) : (
            <small className="form-text text-muted">
              For ANEL devices with custom login
            </small>
          )}
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
  credential_id: '',
  enabled: true,
  automation_enabled: true,
};
