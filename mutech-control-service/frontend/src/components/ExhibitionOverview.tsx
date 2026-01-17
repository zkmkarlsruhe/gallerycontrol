import type { Exhibition } from '../types';
import { ExhibitionCard } from './ExhibitionCard';
import { ConfirmButton } from './ui/ConfirmButton';

interface ExhibitionOverviewProps {
  exhibitions: Exhibition[];
  editMode: boolean;
  onScrollTo: (exhibitionId: string) => void;
  onControl: (exhibitionId: string, command: 'on' | 'off', exhibitionName: string) => void;
  onControlAll: (command: 'on' | 'off') => void;
  onAddExhibition?: () => void;
}

export function ExhibitionOverview({ exhibitions, editMode, onScrollTo, onControl, onControlAll, onAddExhibition }: ExhibitionOverviewProps) {
  const visibleExhibitions = editMode ? exhibitions : exhibitions.filter(e => e.enabled);
  const enabledExhibitions = exhibitions.filter(e => e.enabled);

  if (visibleExhibitions.length === 0 && !editMode) return null;

  return (
    <div className="overview-section">
      {/* Global Control Buttons */}
      {enabledExhibitions.length > 0 && (
        <div className="global-controls">
          <ConfirmButton
            className="btn btn-global-on"
            onConfirm={() => onControlAll('on')}
            confirmText="Confirm ON?"
          >
            <i className="bi bi-power me-2"></i>
            Turn All ON
          </ConfirmButton>
          <ConfirmButton
            className="btn btn-global-off"
            onConfirm={() => onControlAll('off')}
            confirmText="Confirm OFF?"
          >
            <i className="bi bi-power me-2"></i>
            Turn All OFF
          </ConfirmButton>
        </div>
      )}

      {/* Exhibition Cards */}
      <div className="exhibition-cards">
        {visibleExhibitions.map(exhibition => (
          <ExhibitionCard
            key={exhibition.id}
            exhibition={exhibition}
            onScrollTo={onScrollTo}
            onControl={onControl}
          />
        ))}
        {editMode && onAddExhibition && (
          <div className="exhibition-card add-exhibition-card" onClick={onAddExhibition}>
            <div className="add-card-content">
              <i className="bi bi-plus-circle"></i>
              <span>Add Exhibition</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
