import type { Exhibition } from '../types';
import { TouchSafeButton } from './ui/TouchSafeButton';

interface DeviceStats {
  on: number;
  off: number;
  error: number;
  cooling: number;
}

interface ExhibitionCardProps {
  exhibition: Exhibition;
  onScrollTo: (exhibitionId: string) => void;
  onControl: (exhibitionId: string, command: 'on' | 'off', exhibitionName: string) => void;
}

function getExhibitionStats(exhibition: Exhibition): DeviceStats {
  const stats: DeviceStats = { on: 0, off: 0, error: 0, cooling: 0 };
  exhibition.artworks.forEach(artwork => {
    artwork.devices.forEach(device => {
      if (device.state === 1) stats.on++;
      else if (device.state === 0) stats.off++;
      else if (device.state === 2 || device.state === 3) stats.cooling++;
      else stats.error++;
    });
  });
  return stats;
}

export function ExhibitionCard({ exhibition, onScrollTo, onControl }: ExhibitionCardProps) {
  const stats = getExhibitionStats(exhibition);
  const isDisabled = !exhibition.enabled;

  return (
    <div className={`exhibition-card ${isDisabled ? 'disabled' : ''}`}>
      <div className="exhibition-card-header">
        <div
          className="exhibition-card-name"
          onClick={() => onScrollTo(exhibition.id)}
        >
          {isDisabled && <span className="disabled-badge">DISABLED</span>}
          {exhibition.name}
        </div>
      </div>
      <div className="exhibition-card-stats">
        {stats.on > 0 && (
          <><span className="stat-dot on"></span><span className="stat-count">{stats.on}</span></>
        )}
        {stats.off > 0 && (
          <><span className="stat-dot off"></span><span className="stat-count">{stats.off}</span></>
        )}
        {stats.error > 0 && (
          <><span className="stat-dot error"></span><span className="stat-count">{stats.error}</span></>
        )}
        {stats.cooling > 0 && (
          <><span className="stat-dot cooling"></span><span className="stat-count">{stats.cooling}</span></>
        )}
      </div>
      <div className="exhibition-card-controls">
        <div className="btn-group">
          <TouchSafeButton
            className="btn btn-on btn-sm"
            onClick={() => onControl(exhibition.id, 'on', exhibition.name)}
          >
            ON
          </TouchSafeButton>
          <TouchSafeButton
            className="btn btn-off btn-sm"
            onClick={() => onControl(exhibition.id, 'off', exhibition.name)}
          >
            OFF
          </TouchSafeButton>
        </div>
      </div>
    </div>
  );
}
