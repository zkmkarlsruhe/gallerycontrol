import { useState } from 'react';
import type { Credential, ShellTemplate } from '../../types';

interface ShellAction {
  name: string;
  cmd: string;
}

interface ShellFormData {
  name: string;
  credential_id: string;
  onoff_mode: boolean;
  automation_enabled: boolean;
  status_cmd: string;
  on_pattern: string;
  off_pattern: string;
  on_cmd: string;
  off_cmd: string;
  actions: ShellAction[];
  enabled: boolean;
}

interface ShellFormProps {
  data: ShellFormData;
  onChange: (data: ShellFormData) => void;
  credentials?: Credential[];
  templates?: ShellTemplate[];
}

interface TestResult {
  success: boolean;
  exit_code: number | null;
  stdout: string;
  stderr: string;
  duration_ms: number;
  error: string | null;
  commandLabel: string;
}

export function ShellForm({ data, onChange, credentials = [], templates = [] }: ShellFormProps) {
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [testingCommand, setTestingCommand] = useState<string | null>(null);
  const [outputExpanded, setOutputExpanded] = useState(true);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>('');

  const update = (field: keyof ShellFormData, value: string | boolean | ShellAction[]) => {
    onChange({ ...data, [field]: value });
  };

  const applyTemplate = () => {
    const template = templates.find(t => t.id === selectedTemplateId);
    if (!template) return;

    onChange({
      ...data,
      onoff_mode: template.onoff_mode,
      status_cmd: template.status_command || '',
      on_pattern: template.status_on_pattern || '',
      off_pattern: template.status_off_pattern || '',
      on_cmd: template.on_command || '',
      off_cmd: template.off_command || '',
      actions: template.actions?.length ? template.actions : [{ name: '', cmd: '' }],
      automation_enabled: template.onoff_mode, // Enable automation for ON/OFF templates
    });
    setSelectedTemplateId('');
  };

  const updateAction = (index: number, field: 'name' | 'cmd', value: string) => {
    const newActions = [...data.actions];
    newActions[index] = { ...newActions[index], [field]: value };
    update('actions', newActions);
  };

  const addAction = () => {
    update('actions', [...data.actions, { name: '', cmd: '' }]);
  };

  const removeAction = (index: number) => {
    update('actions', data.actions.filter((_, i) => i !== index));
  };

  const testCommand = async (command: string, label: string) => {
    if (!command.trim()) return;

    setTestingCommand(label);
    setTestResult(null);

    try {
      const response = await fetch('/api/admin/shell/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command, timeout: 5 }),
      });

      const result = await response.json();
      setTestResult({
        ...result,
        commandLabel: label,
      });
      setOutputExpanded(true);
    } catch (err) {
      setTestResult({
        success: false,
        exit_code: null,
        stdout: '',
        stderr: '',
        duration_ms: 0,
        error: err instanceof Error ? err.message : 'Unknown error',
        commandLabel: label,
      });
      setOutputExpanded(true);
    } finally {
      setTestingCommand(null);
    }
  };

  // Filter credentials by shell type
  const shellCredentials = credentials.filter(c => c.credential_type === 'shell');
  const selectedCredential = shellCredentials.find(c => c.id === data.credential_id);

  const TestButton = ({ command, label }: { command: string; label: string }) => (
    <button
      type="button"
      className="btn btn-outline-secondary btn-sm"
      onClick={() => testCommand(command, label)}
      disabled={!command.trim() || testingCommand !== null}
      title={command.trim() ? `Test ${label}` : 'Enter a command first'}
    >
      {testingCommand === label ? (
        <><i className="bi bi-hourglass-split"></i> Testing...</>
      ) : (
        <><i className="bi bi-play-fill"></i> Test</>
      )}
    </button>
  );

  return (
    <div className="device-form">
      {/* Template Selector */}
      {templates.length > 0 && (
        <div className="form-section template-selector">
          <div className="section-title">
            <i className="bi bi-bookmark me-1"></i> Load from Template
          </div>
          <div className="input-group">
            <select
              className="form-select"
              value={selectedTemplateId}
              onChange={(e) => setSelectedTemplateId(e.target.value)}
            >
              <option value="">Select a template...</option>
              {templates.map(tmpl => (
                <option key={tmpl.id} value={tmpl.id}>
                  {tmpl.name} {tmpl.onoff_mode ? '(ON/OFF)' : '(Custom)'}{tmpl.description ? ` - ${tmpl.description}` : ''}
                </option>
              ))}
            </select>
            <button
              type="button"
              className="btn btn-primary"
              onClick={applyTemplate}
              disabled={!selectedTemplateId}
            >
              Apply
            </button>
          </div>
          <small className="form-text text-muted">
            Templates pre-fill command fields. Device name and credentials are not affected.
          </small>
        </div>
      )}

      <div className="form-section">
        <div className="section-title">Basic Information</div>
        <div className="mb-3">
          <label className="form-label">Device Name</label>
          <input
            type="text"
            className="form-control"
            placeholder="e.g. Media Server"
            value={data.name}
            onChange={(e) => update('name', e.target.value)}
          />
        </div>
      </div>

      {/* Credentials Section */}
      <div className="form-section">
        <div className="section-title">Credentials (Optional)</div>
        <div className="mb-3">
          <label className="form-label">Select Credentials</label>
          <select
            className="form-select"
            value={data.credential_id}
            onChange={(e) => update('credential_id', e.target.value)}
          >
            <option value="">No credentials</option>
            {shellCredentials.map(cred => (
              <option key={cred.id} value={cred.id}>
                {cred.name} ({cred.username})
              </option>
            ))}
          </select>
          {shellCredentials.length === 0 ? (
            <small className="form-text text-muted">
              Add Shell credentials in the Credentials Store to use here
            </small>
          ) : data.credential_id && selectedCredential ? (
            <div className="info-box mt-2">
              <strong>Placeholders available:</strong>
              <ul className="mb-0 mt-1">
                <li><code>{'{{user}}'}</code> - will be replaced with <strong>{selectedCredential.username}</strong></li>
                <li><code>{'{{password}}'}</code> - will be replaced with the password</li>
              </ul>
            </div>
          ) : null}
        </div>
      </div>

      <div className="form-section">
        <div className="section-title">Command Mode</div>
        <div className="shell-mode-switch">
          <div className="form-check form-switch mb-2">
            <input
              className="form-check-input"
              type="checkbox"
              id="shell-onoff-mode"
              checked={data.onoff_mode}
              onChange={(e) => update('onoff_mode', e.target.checked)}
            />
            <label className="form-check-label" htmlFor="shell-onoff-mode">
              <strong>ON/OFF Control Mode</strong>
            </label>
          </div>
          <small className="text-muted">
            {data.onoff_mode
              ? 'System can turn device ON/OFF and detect current state'
              : 'Manual custom commands only - no automatic state detection'
            }
          </small>
        </div>

        {/* ON/OFF Mode */}
        {data.onoff_mode && (
          <div id="shell-onoff">
            <div className="command-input-group">
              <label className="form-label">
                <strong>Status Command</strong> <span className="text-danger">(required)</span>
              </label>
              <div className="input-group mb-2">
                <input
                  type="text"
                  className="form-control"
                  placeholder="systemctl status myapp"
                  value={data.status_cmd}
                  onChange={(e) => update('status_cmd', e.target.value)}
                />
                <TestButton command={data.status_cmd} label="Status" />
              </div>
              <small className="form-text text-muted">Command to check if device is ON or OFF</small>
              <div className="row mt-2">
                <div className="col-md-6">
                  <label className="form-label small">ON Pattern (regex)</label>
                  <input
                    type="text"
                    className="form-control form-control-sm"
                    placeholder="active \(running\)"
                    value={data.on_pattern}
                    onChange={(e) => update('on_pattern', e.target.value)}
                  />
                  <small className="form-text text-muted">Regex to detect ON state</small>
                </div>
                <div className="col-md-6">
                  <label className="form-label small">OFF Pattern (regex)</label>
                  <input
                    type="text"
                    className="form-control form-control-sm"
                    placeholder="inactive"
                    value={data.off_pattern}
                    onChange={(e) => update('off_pattern', e.target.value)}
                  />
                  <small className="form-text text-muted">Regex to detect OFF state</small>
                </div>
              </div>
            </div>

            <div className="command-input-group">
              <label className="form-label">
                <strong>ON Command</strong> <span className="text-danger">(required)</span>
              </label>
              <div className="input-group mb-2">
                <input
                  type="text"
                  className="form-control"
                  placeholder="systemctl start myapp"
                  value={data.on_cmd}
                  onChange={(e) => update('on_cmd', e.target.value)}
                />
                <TestButton command={data.on_cmd} label="ON" />
              </div>
              <small className="form-text text-muted">Command to turn device ON</small>
            </div>

            <div className="command-input-group">
              <label className="form-label">
                <strong>OFF Command</strong> <span className="text-danger">(required)</span>
              </label>
              <div className="input-group mb-2">
                <input
                  type="text"
                  className="form-control"
                  placeholder="systemctl stop myapp"
                  value={data.off_cmd}
                  onChange={(e) => update('off_cmd', e.target.value)}
                />
                <TestButton command={data.off_cmd} label="OFF" />
              </div>
              <small className="form-text text-muted">Command to turn device OFF</small>
            </div>
          </div>
        )}

        {/* Custom Commands Mode */}
        {!data.onoff_mode && (
          <div id="shell-custom">
            <div className="alert alert-info">
              <strong>Custom Commands Mode:</strong> Define custom commands with labels. Status command checks reachability.
            </div>

            <div className="command-input-group">
              <label className="form-label">
                <strong>Status Command</strong> <span className="text-danger">(required)</span>
              </label>
              <div className="input-group mb-2">
                <input
                  type="text"
                  className="form-control"
                  placeholder="ping -c 1 server.local"
                  value={data.status_cmd}
                  onChange={(e) => update('status_cmd', e.target.value)}
                />
                <TestButton command={data.status_cmd} label="Status" />
              </div>
              <small className="form-text text-muted">Command to check device state (exit 0 = reachable, patterns determine ON/OFF)</small>
              <div className="row mt-2">
                <div className="col-md-6">
                  <label className="form-label small">ON Pattern (regex)</label>
                  <input
                    type="text"
                    className="form-control form-control-sm"
                    placeholder="online|running|true"
                    value={data.on_pattern}
                    onChange={(e) => update('on_pattern', e.target.value)}
                  />
                  <small className="form-text text-muted">Regex to detect ON state</small>
                </div>
                <div className="col-md-6">
                  <label className="form-label small">OFF Pattern (regex)</label>
                  <input
                    type="text"
                    className="form-control form-control-sm"
                    placeholder="offline|stopped|false"
                    value={data.off_pattern}
                    onChange={(e) => update('off_pattern', e.target.value)}
                  />
                  <small className="form-text text-muted">Regex to detect OFF state</small>
                </div>
              </div>
            </div>

            <div id="custom-commands-container">
              {data.actions.map((action, index) => (
                <div key={index} className="command-input-group">
                  {data.actions.length > 1 && (
                    <button
                      type="button"
                      className="btn btn-sm btn-delete remove-btn"
                      onClick={() => removeAction(index)}
                    >
                      <i className="bi bi-x"></i>
                    </button>
                  )}
                  <label className="form-label"><strong>Command {index + 1}</strong></label>
                  <input
                    type="text"
                    className="form-control mb-2"
                    placeholder="Button label (e.g. Restart Service)"
                    value={action.name}
                    onChange={(e) => updateAction(index, 'name', e.target.value)}
                  />
                  <div className="input-group mb-2">
                    <input
                      type="text"
                      className="form-control"
                      placeholder="Command"
                      value={action.cmd}
                      onChange={(e) => updateAction(index, 'cmd', e.target.value)}
                    />
                    <TestButton command={action.cmd} label={action.name || `Action ${index + 1}`} />
                  </div>
                </div>
              ))}
            </div>

            <button type="button" className="btn btn-add btn-sm" onClick={addAction}>
              <i className="bi bi-plus-circle"></i> Add Another Command
            </button>
          </div>
        )}
      </div>

      {/* Test Output Panel */}
      {testResult && (
        <div className="form-section test-output-section">
          <div
            className="section-title d-flex justify-content-between align-items-center"
            style={{ cursor: 'pointer' }}
            onClick={() => setOutputExpanded(!outputExpanded)}
          >
            <span>
              <i className={`bi bi-chevron-${outputExpanded ? 'down' : 'right'} me-2`}></i>
              Test Output: {testResult.commandLabel}
            </span>
            <span className={`badge ${testResult.success ? 'bg-success' : 'bg-danger'}`}>
              {testResult.success ? 'Success' : 'Failed'}
            </span>
          </div>

          {outputExpanded && (
            <div className="test-output-content">
              <div className="test-output-meta mb-2">
                <span className="me-3">
                  <strong>Exit Code:</strong>{' '}
                  <code className={testResult.exit_code === 0 ? 'text-success' : 'text-danger'}>
                    {testResult.exit_code ?? 'N/A'}
                  </code>
                </span>
                <span>
                  <strong>Duration:</strong> <code>{testResult.duration_ms}ms</code>
                </span>
              </div>

              {testResult.error && (
                <div className="test-output-block error">
                  <div className="test-output-label">Error</div>
                  <pre>{testResult.error}</pre>
                </div>
              )}

              {testResult.stdout && (
                <div className="test-output-block stdout">
                  <div className="test-output-label">stdout</div>
                  <pre>{testResult.stdout}</pre>
                </div>
              )}

              {testResult.stderr && (
                <div className="test-output-block stderr">
                  <div className="test-output-label">stderr</div>
                  <pre>{testResult.stderr}</pre>
                </div>
              )}

              {!testResult.stdout && !testResult.stderr && !testResult.error && (
                <div className="text-muted">
                  <em>No output</em>
                </div>
              )}

              <button
                type="button"
                className="btn btn-sm btn-outline-secondary mt-2"
                onClick={() => setTestResult(null)}
              >
                <i className="bi bi-x-circle"></i> Clear Output
              </button>
            </div>
          )}
        </div>
      )}

      <div className="form-section">
        <div className="section-title">Settings</div>
        <div className="form-check mb-3">
          <input
            className="form-check-input"
            type="checkbox"
            id="shell-enabled"
            checked={data.enabled}
            onChange={(e) => update('enabled', e.target.checked)}
          />
          <label className="form-check-label" htmlFor="shell-enabled">
            <strong>Device Enabled</strong>
          </label>
          <small className="d-block text-muted">When disabled, device is ignored by the system</small>
        </div>
        {data.onoff_mode && (
          <div className="form-check mb-3">
            <input
              className="form-check-input"
              type="checkbox"
              id="shell-automation"
              checked={data.automation_enabled}
              onChange={(e) => update('automation_enabled', e.target.checked)}
            />
            <label className="form-check-label" htmlFor="shell-automation">
              <strong>Include in Automation</strong>
            </label>
            <small className="d-block text-muted">Included in bulk ON/OFF operations for artwork/exhibition</small>
          </div>
        )}
        {!data.onoff_mode && (
          <small className="d-block text-muted">
            <i className="bi bi-info-circle"></i> Custom command devices are not included in automation (no ON/OFF state)
          </small>
        )}
      </div>
    </div>
  );
}

export const defaultShellData: ShellFormData = {
  name: '',
  credential_id: '',
  onoff_mode: true,
  automation_enabled: true,
  status_cmd: '',
  on_pattern: '',
  off_pattern: '',
  on_cmd: '',
  off_cmd: '',
  actions: [{ name: '', cmd: '' }],
  enabled: true,
};
