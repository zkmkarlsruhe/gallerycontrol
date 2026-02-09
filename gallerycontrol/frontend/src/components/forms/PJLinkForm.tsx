// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT
import { useEffect } from 'react';
import type { Credential } from '../../types';
import { useHostReachability, type ReachabilityStatus } from '../../hooks/useHostReachability';
import { SettingsSection, ReachabilityIndicator, getHostInputClass, CredentialSelector } from './shared';

interface PJLinkFormData {
  name: string;
  host: string;
  port: number;
  credential_id: string;
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
                  className={`form-control ${getHostInputClass(reachabilityStatus)}`}
                  placeholder="192.168.10.45"
                  value={data.host}
                  onChange={(e) => update('host', e.target.value)}
                />
                <ReachabilityIndicator status={reachabilityStatus} error={reachabilityError} />
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
        <CredentialSelector
          credentials={credentials}
          credentialType="pjlink"
          selectedId={data.credential_id}
          onChange={(id) => update('credential_id', id)}
          emptyLabel="None (no password)"
          helpText="Add PJLink credentials in the Credentials Store"
        />
      </div>

      <SettingsSection
        deviceType="pjlink"
        enabled={data.enabled}
        automationEnabled={data.automation_enabled}
        onEnabledChange={(enabled) => update('enabled', enabled)}
        onAutomationChange={(enabled) => update('automation_enabled', enabled)}
      />
    </div>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export const defaultPJLinkData: PJLinkFormData = {
  name: '',
  host: '',
  port: 4352,
  credential_id: '',
  enabled: true,
  automation_enabled: true,
};
