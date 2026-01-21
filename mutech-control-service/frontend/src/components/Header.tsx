interface HeaderProps {
  editMode: boolean;
  onEditModeChange: (enabled: boolean) => void;
  onOpenCredentials?: () => void;
  onOpenShellLibrary?: () => void;
  onOpenEmailInventory?: () => void;
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
        <button
          className={`btn btn-sm ${showingTimeline ? 'btn-timeline-active' : 'btn-timeline'}`}
          onClick={onOpenTimeline}
          title="State Timeline"
        >
          <i className="bi bi-bar-chart-steps me-1"></i>
          Timeline
        </button>
        <button
          className={`btn btn-sm ${showingAssets ? 'btn-assets-active' : 'btn-assets'}`}
          onClick={onOpenAssets}
          title="Asset Browser"
        >
          <i className="bi bi-lamp me-1"></i>
          Assets
        </button>
        <button
          className={`btn btn-sm ${showingLogs ? 'btn-logs-active' : 'btn-logs'}`}
          onClick={onOpenLogs}
          title="Log Viewer"
        >
          <i className="bi bi-terminal me-1"></i>
          Logs
        </button>
        {editMode && onOpenShellLibrary && (
          <button className="btn btn-shell-library btn-sm" onClick={onOpenShellLibrary}>
            <i className="bi bi-bookmark me-1"></i>
            Shell Library
          </button>
        )}
        {editMode && onOpenCredentials && (
          <button className="btn btn-credentials btn-sm" onClick={onOpenCredentials}>
            <i className="bi bi-key me-1"></i>
            Credentials
          </button>
        )}
        {editMode && onOpenEmailInventory && (
          <button className="btn btn-email-inventory btn-sm" onClick={onOpenEmailInventory}>
            <i className="bi bi-envelope me-1"></i>
            Email Inventory
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
