// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT
import { useState, useEffect } from 'react';
import type { Credential } from '../../types';
import { useHostReachability, type ReachabilityStatus } from '../../hooks/useHostReachability';
import { SettingsSection, ReachabilityIndicator, getHostInputClass, CredentialSelector, PortSelector } from './shared';

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
                className={`form-control ${getHostInputClass(reachabilityStatus)}`}
                placeholder="netzwerksteckdose21.zkm.de"
                value={data.host}
                onChange={(e) => update('host', e.target.value)}
              />
              <ReachabilityIndicator status={reachabilityStatus} error={reachabilityError} />
            </div>
          </div>
          {reachabilityStatus === 'unreachable' && reachabilityError ? (
            <small className="text-danger">{reachabilityError}</small>
          ) : (
            <small className="form-text text-muted">ANEL device on control network</small>
          )}
        </div>
        <PortSelector
          maxPorts={8}
          selectedPort={data.port}
          usedPorts={usedPorts}
          onChange={(port) => update('port', port)}
          label="Port Number (1-8)"
        />
        <CredentialSelector
          credentials={credentials}
          credentialType="anel"
          selectedId={data.credential_id}
          onChange={(id) => update('credential_id', id)}
          emptyLabel="Default (admin/anel)"
          helpText="For ANEL devices with custom login"
          showUsername
        />
      </div>

      <SettingsSection
        deviceType="anel"
        enabled={data.enabled}
        automationEnabled={data.automation_enabled}
        onEnabledChange={(enabled) => update('enabled', enabled)}
        onAutomationChange={(enabled) => update('automation_enabled', enabled)}
      />
    </div>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export const defaultAnelData: AnelFormData = {
  name: '',
  host: '',
  port: 1,
  credential_id: '',
  enabled: true,
  automation_enabled: true,
};
