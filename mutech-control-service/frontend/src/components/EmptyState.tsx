interface EmptyStateProps {
  editMode: boolean;
  newExhibitionName: string;
  onNameChange: (name: string) => void;
  onSubmit: () => void;
}

export function EmptyState({ editMode, newExhibitionName, onNameChange, onSubmit }: EmptyStateProps) {
  return (
    <div className="empty-state">
      <div className="empty-state-content">
        <i className="bi bi-collection"></i>
        <h2>No exhibitions yet</h2>
        {editMode ? (
          <div className="add-exhibition-form">
            <p>Create your first exhibition:</p>
            <div className="input-group">
              <input
                type="text"
                className="form-control"
                placeholder="Exhibition name"
                value={newExhibitionName}
                onChange={(e) => onNameChange(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && onSubmit()}
              />
              <button
                className="btn btn-primary"
                onClick={onSubmit}
                disabled={!newExhibitionName.trim()}
              >
                <i className="bi bi-plus-lg"></i> Add
              </button>
            </div>
          </div>
        ) : (
          <>
            <p>Enable Edit Mode to start adding exhibitions, artworks, and devices.</p>
            <div className="empty-state-arrow">
              <span>Start here</span>
              <i className="bi bi-arrow-up"></i>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
