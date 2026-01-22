/**
 * Shared settings section for device forms.
 * Contains enabled and automation checkboxes.
 */

interface SettingsSectionProps {
  deviceType: string;
  enabled: boolean;
  automationEnabled: boolean;
  onEnabledChange: (enabled: boolean) => void;
  onAutomationChange: (enabled: boolean) => void;
}

export function SettingsSection({
  deviceType,
  enabled,
  automationEnabled,
  onEnabledChange,
  onAutomationChange,
}: SettingsSectionProps) {
  const enabledId = `${deviceType}-enabled`;
  const automationId = `${deviceType}-automation`;

  return (
    <div className="form-section">
      <div className="section-title">Settings</div>
      <div className="form-check mb-3">
        <input
          className="form-check-input"
          type="checkbox"
          id={enabledId}
          checked={enabled}
          onChange={(e) => onEnabledChange(e.target.checked)}
        />
        <label className="form-check-label" htmlFor={enabledId}>
          <strong>Device Enabled</strong>
        </label>
        <small className="d-block text-muted">When disabled, device is ignored by the system</small>
      </div>
      <div className="form-check mb-3">
        <input
          className="form-check-input"
          type="checkbox"
          id={automationId}
          checked={automationEnabled}
          onChange={(e) => onAutomationChange(e.target.checked)}
        />
        <label className="form-check-label" htmlFor={automationId}>
          <strong>Include in Automation</strong>
        </label>
        <small className="d-block text-muted">Included in bulk ON/OFF operations for artwork/exhibition</small>
      </div>
    </div>
  );
}
