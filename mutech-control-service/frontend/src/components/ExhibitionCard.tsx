import type { Exhibition } from '../types';
import { TouchSafeButton } from './ui/TouchSafeButton';

interface StatCount {
  auto: number;
  manual: number;
}

interface DeviceStats {
  on: StatCount;
  off: StatCount;
  error: StatCount;
  cooling: StatCount;
}

interface ExhibitionCardProps {
  exhibition: Exhibition;
  onScrollTo: (exhibitionId: string) => void;
  onControl: (exhibitionId: string, command: 'on' | 'off', exhibitionName: string) => void;
}

function getExhibitionStats(exhibition: Exhibition): DeviceStats {
  const stats: DeviceStats = {
    on: { auto: 0, manual: 0 },
    off: { auto: 0, manual: 0 },
    error: { auto: 0, manual: 0 },
    cooling: { auto: 0, manual: 0 },
  };
  exhibition.artworks.forEach(artwork => {
    artwork.devices.forEach(device => {
      const bucket = device.automation_enabled ? 'auto' : 'manual';
      if (device.state === 1) stats.on[bucket]++;
      else if (device.state === 0) stats.off[bucket]++;
      else if (device.state === 2 || device.state === 3) stats.cooling[bucket]++;
      else stats.error[bucket]++;
    });
  });
  return stats;
}

function formatStat(stat: StatCount): string {
  return `${stat.auto}/${stat.manual}`;
}

function statTotal(stat: StatCount): number {
  return stat.auto + stat.manual;
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
        {statTotal(stats.on) > 0 && (
          <><span className="stat-dot on"></span><span className="stat-count">{formatStat(stats.on)}</span></>
        )}
        {statTotal(stats.off) > 0 && (
          <><span className="stat-dot off"></span><span className="stat-count">{formatStat(stats.off)}</span></>
        )}
        {statTotal(stats.error) > 0 && (
          <><span className="stat-dot error"></span><span className="stat-count">{formatStat(stats.error)}</span></>
        )}
        {statTotal(stats.cooling) > 0 && (
          <><span className="stat-dot cooling"></span><span className="stat-count">{formatStat(stats.cooling)}</span></>
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
