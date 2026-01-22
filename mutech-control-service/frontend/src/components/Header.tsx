interface HeaderProps {
  editMode: boolean;
  onEditModeChange: (enabled: boolean) => void;
  onOpenCredentials?: () => void;
  onOpenShellLibrary?: () => void;
  onOpenEmailInventory?: () => void;
  onOpenAdmin?: () => void;
  onOpenLogs?: () => void;
  onOpenTimeline?: () => void;
  onOpenAssets?: () => void;
  showingLogs?: boolean;
  showingTimeline?: boolean;
  showingAssets?: boolean;
}

export function Header({
  editMode,
  onEditModeChange,
  onOpenCredentials,
  onOpenShellLibrary,
  onOpenEmailInventory,
  onOpenAdmin,
  onOpenLogs,
  onOpenTimeline,
  onOpenAssets,
  showingLogs,
  showingTimeline,
  showingAssets,
}: HeaderProps) {
  return (
    <div className="app-header">
      <h1>MuTech Control</h1>
      <div className="header-controls">
        {/* View Tools - Always visible */}
        <button
          className={`btn btn-sm ${showingTimeline ? 'btn-timeline-active' : 'btn-timeline'}`}
          onClick={onOpenTimeline}
          title="View device state history over time"
        >
          <i className="bi bi-bar-chart-steps me-1"></i>
          State Timeline
        </button>
        <button
          className={`btn btn-sm ${showingAssets ? 'btn-assets-active' : 'btn-assets'}`}
          onClick={onOpenAssets}
          title="Browse and manage physical assets (projectors, lamps)"
        >
          <i className="bi bi-lamp me-1"></i>
          Asset Browser
        </button>
        <button
          className={`btn btn-sm ${showingLogs ? 'btn-logs-active' : 'btn-logs'}`}
          onClick={onOpenLogs}
          title="View real-time operation logs and errors"
        >
          <i className="bi bi-terminal me-1"></i>
          Operation Logs
        </button>

        {/* Separator */}
        {editMode && <span className="header-separator">|</span>}

        {/* Config Tools - Edit mode only */}
        {editMode && onOpenShellLibrary && (
          <button
            className="btn btn-shell-library btn-sm"
            onClick={onOpenShellLibrary}
            title="Manage reusable shell command templates"
          >
            <i className="bi bi-bookmark me-1"></i>
            Shell Library
          </button>
        )}
        {editMode && onOpenCredentials && (
          <button
            className="btn btn-credentials btn-sm"
            onClick={onOpenCredentials}
            title="Manage device login credentials"
          >
            <i className="bi bi-key me-1"></i>
            Credentials
          </button>
        )}
        {editMode && onOpenEmailInventory && (
          <button
            className="btn btn-email-inventory btn-sm"
            onClick={onOpenEmailInventory}
            title="Send device inventory report via email"
          >
            <i className="bi bi-envelope me-1"></i>
            Email Report
          </button>
        )}
        {editMode && onOpenAdmin && (
          <button
            className="btn btn-admin btn-sm"
            onClick={onOpenAdmin}
            title="Admin tools: run scheduled tasks, view system status"
          >
            <i className="bi bi-gear me-1"></i>
            Admin
          </button>
        )}

        <div className="edit-mode-toggle">
          <label htmlFor="edit-mode-checkbox">Edit Mode</label>
          <input
            type="checkbox"
            id="edit-mode-checkbox"
            checked={editMode}
            onChange={(e) => onEditModeChange(e.target.checked)}
          />
        </div>
      </div>
    </div>
  );
}
