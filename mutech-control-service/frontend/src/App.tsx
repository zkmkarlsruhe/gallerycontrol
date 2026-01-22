import { useState, useEffect, useCallback, useMemo } from 'react';
import { useApi } from './hooks/useApi';
import type { Exhibition, Credential, Device, ShellTemplate } from './types';
import {
  Header,
  Toast,
  EmptyState,
  ExhibitionOverview,
  ExhibitionSection,
  AddExhibitionModal,
  AddArtworkModal,
  AddDeviceModal,
  EditExhibitionModal,
  EditArtworkModal,
  EditDeviceModal,
  CredentialsModal,
  ShellTemplatesModal,
  LogViewer,
  StateTimelinePage,
  AssetBrowserPage,
} from './components';
import { EmailInventoryModal } from './components/modals/EmailInventoryModal';
import { AdminModal } from './components/modals/AdminModal';
import 'bootstrap/dist/css/bootstrap.min.css';
import 'bootstrap-icons/font/bootstrap-icons.css';
import './App.css';

interface ToastState {
  message: string;
  type: 'success' | 'danger' | 'info';
}

interface AddDeviceContext {
  exhibitionId: string;
  exhibitionName: string;
  artworkId: string;
  artworkName: string;
}

interface AddArtworkContext {
  exhibitionId: string;
  exhibitionName: string;
}

function App() {
  const {
    fetchExhibitions,
    controlDevice,
    controlArtwork,
    controlExhibition,
    executeAction,
    createExhibition,
    createArtwork,
    createDevice,
    updateExhibition,
    updateArtwork,
    updateDevice,
    deleteExhibition,
    deleteArtwork,
    deleteDevice,
    fetchCredentials,
    createCredential,
    updateCredential,
    deleteCredential,
    fetchShellTemplates,
    createShellTemplate,
    updateShellTemplate,
    deleteShellTemplate,
    saveDeviceAsTemplate,
    fetchEmailConfig,
    fetchInventoryPreview,
    sendInventoryEmail,
  } = useApi();

  const [exhibitions, setExhibitions] = useState<Exhibition[]>([]);
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [templates, setTemplates] = useState<ShellTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editMode, setEditMode] = useState(true);
  const [expandedDevice, setExpandedDevice] = useState<string | null>(null);
  const [toast, setToast] = useState<ToastState | null>(null);
  const [newExhibitionName, setNewExhibitionName] = useState('');

  // Modal states
  const [showAddExhibitionModal, setShowAddExhibitionModal] = useState(false);
  const [showCredentialsModal, setShowCredentialsModal] = useState(false);
  const [showShellTemplatesModal, setShowShellTemplatesModal] = useState(false);
  const [showEmailInventoryModal, setShowEmailInventoryModal] = useState(false);
  const [showAdminModal, setShowAdminModal] = useState(false);

  // Log viewer state
  const [showLogViewer, setShowLogViewer] = useState(false);
  const [logFilterDeviceId, setLogFilterDeviceId] = useState<string | null>(null);

  // Timeline page state
  const [showTimeline, setShowTimeline] = useState(false);

  // Asset browser state
  const [showAssets, setShowAssets] = useState(false);

  // Pending state changes (deviceId -> target state)
  const [pendingStates, setPendingStates] = useState<Map<string, 'on' | 'off'>>(new Map());

  const [editExhibitionData, setEditExhibitionData] = useState<Exhibition | null>(null);
  const [editArtworkData, setEditArtworkData] = useState<{ id: string; name: string; enabled: boolean } | null>(null);
  const [editDeviceData, setEditDeviceData] = useState<Device | null>(null);
  const [addArtworkContext, setAddArtworkContext] = useState<AddArtworkContext | null>(null);
  const [addDeviceContext, setAddDeviceContext] = useState<AddDeviceContext | null>(null);

  // Extract all devices for debug filter dropdown and timeline
  const allDevices = useMemo(() => {
    const devices: Array<{ id: string; name: string; type: string; artworkName: string; exhibitionName: string; state: number }> = [];
    for (const exhibition of exhibitions) {
      for (const artwork of exhibition.artworks) {
        for (const device of artwork.devices) {
          devices.push({
            id: device.id,
            name: device.name,
            type: device.device_type,
            artworkName: artwork.name,
            exhibitionName: exhibition.name,
            state: device.state,
          });
        }
      }
    }
    return devices;
  }, [exhibitions]);

  const showToast = useCallback((message: string, type: 'success' | 'danger' | 'info' = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  }, []);

  const openLogViewer = useCallback((deviceId?: string | null) => {
    setLogFilterDeviceId(deviceId || null);
    setShowLogViewer(true);
  }, []);

  const closeLogViewer = useCallback(() => {
    setShowLogViewer(false);
    setLogFilterDeviceId(null);
  }, []);

  const loadData = useCallback(async () => {
    try {
      const data = await fetchExhibitions();
      setExhibitions(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, [fetchExhibitions]);

  const loadCredentials = useCallback(async () => {
    try {
      const data = await fetchCredentials();
      setCredentials(data);
    } catch {
      // Credentials are optional, don't show error
    }
  }, [fetchCredentials]);

  const loadTemplates = useCallback(async () => {
    try {
      const data = await fetchShellTemplates();
      setTemplates(data);
    } catch {
      // Templates are optional, don't show error
    }
  }, [fetchShellTemplates]);

  useEffect(() => {
    loadData();
    loadCredentials();
    loadTemplates();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, [loadData, loadCredentials, loadTemplates]);

  // Clear pending states when device states match targets AND not in fast polling
  useEffect(() => {
    if (pendingStates.size === 0) return;

    const deviceInfoMap = new Map<string, { state: number; isVerifying: boolean }>();
    for (const exhibition of exhibitions) {
      for (const artwork of exhibition.artworks) {
        for (const device of artwork.devices) {
          deviceInfoMap.set(device.id, {
            state: device.state,
            isVerifying: device.poll_status?.is_verifying || false,
          });
        }
      }
    }

    const toRemove: string[] = [];
    pendingStates.forEach((targetCommand, deviceId) => {
      const deviceInfo = deviceInfoMap.get(deviceId);
      if (deviceInfo !== undefined) {
        // Don't clear while device is verifying (fast polling in progress)
        if (deviceInfo.isVerifying) return;

        // State 1 = on, State 0 = off
        const targetState = targetCommand === 'on' ? 1 : 0;
        if (deviceInfo.state === targetState) {
          toRemove.push(deviceId);
        }
      }
    });

    if (toRemove.length > 0) {
      setPendingStates(prev => {
        const next = new Map(prev);
        toRemove.forEach(id => next.delete(id));
        return next;
      });
    }
  }, [exhibitions, pendingStates]);

  // Control handlers
  const handleDeviceControl = async (deviceId: string, command: 'on' | 'off', deviceName: string) => {
    // Set pending state immediately for visual feedback
    setPendingStates(prev => new Map(prev).set(deviceId, command));

    try {
      const result = await controlDevice(deviceId, command);
      if (result.success) {
        showToast(`${command.toUpperCase()} sent to ${deviceName}`, 'success');
        setTimeout(loadData, 1000);
      } else {
        showToast(`Failed: ${result.error || 'Unknown error'}`, 'danger');
        // Clear pending state on failure
        setPendingStates(prev => {
          const next = new Map(prev);
          next.delete(deviceId);
          return next;
        });
      }
    } catch {
      showToast('Network error', 'danger');
      // Clear pending state on error
      setPendingStates(prev => {
        const next = new Map(prev);
        next.delete(deviceId);
        return next;
      });
    }
  };

  const handleArtworkControl = async (artworkId: string, command: 'on' | 'off', artworkName: string) => {
    // Set pending state for all automation-enabled devices in this artwork
    const artwork = exhibitions.flatMap(e => e.artworks).find(a => a.id === artworkId);
    if (artwork) {
      setPendingStates(prev => {
        const next = new Map(prev);
        artwork.devices.filter(d => d.automation_enabled && d.enabled).forEach(d => next.set(d.id, command));
        return next;
      });
    }

    try {
      const result = await controlArtwork(artworkId, command);
      if (result.success) {
        showToast(`${command.toUpperCase()} sent to ${artworkName}`, 'success');
        setTimeout(loadData, 1000);
      } else {
        showToast(`Failed: ${result.error || 'Unknown error'}`, 'danger');
      }
    } catch {
      showToast('Network error', 'danger');
    }
  };

  const handleExhibitionControl = async (exhibitionId: string, command: 'on' | 'off', exhibitionName: string) => {
    // Set pending state for all automation-enabled devices in this exhibition
    const exhibition = exhibitions.find(e => e.id === exhibitionId);
    if (exhibition) {
      setPendingStates(prev => {
        const next = new Map(prev);
        exhibition.artworks.flatMap(a => a.devices).filter(d => d.automation_enabled && d.enabled).forEach(d => next.set(d.id, command));
        return next;
      });
    }

    try {
      const result = await controlExhibition(exhibitionId, command);
      if (result.success) {
        showToast(`${command.toUpperCase()} sent to ${exhibitionName}`, 'success');
        setTimeout(loadData, 2000);
      } else {
        showToast(`Failed: ${result.error || 'Unknown error'}`, 'danger');
      }
    } catch {
      showToast('Network error', 'danger');
    }
  };

  const handleAllControl = async (command: 'on' | 'off') => {
    const enabledExhibitions = exhibitions.filter(e => e.enabled);
    if (enabledExhibitions.length === 0) {
      showToast('No enabled exhibitions to control', 'info');
      return;
    }

    // Set pending state for all automation-enabled devices in all exhibitions
    setPendingStates(prev => {
      const next = new Map(prev);
      enabledExhibitions.flatMap(e => e.artworks).flatMap(a => a.devices).filter(d => d.automation_enabled && d.enabled).forEach(d => next.set(d.id, command));
      return next;
    });

    showToast(`Sending ${command.toUpperCase()} to all exhibitions...`, 'info');

    // Send commands to all enabled exhibitions in parallel
    const results = await Promise.allSettled(
      enabledExhibitions.map(e => controlExhibition(e.id, command))
    );

    const successful = results.filter(r => r.status === 'fulfilled' && r.value.success).length;
    const failed = enabledExhibitions.length - successful;

    if (failed === 0) {
      showToast(`${command.toUpperCase()} sent to all ${successful} exhibitions`, 'success');
    } else {
      showToast(`${command.toUpperCase()}: ${successful} succeeded, ${failed} failed`, 'danger');
    }

    setTimeout(loadData, 2000);
  };

  const handleAction = async (deviceId: string, actionName: string, deviceName: string) => {
    try {
      showToast(`Executing ${actionName}...`, 'info');
      const result = await executeAction(deviceId, actionName);
      if (result.success) {
        showToast(`${actionName} executed on ${deviceName}`, 'success');
      } else {
        showToast(`${actionName} failed: ${result.error || 'Unknown error'}`, 'danger');
      }
    } catch {
      showToast('Network error', 'danger');
    }
  };

  // Navigation
  const scrollToExhibition = (exhibitionId: string) => {
    document.getElementById(`exhibition-${exhibitionId}`)?.scrollIntoView({ behavior: 'smooth' });
  };

  const toggleDeviceAccordion = (deviceId: string) => {
    setExpandedDevice(expandedDevice === deviceId ? null : deviceId);
  };

  // CRUD handlers
  const handleCreateExhibition = async () => {
    if (!newExhibitionName.trim()) return;
    try {
      await createExhibition(newExhibitionName.trim());
      showToast(`Exhibition "${newExhibitionName}" created`, 'success');
      setNewExhibitionName('');
      loadData();
    } catch {
      showToast('Failed to create exhibition', 'danger');
    }
  };

  const handleSaveExhibition = async (name: string) => {
    await createExhibition(name);
    showToast(`Exhibition "${name}" created`, 'success');
    loadData();
  };

  const handleSaveArtwork = async (exhibitionId: string, name: string) => {
    await createArtwork(exhibitionId, name);
    showToast(`Artwork "${name}" created`, 'success');
    loadData();
  };

  const handleSaveDevice = async (artworkId: string, data: any) => {
    await createDevice(artworkId, data);
    showToast(`Device "${data.name}" created`, 'success');
    loadData();
  };

  // Update handlers
  const handleUpdateExhibition = async (id: string, data: { name: string; enabled: boolean }) => {
    try {
      await updateExhibition(id, data);
      showToast(`Exhibition "${data.name}" updated`, 'success');
      loadData();
    } catch {
      showToast('Failed to update exhibition', 'danger');
    }
  };

  const handleUpdateArtwork = async (id: string, data: { name: string; enabled: boolean }) => {
    try {
      await updateArtwork(id, data);
      showToast(`Artwork "${data.name}" updated`, 'success');
      loadData();
    } catch {
      showToast('Failed to update artwork', 'danger');
    }
  };

  // Delete handlers (double-tap confirmation handled by ConfirmButton)
  const handleDeleteExhibition = async (exhibitionId: string, exhibitionName: string) => {
    try {
      await deleteExhibition(exhibitionId);
      showToast(`Exhibition "${exhibitionName}" deleted`, 'success');
      loadData();
    } catch {
      showToast('Failed to delete exhibition', 'danger');
    }
  };

  const handleDeleteArtwork = async (artworkId: string, artworkName: string) => {
    try {
      await deleteArtwork(artworkId);
      showToast(`Artwork "${artworkName}" deleted`, 'success');
      loadData();
    } catch {
      showToast('Failed to delete artwork', 'danger');
    }
  };

  // Device handlers
  const handleUpdateDevice = async (id: string, data: {
    name?: string;
    host?: string;
    port?: number;
    enabled?: boolean;
    automation_enabled?: boolean;
  }) => {
    try {
      await updateDevice(id, data);
      showToast(`Device "${data.name}" updated`, 'success');
      loadData();
    } catch {
      showToast('Failed to update device', 'danger');
    }
  };

  const handleDeleteDevice = async (id: string, name: string) => {
    try {
      await deleteDevice(id);
      showToast(`Device "${name}" deleted`, 'success');
      loadData();
    } catch {
      showToast('Failed to delete device', 'danger');
    }
  };

  const handleSaveDeviceAsTemplate = async (deviceId: string, templateName: string) => {
    try {
      await saveDeviceAsTemplate(deviceId, templateName);
      showToast(`Template "${templateName}" saved to library`, 'success');
      loadTemplates();
    } catch {
      showToast('Failed to save template', 'danger');
    }
  };

  // Add device modal opener
  const openAddDeviceModal = (exhibitionId: string, artworkId: string) => {
    const exhibition = exhibitions.find(e => e.id === exhibitionId);
    const artwork = exhibition?.artworks.find(a => a.id === artworkId);
    if (exhibition && artwork) {
      setAddDeviceContext({
        exhibitionId,
        exhibitionName: exhibition.name,
        artworkId,
        artworkName: artwork.name,
      });
    }
  };

  // Add artwork modal opener
  const openAddArtworkModal = (exhibitionId: string) => {
    const exhibition = exhibitions.find(e => e.id === exhibitionId);
    if (exhibition) {
      setAddArtworkContext({
        exhibitionId,
        exhibitionName: exhibition.name,
      });
    }
  };

  if (loading && exhibitions.length === 0) {
    return (
      <div className="d-flex justify-content-center align-items-center" style={{ height: '100vh' }}>
        <div className="spinner-border text-primary" role="status">
          <span className="visually-hidden">Loading...</span>
        </div>
      </div>
    );
  }

  return (
    <div className={editMode ? 'edit-mode' : ''}>
      {/* Toast */}
      {toast && <Toast message={toast.message} type={toast.type} />}

      {/* Header */}
      <Header
        editMode={editMode}
        onEditModeChange={setEditMode}
        onOpenCredentials={() => setShowCredentialsModal(true)}
        onOpenShellLibrary={() => setShowShellTemplatesModal(true)}
        onOpenEmailInventory={() => setShowEmailInventoryModal(true)}
        onOpenAdmin={() => setShowAdminModal(true)}
        onOpenLogs={() => openLogViewer()}
        onOpenTimeline={() => setShowTimeline(true)}
        onOpenAssets={() => setShowAssets(true)}
        showingLogs={showLogViewer}
        showingTimeline={showTimeline}
        showingAssets={showAssets}
      />

      {/* Error Banner */}
      {error && (
        <div className="alert alert-danger m-3 mb-0">{error}</div>
      )}

      {/* Empty State */}
      {exhibitions.length === 0 && !loading && (
        <EmptyState
          editMode={editMode}
          newExhibitionName={newExhibitionName}
          onNameChange={setNewExhibitionName}
          onSubmit={handleCreateExhibition}
        />
      )}

      {/* Exhibition Overview Cards */}
      <ExhibitionOverview
        exhibitions={exhibitions}
        editMode={editMode}
        onScrollTo={scrollToExhibition}
        onControl={handleExhibitionControl}
        onControlAll={handleAllControl}
        onAddExhibition={() => setShowAddExhibitionModal(true)}
      />

      {/* Exhibition Sections */}
      {(editMode ? exhibitions : exhibitions.filter(e => e.enabled)).map(exhibition => (
        <ExhibitionSection
          key={exhibition.id}
          exhibition={exhibition}
          editMode={editMode}
          expandedDevice={expandedDevice}
          pendingStates={pendingStates}
          onToggleDevice={toggleDeviceAccordion}
          onExhibitionControl={handleExhibitionControl}
          onArtworkControl={handleArtworkControl}
          onDeviceControl={handleDeviceControl}
          onDeviceAction={handleAction}
          onAddArtwork={() => openAddArtworkModal(exhibition.id)}
          onEditExhibition={setEditExhibitionData}
          onDeleteExhibition={handleDeleteExhibition}
          onDeleteArtwork={handleDeleteArtwork}
          onEditArtwork={setEditArtworkData}
          onAddDevice={(artworkId) => openAddDeviceModal(exhibition.id, artworkId)}
          onEditDevice={setEditDeviceData}
          onDeleteDevice={handleDeleteDevice}
          onViewDeviceLogs={openLogViewer}
        />
      ))}

      {/* State Timeline Page (Full Page) */}
      {showTimeline && (
        <StateTimelinePage
          onClose={() => setShowTimeline(false)}
          devices={allDevices}
        />
      )}

      {/* Asset Browser Page (Full Page) */}
      {showAssets && (
        <AssetBrowserPage
          onClose={() => setShowAssets(false)}
        />
      )}

      {/* Log Viewer (Full Page) */}
      {showLogViewer && (
        <LogViewer
          onClose={closeLogViewer}
          initialFilterDeviceId={logFilterDeviceId}
          devices={allDevices}
        />
      )}

      {/* Modals */}
      <AddExhibitionModal
        isOpen={showAddExhibitionModal}
        onClose={() => setShowAddExhibitionModal(false)}
        onSave={handleSaveExhibition}
      />

      {addArtworkContext && (
        <AddArtworkModal
          isOpen={true}
          exhibitionName={addArtworkContext.exhibitionName}
          exhibitionId={addArtworkContext.exhibitionId}
          onClose={() => setAddArtworkContext(null)}
          onSave={handleSaveArtwork}
        />
      )}

      {addDeviceContext && (
        <AddDeviceModal
          isOpen={true}
          exhibitionName={addDeviceContext.exhibitionName}
          artworkName={addDeviceContext.artworkName}
          artworkId={addDeviceContext.artworkId}
          onClose={() => setAddDeviceContext(null)}
          onSave={handleSaveDevice}
          credentials={credentials}
          templates={templates}
        />
      )}

      <EditExhibitionModal
        isOpen={editExhibitionData !== null}
        exhibition={editExhibitionData}
        onClose={() => setEditExhibitionData(null)}
        onSave={handleUpdateExhibition}
      />

      <EditArtworkModal
        isOpen={editArtworkData !== null}
        artwork={editArtworkData}
        onClose={() => setEditArtworkData(null)}
        onSave={handleUpdateArtwork}
      />

      <CredentialsModal
        isOpen={showCredentialsModal}
        onClose={() => {
          setShowCredentialsModal(false);
          loadCredentials(); // Refresh App-level credentials after modal closes
        }}
        fetchCredentials={fetchCredentials}
        createCredential={createCredential}
        updateCredential={updateCredential}
        deleteCredential={deleteCredential}
        showToast={showToast}
      />

      <EditDeviceModal
        isOpen={editDeviceData !== null}
        device={editDeviceData}
        onClose={() => setEditDeviceData(null)}
        onSave={handleUpdateDevice}
        onDelete={handleDeleteDevice}
        credentials={credentials}
        onSaveAsTemplate={handleSaveDeviceAsTemplate}
      />

      <ShellTemplatesModal
        isOpen={showShellTemplatesModal}
        onClose={() => setShowShellTemplatesModal(false)}
        fetchShellTemplates={fetchShellTemplates}
        createShellTemplate={createShellTemplate}
        updateShellTemplate={updateShellTemplate}
        deleteShellTemplate={deleteShellTemplate}
        showToast={showToast}
      />

      <EmailInventoryModal
        isOpen={showEmailInventoryModal}
        onClose={() => setShowEmailInventoryModal(false)}
        exhibitions={exhibitions}
        fetchEmailConfig={fetchEmailConfig}
        fetchInventoryPreview={fetchInventoryPreview}
        sendInventoryEmail={sendInventoryEmail}
        showToast={showToast}
      />

      <AdminModal
        isOpen={showAdminModal}
        onClose={() => setShowAdminModal(false)}
        showToast={showToast}
      />
    </div>
  );
}

export default App;
