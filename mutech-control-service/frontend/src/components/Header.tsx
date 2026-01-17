interface HeaderProps {
  editMode: boolean;
  onEditModeChange: (enabled: boolean) => void;
  onOpenCredentials?: () => void;
  onOpenLogs?: () => void;
  onOpenTimeline?: () => void;
  showingLogs?: boolean;
  showingTimeline?: boolean;
}

export function Header({
  editMode,
  onEditModeChange,
  onOpenCredentials,
  onOpenLogs,
  onOpenTimeline,
  showingLogs,
  showingTimeline,
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
          className={`btn btn-sm ${showingLogs ? 'btn-logs-active' : 'btn-logs'}`}
          onClick={onOpenLogs}
          title="Log Viewer"
        >
          <i className="bi bi-terminal me-1"></i>
          Logs
        </button>
        {editMode && onOpenCredentials && (
          <button className="btn btn-credentials btn-sm" onClick={onOpenCredentials}>
            <i className="bi bi-key me-1"></i>
            Credentials
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
