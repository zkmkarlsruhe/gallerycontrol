import React, { useState, useEffect, useCallback } from 'react';
import type { Asset, LampHoursLog } from '../types';
import { Modal } from './ui/Modal';
import { ConfirmButton } from './ui/ConfirmButton';

interface AssetBrowserPageProps {
  onClose: () => void;
}

interface AssetListResponse {
  items: Asset[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

interface LampHistoryResponse {
  items: LampHoursLog[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

const EVENT_ICONS: Record<string, string> = {
  onboard: '🔌',
  power_on: '▶️',
  power_off: '⏹️',
  offboard: '🔌',
  manual: '✏️',
};

function LampHoursTimeline({ assetId }: { assetId: string }) {
  const [logs, setLogs] = useState<LampHoursLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);

  const loadLogs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/assets/${assetId}/lamp-history?per_page=500`);
      if (res.ok) {
        const data: LampHistoryResponse = await res.json();
        setLogs(data.items);
        setTotal(data.total);
      }
    } catch (err) {
      console.error('Failed to load lamp history:', err);
    } finally {
      setLoading(false);
    }
  }, [assetId]);

  useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  const handleExportCsv = () => {
    window.open(`/api/assets/${assetId}/lamp-history/csv`, '_blank');
  };

  if (loading) {
    return <div className="lamp-history-loading">Loading...</div>;
  }

  if (logs.length === 0) {
    return <div className="lamp-history-empty">No lamp hours history recorded yet.</div>;
  }

  return (
    <div className="lamp-history-table-container">
      <div className="lamp-history-header">
        <span>{total} entries</span>
        <button className="btn btn-sm btn-outline" onClick={handleExportCsv}>
          Export CSV
        </button>
      </div>
      <table className="lamp-history-table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Event</th>
            <th>Hours</th>
            <th>+/-</th>
            <th>Exhibition</th>
            <th>Artwork</th>
            <th>Device</th>
          </tr>
        </thead>
        <tbody>
          {logs.map((log, index) => {
            const prevLog = logs[index + 1];
            const delta = prevLog ? log.lamp_hours - prevLog.lamp_hours : null;
            const date = new Date(log.timestamp);
            const dateStr = date.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: '2-digit' });
            const timeStr = date.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });

            return (
              <tr key={log.id} className={`event-${log.event_type}`}>
                <td className="col-date">{dateStr} {timeStr}</td>
                <td className="col-event">
                  <span className="event-icon">{EVENT_ICONS[log.event_type] || '📊'}</span>
                  {log.event_type}
                </td>
                <td className="col-hours">{log.lamp_hours}h</td>
                <td className="col-delta">
                  {delta !== null && delta !== 0 && (
                    <span className={delta > 0 ? 'delta-pos' : 'delta-neg'}>
                      {delta > 0 ? '+' : ''}{delta}
                    </span>
                  )}
                </td>
                <td className="col-exhibition">{log.exhibition_name || '-'}</td>
                <td className="col-artwork">{log.artwork_name || '-'}</td>
                <td className="col-device">{log.device_name || '-'}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function EditAssetModal({
  asset,
  onClose,
  onSave,
}: {
  asset: Asset;
  onClose: () => void;
  onSave: (id: string, data: { hostname?: string; notes?: string }) => void;
}) {
  const [hostname, setHostname] = useState(asset.hostname || '');
  const [notes, setNotes] = useState(asset.notes || '');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave(asset.id, { hostname: hostname || undefined, notes: notes || undefined });
    onClose();
  };

  return (
    <Modal isOpen={true} onClose={onClose} title={`Edit Asset ${asset.asset_number}`}>
      <form onSubmit={handleSubmit}>
        <div className="mb-3">
          <label className="form-label">Asset Number</label>
          <input type="text" className="form-control" value={asset.asset_number} disabled />
        </div>
        <div className="mb-3">
          <label className="form-label">Hostname Override</label>
          <input
            type="text"
            className="form-control"
            value={hostname}
            onChange={(e) => setHostname(e.target.value)}
            placeholder="Auto-detected from DNS"
          />
          <div className="form-text">Leave empty to use auto-detected hostname</div>
        </div>
        <div className="mb-3">
          <label className="form-label">Notes</label>
          <textarea
            className="form-control"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            placeholder="Optional notes about this asset"
          />
        </div>
        <div className="modal-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary">
            Save
          </button>
        </div>
      </form>
    </Modal>
  );
}

interface ExhibitionOption {
  id: string;
  name: string;
}

export function AssetBrowserPage({ onClose }: AssetBrowserPageProps) {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [total, setTotal] = useState(0);
  const [expandedAssetId, setExpandedAssetId] = useState<string | null>(null);
  const [editAsset, setEditAsset] = useState<Asset | null>(null);
  const [backfillRunning, setBackfillRunning] = useState(false);
  const [backfillResult, setBackfillResult] = useState<any>(null);
  const [relinkRunning, setRelinkRunning] = useState(false);
  const [lampHoursRunning, setLampHoursRunning] = useState(false);
  const [lampHoursResult, setLampHoursResult] = useState<any>(null);
  const [exhibitions, setExhibitions] = useState<ExhibitionOption[]>([]);
  const [selectedExhibition, setSelectedExhibition] = useState<string>('');
  const [selectedAssets, setSelectedAssets] = useState<Set<string>>(new Set());

  const loadAssets = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        per_page: '1000',
      });
      if (search) {
        params.set('search', search);
      }
      if (selectedExhibition) {
        params.set('exhibition_id', selectedExhibition);
      }
      const res = await fetch(`/api/assets?${params}`);
      if (res.ok) {
        const data: AssetListResponse = await res.json();
        setAssets(data.items);
        setTotal(data.total);
      }
    } catch (err) {
      console.error('Failed to load assets:', err);
    } finally {
      setLoading(false);
    }
  }, [search, selectedExhibition]);

  useEffect(() => {
    loadAssets();
  }, [loadAssets]);

  // Load exhibitions for filter dropdown
  useEffect(() => {
    fetch('/api/assets/exhibitions')
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(data => {
        // Ensure we got an array
        if (Array.isArray(data)) {
          setExhibitions(data);
        } else {
          console.error('Exhibitions response is not an array:', data);
        }
      })
      .catch(err => console.error('Failed to load exhibitions:', err));
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    loadAssets();
  };

  const handleUpdateAsset = async (id: string, data: { hostname?: string; notes?: string }) => {
    try {
      const res = await fetch(`/api/assets/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      if (res.ok) {
        loadAssets();
      }
    } catch (err) {
      console.error('Failed to update asset:', err);
    }
  };

  const handleDeleteAsset = async (id: string) => {
    try {
      const res = await fetch(`/api/assets/${id}`, { method: 'DELETE' });
      if (res.ok) {
        loadAssets();
      }
    } catch (err) {
      console.error('Failed to delete asset:', err);
    }
  };

  const handleBackfill = async () => {
    setBackfillRunning(true);
    setBackfillResult(null);
    try {
      const res = await fetch('/api/assets/backfill', { method: 'POST' });
      if (res.ok) {
        const result = await res.json();
        setBackfillResult(result);
        loadAssets();
      }
    } catch (err) {
      console.error('Failed to run backfill:', err);
    } finally {
      setBackfillRunning(false);
    }
  };

  const handleRelink = async () => {
    setRelinkRunning(true);
    try {
      const res = await fetch('/api/admin/scheduler/trigger/asset_linker', { method: 'POST' });
      if (res.ok) {
        // Reload assets after a short delay to see updated links
        setTimeout(loadAssets, 2000);
      }
    } catch (err) {
      console.error('Failed to trigger relink:', err);
    } finally {
      setRelinkRunning(false);
    }
  };

  const handleRecordLampHours = async () => {
    const ids = Array.from(selectedAssets);
    if (ids.length === 0) {
      alert('Please select assets first');
      return;
    }
    setLampHoursRunning(true);
    setLampHoursResult(null);
    try {
      const res = await fetch('/api/assets/record-lamp-hours', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(ids),
      });
      if (res.ok) {
        const result = await res.json();
        setLampHoursResult(result);
        loadAssets();
      }
    } catch (err) {
      console.error('Failed to record lamp hours:', err);
    } finally {
      setLampHoursRunning(false);
    }
  };

  const exportSelectedCSV = async () => {
    const ids = Array.from(selectedAssets);
    try {
      const response = await fetch('/api/assets/lamp-history/csv', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(ids),
      });
      if (!response.ok) {
        console.error('Failed to export CSV');
        return;
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `lamp_history_${ids.length}_assets.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to export CSV:', err);
    }
  };

  return (
    <div className="asset-browser-page">
      <div className="sub-page-header">
        <div className="sub-page-header-left">
          <button className="btn btn-sm btn-outline-secondary" onClick={onClose}>
            <i className="bi bi-arrow-left me-1"></i>
            Back
          </button>
          <h2>
            <i className="bi bi-projector me-2"></i>
            Projectors
          </h2>
          <span className="text-muted">{total} assets</span>
        </div>
        <div className="sub-page-header-right">
          <form onSubmit={handleSearch} className="d-flex gap-2 align-items-center">
            <input
              type="text"
              className="form-control form-control-sm"
              placeholder="Search..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ width: '150px' }}
            />
            <button type="submit" className="btn btn-sm btn-outline-secondary">
              <i className="bi bi-search"></i>
            </button>
          </form>
          <select
            className="form-select form-select-sm"
            value={selectedExhibition}
            onChange={(e) => setSelectedExhibition(e.target.value)}
            style={{ width: 'auto', maxWidth: '180px' }}
          >
            <option value="">All Exhibitions</option>
            {exhibitions.map(ex => (
              <option key={ex.id} value={ex.id}>{ex.name}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Action row */}
      <div className="sub-page-actions">
        {selectedAssets.size > 0 && (
          <button
            type="button"
            className="btn btn-sm btn-outline-secondary"
            onClick={exportSelectedCSV}
          >
            <i className="bi bi-download me-1"></i>
            Export ({selectedAssets.size})
          </button>
        )}
        <button
          className="btn btn-sm btn-outline-secondary"
          onClick={handleRelink}
          disabled={relinkRunning}
          title="Link unlinked assets to devices via DNS lookup"
        >
          <i className="bi bi-link-45deg me-1"></i>
          {relinkRunning ? 'Linking...' : 'Relink'}
        </button>
        <button
          className="btn btn-sm btn-outline-secondary"
          onClick={handleBackfill}
          disabled={backfillRunning}
          title="Create missing assets from existing PJLink devices"
        >
          <i className="bi bi-plus-circle me-1"></i>
          {backfillRunning ? 'Running...' : 'Backfill'}
        </button>
        <button
          className="btn btn-sm btn-outline-secondary"
          onClick={handleRecordLampHours}
          disabled={lampHoursRunning || selectedAssets.size === 0}
          title="Record current lamp hours for selected assets"
        >
          <i className="bi bi-lightbulb me-1"></i>
          {lampHoursRunning ? 'Recording...' : `Lamp Hours${selectedAssets.size > 0 ? ` (${selectedAssets.size})` : ''}`}
        </button>
      </div>

      {backfillResult && (
        <div className="backfill-result alert alert-info">
          <strong>Backfill complete:</strong> {backfillResult.linked} assets linked,
          {backfillResult.created} lamp hours logged,
          {backfillResult.skipped?.length || 0} skipped,
          {backfillResult.failed?.length || 0} failed
        </div>
      )}

      {lampHoursResult && (
        <div className="backfill-result alert alert-info">
          <strong>Lamp hours recorded:</strong> {lampHoursResult.recorded} devices,
          {lampHoursResult.skipped?.length || 0} skipped,
          {lampHoursResult.failed?.length || 0} failed
        </div>
      )}

      <div className="asset-content">
        {loading ? (
          <div className="loading">Loading assets...</div>
        ) : assets.length === 0 ? (
          <div className="empty-state">
            <p>No assets found.</p>
            <p>Assets are automatically created when PJLink devices are added with asset numbers in their hostnames.</p>
          </div>
        ) : (
          <>
            <table className="asset-table">
            <thead>
              <tr>
                <th className="col-select">
                  <input
                    type="checkbox"
                    checked={selectedAssets.size === assets.length && assets.length > 0}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedAssets(new Set(assets.map(a => a.id)));
                      } else {
                        setSelectedAssets(new Set());
                      }
                    }}
                    title="Select all"
                  />
                </th>
                <th className="col-status"></th>
                <th>Asset</th>
                <th>Exhibition</th>
                <th>Artwork</th>
                <th>Device</th>
                <th>Lamp Hours</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {assets.map((asset) => {
                const stateClass = asset.device_state === 1 ? 'state-on'
                  : asset.device_state === 0 ? 'state-standby'
                  : asset.device_state === -1 ? 'state-offline'
                  : 'state-unknown';
                return (
                <React.Fragment key={asset.id}>
                  <tr
                    className={`asset-row ${expandedAssetId === asset.id ? 'expanded' : ''} ${stateClass} ${!asset.current_device_id ? 'asset-unlinked' : ''}`}
                    onClick={() => setExpandedAssetId(
                      expandedAssetId === asset.id ? null : asset.id
                    )}
                  >
                    <td className="col-select" onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={selectedAssets.has(asset.id)}
                        onChange={(e) => {
                          const next = new Set(selectedAssets);
                          if (e.target.checked) next.add(asset.id);
                          else next.delete(asset.id);
                          setSelectedAssets(next);
                        }}
                      />
                    </td>
                    <td className="col-status">
                      <span className={`status-dot ${stateClass}`} title={
                        asset.device_state === 1 ? 'On'
                        : asset.device_state === 0 ? 'Standby'
                        : asset.device_state === -1 ? 'Offline'
                        : 'Not linked'
                      }></span>
                    </td>
                    <td className="asset-number">{asset.asset_number}</td>
                    <td className="exhibition">{asset.exhibition_name || '-'}</td>
                    <td className="artwork">{asset.artwork_name || '-'}</td>
                    <td className="current-device">
                      {asset.current_device_name || <span className="text-muted">Not linked</span>}
                    </td>
                    <td className="lamp-hours">
                      {asset.last_lamp_hours !== null ? (
                        <>{asset.last_lamp_hours}h</>
                      ) : (
                        '-'
                      )}
                    </td>
                    <td className="actions" onClick={(e) => e.stopPropagation()}>
                      <button
                        className="btn btn-sm btn-edit"
                        onClick={() => setEditAsset(asset)}
                        title="Edit"
                      >
                        <i className="bi bi-pencil"></i>
                      </button>
                      <ConfirmButton
                        className="btn btn-sm btn-delete"
                        onConfirm={() => handleDeleteAsset(asset.id)}
                        confirmText="Delete?"
                        title="Delete"
                      >
                        <i className="bi bi-trash"></i>
                      </ConfirmButton>
                    </td>
                  </tr>
                  {expandedAssetId === asset.id && (
                    <tr key={`${asset.id}-timeline`} className="timeline-row">
                      <td colSpan={8}>
                        <LampHoursTimeline assetId={asset.id} />
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );})}
            </tbody>
          </table>
          </>
        )}
      </div>

      {editAsset && (
        <EditAssetModal
          asset={editAsset}
          onClose={() => setEditAsset(null)}
          onSave={handleUpdateAsset}
        />
      )}
    </div>
  );
}
