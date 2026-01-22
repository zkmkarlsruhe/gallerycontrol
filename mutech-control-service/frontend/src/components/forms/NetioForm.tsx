import { useState, useEffect } from 'react';
import type { Credential } from '../../types';
import { useHostReachability, type ReachabilityStatus } from '../../hooks/useHostReachability';

// Generate NETIO hostname from number: 49 -> netzwerksteckdose-netio-049.zkm.de
function generateNetioHostname(num: string): string {
  const n = parseInt(num, 10);
  if (isNaN(n) || n < 1) return '';
  const padded = n.toString().padStart(3, '0');
  return `netzwerksteckdose-netio-${padded}.zkm.de`;
}

interface NetioFormData {
  name: string;
  host: string;
  port: number;
  credential_id: string;
  enabled: boolean;
  automation_enabled: boolean;
}

interface NetioFormProps {
  data: NetioFormData;
  onChange: (data: NetioFormData) => void;
  credentials?: Credential[];
  onReachabilityChange?: (status: ReachabilityStatus) => void;
  usedPorts?: number[];
}

export function NetioForm({ data, onChange, credentials = [], onReachabilityChange, usedPorts = [] }: NetioFormProps) {
  const [quickNum, setQuickNum] = useState('');

  const update = (field: keyof NetioFormData, value: string | number | boolean) => {
    onChange({ ...data, [field]: value });
  };

  const handleQuickHostname = () => {
    const hostname = generateNetioHostname(quickNum);
    if (hostname) {
      update('host', hostname);
      setQuickNum('');
    }
  };

  // Check host reachability (port 80 for HTTP API)
  const { status: reachabilityStatus, error: reachabilityError } = useHostReachability(
    data.host,
    80,
    'netio'
  );

  // Notify parent of reachability changes
  useEffect(() => {
    onReachabilityChange?.(reachabilityStatus);
  }, [reachabilityStatus, onReachabilityChange]);

  // Filter credentials by netio type
  const netioCredentials = credentials.filter(c => c.credential_type === 'netio');

  return (
    <div className="device-form">
      <div className="form-section">
        <div className="section-title">Basic Information</div>
        <div className="mb-3">
          <label className="form-label">Device Name</label>
          <input
            type="text"
            className="form-control"
            placeholder="e.g. Licht Galerie"
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
              placeholder="049"
              value={quickNum}
              onChange={(e) => setQuickNum(e.target.value.replace(/\D/g, ''))}
              onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), handleQuickHostname())}
              maxLength={3}
              title="Enter device number"
            />
            <button
              type="button"
              className="btn btn-sm btn-outline-secondary quick-apply-btn"
              onClick={handleQuickHostname}
              disabled={!quickNum}
              title={quickNum ? `Generate netzwerksteckdose-netio-${quickNum.padStart(3, '0')}.zkm.de` : 'Enter a number first'}
            >
              <i className="bi bi-arrow-right"></i>
            </button>
            <div className="host-input-wrapper flex-grow-1">
              <input
                type="text"
                className={`form-control ${reachabilityStatus === 'unreachable' ? 'is-invalid' : reachabilityStatus === 'reachable' ? 'is-valid' : ''}`}
                placeholder="netzwerksteckdose-netio-049.zkm.de"
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
          {reachabilityStatus === 'unreachable' && reachabilityError && (
            <small className="text-danger">{reachabilityError}</small>
          )}
        </div>
        <div className="mb-3">
          <label className="form-label">Port Number (1-3)</label>
          <div className="port-selector">
            {[1, 2, 3].map(portNum => {
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
            <option value="">Select...</option>
            {netioCredentials.map(cred => (
              <option key={cred.id} value={cred.id}>
                {cred.name} ({cred.username})
              </option>
            ))}
          </select>
          {netioCredentials.length === 0 ? (
            <small className="form-text text-danger">
              No NETIO credentials. Add in Credentials Store first.
            </small>
          ) : (
            <small className="form-text text-muted">
              Required for NETIO authentication
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
            id="netio-enabled"
            checked={data.enabled}
            onChange={(e) => update('enabled', e.target.checked)}
          />
          <label className="form-check-label" htmlFor="netio-enabled">
            <strong>Device Enabled</strong>
          </label>
          <small className="d-block text-muted">When disabled, device is ignored by the system</small>
        </div>
        <div className="form-check mb-3">
          <input
            className="form-check-input"
            type="checkbox"
            id="netio-automation"
            checked={data.automation_enabled}
            onChange={(e) => update('automation_enabled', e.target.checked)}
          />
          <label className="form-check-label" htmlFor="netio-automation">
            <strong>Include in Automation</strong>
          </label>
          <small className="d-block text-muted">Included in bulk ON/OFF operations for artwork/exhibition</small>
        </div>
      </div>
    </div>
  );
}

export const defaultNetioData: NetioFormData = {
  name: '',
  host: '',
  port: 1,
  credential_id: '',
  enabled: true,
  automation_enabled: true,
};
