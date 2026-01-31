// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT
import { useState, useEffect } from 'react';
import type { Credential } from '../../types';
import { useHostReachability, type ReachabilityStatus } from '../../hooks/useHostReachability';
import { SettingsSection, ReachabilityIndicator, getHostInputClass, CredentialSelector, PortSelector } from './shared';

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
                className={`form-control ${getHostInputClass(reachabilityStatus)}`}
                placeholder="netzwerksteckdose-netio-049.zkm.de"
                value={data.host}
                onChange={(e) => update('host', e.target.value)}
              />
              <ReachabilityIndicator status={reachabilityStatus} error={reachabilityError} />
            </div>
          </div>
          {reachabilityStatus === 'unreachable' && reachabilityError && (
            <small className="text-danger">{reachabilityError}</small>
          )}
        </div>
        <PortSelector
          maxPorts={3}
          selectedPort={data.port}
          usedPorts={usedPorts}
          onChange={(port) => update('port', port)}
          label="Port Number (1-3)"
        />
        <CredentialSelector
          credentials={credentials}
          credentialType="netio"
          selectedId={data.credential_id}
          onChange={(id) => update('credential_id', id)}
          emptyLabel="Select..."
          emptyHelpText="No NETIO credentials. Add in Credentials Store first."
          helpText="Required for NETIO authentication"
          showUsername
        />
      </div>

      <SettingsSection
        deviceType="netio"
        enabled={data.enabled}
        automationEnabled={data.automation_enabled}
        onEnabledChange={(enabled) => update('enabled', enabled)}
        onAutomationChange={(enabled) => update('automation_enabled', enabled)}
      />
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
