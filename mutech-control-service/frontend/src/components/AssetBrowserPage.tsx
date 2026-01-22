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

function formatDate(isoString: string): string {
  const date = new Date(isoString);
  return date.toLocaleString();
}

function LampHoursTimeline({ assetId }: { assetId: string }) {
  const [logs, setLogs] = useState<LampHoursLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);

  // Reset page when assetId changes
  useEffect(() => {
    setPage(1);
  }, [assetId]);

  const loadLogs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/assets/${assetId}/lamp-history?page=${page}&per_page=20`);
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
  }, [assetId, page]);

  useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  const handleExportCsv = () => {
    window.open(`/api/assets/${assetId}/lamp-history/csv`, '_blank');
  };

  if (loading) {
    return <div className="timeline-loading">Loading lamp history...</div>;
  }

  if (logs.length === 0) {
    return <div className="timeline-empty">No lamp hours history recorded yet.</div>;
  }

  return (
    <div className="lamp-hours-timeline">
      <div className="timeline-header">
        <h4>Lamp Hours History ({total} entries)</h4>
        <button className="btn btn-sm btn-outline" onClick={handleExportCsv}>
          <i className="bi bi-download me-1"></i>
          Export CSV
        </button>
      </div>
      <div className="timeline-entries">
        {logs.map((log, index) => {
          const prevLog = logs[index + 1];
          const delta = prevLog ? log.lamp_hours - prevLog.lamp_hours : null;

          return (
            <div key={log.id} className={`timeline-entry event-${log.event_type}`}>
              <div className="timeline-marker">
                <span className="timeline-icon">{EVENT_ICONS[log.event_type] || '📊'}</span>
                <div className="timeline-line"></div>
              </div>
              <div className="timeline-content">
                <div className="timeline-event-type">{log.event_type}</div>
                <div className="timeline-lamp-hours">
                  {log.lamp_hours}h
                  {delta !== null && delta > 0 && (
                    <span className="timeline-delta">+{delta}h</span>
                  )}
                </div>
                <div className="timeline-context">
                  {log.device_name && <span>{log.device_name}</span>}
                  {log.artwork_name && <span> / {log.artwork_name}</span>}
                  {log.exhibition_name && <span> / {log.exhibition_name}</span>}
                </div>
                <div className="timeline-timestamp">{formatDate(log.timestamp)}</div>
              </div>
            </div>
          );
        })}
      </div>
      {total > 20 && (
        <div className="timeline-pagination">
          <button
            className="btn btn-sm"
            disabled={page === 1}
            onClick={() => setPage(p => p - 1)}
          >
            Previous
          </button>
          <span>Page {page} of {Math.ceil(total / 20)}</span>
          <button
            className="btn btn-sm"
            disabled={page * 20 >= total}
            onClick={() => setPage(p => p + 1)}
          >
            Next
          </button>
        </div>
      )}
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

export function AssetBrowserPage({ onClose }: AssetBrowserPageProps) {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [expandedAssetId, setExpandedAssetId] = useState<string | null>(null);
  const [editAsset, setEditAsset] = useState<Asset | null>(null);
  const [backfillRunning, setBackfillRunning] = useState(false);
  const [backfillResult, setBackfillResult] = useState<any>(null);
  const [relinkRunning, setRelinkRunning] = useState(false);

  const loadAssets = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(page),
        per_page: '20',
      });
      if (search) {
        params.set('search', search);
      }
      const res = await fetch(`/api/assets?${params}`);
      if (res.ok) {
        const data: AssetListResponse = await res.json();
        setAssets(data.items);
        setTotalPages(data.pages);
        setTotal(data.total);
      }
    } catch (err) {
      console.error('Failed to load assets:', err);
    } finally {
      setLoading(false);
    }
  }, [page, search]);

  useEffect(() => {
    loadAssets();
  }, [loadAssets]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
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

  return (
    <div className="asset-browser-page">
      <div className="page-header">
        <div className="page-title">
          <h2>Asset Browser</h2>
          <span className="badge">{total} assets</span>
        </div>
        <div className="page-actions">
          <button
            className="btn btn-sm btn-outline"
            onClick={handleRelink}
            disabled={relinkRunning}
            title="Link unlinked assets to devices via DNS lookup"
          >
            {relinkRunning ? 'Linking...' : 'Run Relink'}
          </button>
          <button
            className="btn btn-sm btn-outline"
            onClick={handleBackfill}
            disabled={backfillRunning}
            title="Create missing assets from existing PJLink devices"
          >
            {backfillRunning ? 'Running...' : 'Backfill Assets'}
          </button>
          <button className="btn btn-sm btn-close-page" onClick={onClose}>
            <i className="bi bi-x-lg"></i>
          </button>
        </div>
      </div>

      {backfillResult && (
        <div className="backfill-result alert alert-info">
          <strong>Backfill complete:</strong> {backfillResult.linked} assets linked,
          {backfillResult.created} lamp hours logged,
          {backfillResult.skipped?.length || 0} skipped,
          {backfillResult.failed?.length || 0} failed
        </div>
      )}

      <div className="asset-search">
        <form onSubmit={handleSearch}>
          <input
            type="text"
            className="form-control"
            placeholder="Search by asset number or hostname..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <button type="submit" className="btn btn-primary">Search</button>
        </form>
      </div>

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
                <th>Asset Number</th>
                <th>Hostname</th>
                <th>Current Device</th>
                <th>Last Lamp Hours</th>
                <th>Notes</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {assets.map((asset) => (
                <React.Fragment key={asset.id}>
                  <tr
                    className={expandedAssetId === asset.id ? 'expanded' : ''}
                    onClick={() => setExpandedAssetId(
                      expandedAssetId === asset.id ? null : asset.id
                    )}
                  >
                    <td className="asset-number">{asset.asset_number}</td>
                    <td className="hostname">{asset.hostname || '-'}</td>
                    <td className="current-device">
                      {asset.current_device_name || <span className="text-muted">Not linked</span>}
                    </td>
                    <td className="lamp-hours">
                      {asset.last_lamp_hours !== null ? (
                        <>
                          {asset.last_lamp_hours}h
                          <span className="last-event">
                            ({asset.last_event_type})
                          </span>
                        </>
                      ) : (
                        '-'
                      )}
                    </td>
                    <td className="notes">{asset.notes || '-'}</td>
                    <td className="actions" onClick={(e) => e.stopPropagation()}>
                      <button
                        className="btn btn-sm btn-edit"
                        onClick={() => setEditAsset(asset)}
                      >
                        Edit
                      </button>
                      <ConfirmButton
                        className="btn btn-sm btn-delete"
                        onConfirm={() => handleDeleteAsset(asset.id)}
                        confirmText="Delete?"
                      >
                        Delete
                      </ConfirmButton>
                    </td>
                  </tr>
                  {expandedAssetId === asset.id && (
                    <tr key={`${asset.id}-timeline`} className="timeline-row">
                      <td colSpan={6}>
                        <LampHoursTimeline assetId={asset.id} />
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>

          {totalPages > 1 && (
            <div className="pagination">
              <button
                className="btn btn-sm"
                disabled={page === 1}
                onClick={() => setPage(p => p - 1)}
              >
                Previous
              </button>
              <span>Page {page} of {totalPages}</span>
              <button
                className="btn btn-sm"
                disabled={page >= totalPages}
                onClick={() => setPage(p => p + 1)}
              >
                Next
              </button>
            </div>
          )}
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
