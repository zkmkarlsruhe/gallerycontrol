import { useEffect } from 'react';
import type { Credential } from '../../types';
import { useHostReachability, type ReachabilityStatus } from '../../hooks/useHostReachability';

interface PJLinkFormData {
  name: string;
  host: string;
  port: number;
  credential_id: string; // empty string = no password
  enabled: boolean;
  automation_enabled: boolean;
}

interface PJLinkFormProps {
  data: PJLinkFormData;
  onChange: (data: PJLinkFormData) => void;
  credentials?: Credential[];
  onReachabilityChange?: (status: ReachabilityStatus) => void;
}

export function PJLinkForm({ data, onChange, credentials = [], onReachabilityChange }: PJLinkFormProps) {
  const update = (field: keyof PJLinkFormData, value: string | number | boolean) => {
    onChange({ ...data, [field]: value });
  };

  // Check host reachability
  const { status: reachabilityStatus, error: reachabilityError } = useHostReachability(
    data.host,
    data.port,
    'pjlink'
  );

  // Notify parent of reachability changes
  useEffect(() => {
    onReachabilityChange?.(reachabilityStatus);
  }, [reachabilityStatus, onReachabilityChange]);

  // Filter credentials by pjlink type
  const pjlinkCredentials = credentials.filter(c => c.credential_type === 'pjlink');

  return (
    <div className="device-form">
      <div className="form-section">
        <div className="section-title">Basic Information</div>
        <div className="mb-3">
          <label className="form-label">Device Name</label>
          <input
            type="text"
            className="form-control"
            placeholder="e.g. Projektor Links"
            value={data.name}
            onChange={(e) => update('name', e.target.value)}
          />
        </div>
      </div>

      <div className="form-section">
        <div className="section-title">Connection</div>
        <div className="row">
          <div className="col-md-8">
            <div className="mb-3">
              <label className="form-label">Host / IP Address</label>
              <div className="host-input-wrapper">
                <input
                  type="text"
                  className={`form-control ${reachabilityStatus === 'unreachable' ? 'is-invalid' : reachabilityStatus === 'reachable' ? 'is-valid' : ''}`}
                  placeholder="192.168.10.45"
                  value={data.host}
                  onChange={(e) => update('host', e.target.value)}
                />
                <span className={`reachability-indicator status-${reachabilityStatus}`} title={reachabilityError || ''}>
                  {reachabilityStatus === 'checking' && <i className="bi bi-arrow-repeat spin"></i>}
                  {reachabilityStatus === 'reachable' && <i className="bi bi-check-circle-fill"></i>}
                  {reachabilityStatus === 'unreachable' && <i className="bi bi-x-circle-fill"></i>}
                </span>
              </div>
              {reachabilityStatus === 'unreachable' && reachabilityError && (
                <small className="text-danger">{reachabilityError}</small>
              )}
            </div>
          </div>
          <div className="col-md-4">
            <div className="mb-3">
              <label className="form-label">Port</label>
              <input
                type="number"
                className="form-control"
                placeholder="4352"
                value={data.port}
                onChange={(e) => update('port', parseInt(e.target.value) || 4352)}
              />
              <small className="form-text text-muted">Default: 4352</small>
            </div>
          </div>
        </div>
        <div className="mb-3">
          <label className="form-label">Credentials</label>
          <select
            className="form-select"
            value={data.credential_id}
            onChange={(e) => update('credential_id', e.target.value)}
          >
            <option value="">None (no password)</option>
            {pjlinkCredentials.map(cred => (
              <option key={cred.id} value={cred.id}>
                {cred.name}
              </option>
            ))}
          </select>
          {pjlinkCredentials.length === 0 && (
            <small className="form-text text-muted">
              Add PJLink credentials in the Credentials Store
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
            id="pjlink-enabled"
            checked={data.enabled}
            onChange={(e) => update('enabled', e.target.checked)}
          />
          <label className="form-check-label" htmlFor="pjlink-enabled">
            <strong>Device Enabled</strong>
          </label>
          <small className="d-block text-muted">When disabled, device is ignored by the system</small>
        </div>
        <div className="form-check mb-3">
          <input
            className="form-check-input"
            type="checkbox"
            id="pjlink-automation"
            checked={data.automation_enabled}
            onChange={(e) => update('automation_enabled', e.target.checked)}
          />
          <label className="form-check-label" htmlFor="pjlink-automation">
            <strong>Include in Automation</strong>
          </label>
          <small className="d-block text-muted">Included in bulk ON/OFF operations for artwork/exhibition</small>
        </div>
      </div>
    </div>
  );
}

export const defaultPJLinkData: PJLinkFormData = {
  name: '',
  host: '',
  port: 4352,
  credential_id: '',
  enabled: true,
  automation_enabled: true,
};
