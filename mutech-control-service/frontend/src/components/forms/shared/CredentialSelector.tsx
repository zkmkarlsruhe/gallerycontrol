// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT
/**
 * Credential selector for device forms.
 */

import type { Credential } from '../../../types';

interface CredentialSelectorProps {
  credentials: Credential[];
  credentialType: string;
  selectedId: string;
  onChange: (credentialId: string) => void;
  emptyLabel?: string;
  emptyHelpText?: string;
  helpText?: string;
  showUsername?: boolean;
}

export function CredentialSelector({
  credentials,
  credentialType,
  selectedId,
  onChange,
  emptyLabel = 'None',
  emptyHelpText,
  helpText,
  showUsername = false,
}: CredentialSelectorProps) {
  const filteredCredentials = credentials.filter(c => c.credential_type === credentialType);

  return (
    <div className="mb-3">
      <label className="form-label">Credentials</label>
      <select
        className="form-select"
        value={selectedId}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">{emptyLabel}</option>
        {filteredCredentials.map(cred => (
          <option key={cred.id} value={cred.id}>
            {cred.name}{showUsername && cred.username ? ` (${cred.username})` : ''}
          </option>
        ))}
      </select>
      {filteredCredentials.length === 0 && emptyHelpText && (
        <small className="form-text text-danger">{emptyHelpText}</small>
      )}
      {filteredCredentials.length > 0 && helpText && (
        <small className="form-text text-muted">{helpText}</small>
      )}
      {filteredCredentials.length === 0 && !emptyHelpText && helpText && (
        <small className="form-text text-muted">{helpText}</small>
      )}
    </div>
  );
}
