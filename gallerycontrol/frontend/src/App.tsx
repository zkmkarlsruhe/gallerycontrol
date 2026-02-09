// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT
import { useState, useEffect, useCallback, useMemo } from 'react';
import { useApi } from './hooks/useApi';
import { useDeviceControl } from './hooks/useDeviceControl';
import { useDataLoader } from './hooks/useDataLoader';
import type { Exhibition, Device, Artwork, ProtectionConfig } from './types';
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
  ServiceHealthBanner,
} from './components';
import { EmailInventoryModal } from './components/modals/EmailInventoryModal';
import { AdminModal } from './components/modals/AdminModal';
import { ScheduleManagerModal } from './components/modals/ScheduleManagerModal';
import { QuickScheduleModal } from './components/modals/QuickScheduleModal';
import { ProtectionConfigModal } from './components/modals/ProtectionConfigModal';
import { DisplayLinksModal } from './components/modals/DisplayLinksModal';
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

interface ScheduleModalContext {
  type: 'device' | 'artwork' | 'exhibition' | 'all';
  id: string;
  name: string;
  actions?: { name: string }[];
}

// View state type - which page/view is currently active
type ViewType = 'main' | 'timeline' | 'assets' | 'logs';

// Parse URL hash to get view and edit mode
function parseHash(): { view: ViewType; editMode: boolean } {
  const hash = window.location.hash.slice(1).toLowerCase(); // Remove # and lowercase
  switch (hash) {
    case 'edit':
      return { view: 'main', editMode: true };
    case 'timeline':
      return { view: 'timeline', editMode: false };
    case 'assets':
      return { view: 'assets', editMode: false };
    case 'logs':
      return { view: 'logs', editMode: false };
    default:
      return { view: 'main', editMode: false };
  }
}

// Build URL hash from view and edit mode
function buildHash(view: ViewType, editMode: boolean): string {
  if (view === 'main' && editMode) return '#edit';
  if (view === 'timeline') return '#timeline';
  if (view === 'assets') return '#assets';
  if (view === 'logs') return '#logs';
  return '';
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
    fetchServiceHealth,
  } = useApi();

  const [editMode, setEditMode] = useState(() => parseHash().editMode);
  const [expandedDevice, setExpandedDevice] = useState<string | null>(null);
  const [toast, setToast] = useState<ToastState | null>(null);
  const [newExhibitionName, setNewExhibitionName] = useState('');

  // Toast helper
  const showToast = useCallback((message: string, type: 'success' | 'danger' | 'info' = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  }, []);

  // Use data loader hook for fetching and auto-refreshing data
  const {
    exhibitions,
    credentials,
    templates,
    serviceHealth,
    loading,
    error,
    loadData,
    loadCredentials,
    loadTemplates,
  } = useDataLoader({
    fetchExhibitions,
    fetchCredentials,
    fetchShellTemplates,
    fetchServiceHealth,
  });

  // Use device control hook for control handlers and pending states
  const {
    pendingStates,
    handleDeviceControl,
    handleArtworkControl,
    handleExhibitionControl,
    handleAllControl,
    handleAction,
  } = useDeviceControl({
    exhibitions,
    controlDevice,
    controlArtwork,
    controlExhibition,
    executeAction,
    showToast,
    loadData,
  });

  // Modal states
  const [showAddExhibitionModal, setShowAddExhibitionModal] = useState(false);
  const [showCredentialsModal, setShowCredentialsModal] = useState(false);
  const [showShellTemplatesModal, setShowShellTemplatesModal] = useState(false);
  const [showEmailInventoryModal, setShowEmailInventoryModal] = useState(false);
  const [showAdminModal, setShowAdminModal] = useState(false);
  const [showQuickScheduleModal, setShowQuickScheduleModal] = useState(false);

  // View state - which page/view is currently active
  const [currentView, setCurrentView] = useState<ViewType>(() => parseHash().view);
  const [logFilterDeviceId, setLogFilterDeviceId] = useState<string | null>(null);

  const [editExhibitionData, setEditExhibitionData] = useState<Exhibition | null>(null);
  const [editArtworkData, setEditArtworkData] = useState<{
    id: string;
    name: string;
    enabled: boolean;
    timeslice_enabled: boolean;
    schedules_enabled: boolean;
    protection_config?: ProtectionConfig | null;
  } | null>(null);
  const [editDeviceData, setEditDeviceData] = useState<Device | null>(null);
  const [addArtworkContext, setAddArtworkContext] = useState<AddArtworkContext | null>(null);
  const [addDeviceContext, setAddDeviceContext] = useState<AddDeviceContext | null>(null);
  const [scheduleModalContext, setScheduleModalContext] = useState<ScheduleModalContext | null>(null);
  const [protectionArtwork, setProtectionArtwork] = useState<Artwork | null>(null);
  const [displayLinksArtwork, setDisplayLinksArtwork] = useState<Artwork | null>(null);

  // Extract all devices for debug filter dropdown and timeline
  const allDevices = useMemo(() => {
    const devices: Array<{ id: string; name: string; type: string; host: string; port: number | null; artworkName: string; exhibitionName: string; state: number }> = [];
    for (const exhibition of exhibitions) {
      for (const artwork of exhibition.artworks) {
        for (const device of artwork.devices) {
          devices.push({
            id: device.id,
            name: device.name,
            type: device.device_type,
            host: device.host,
            port: device.port,
            artworkName: artwork.name,
            exhibitionName: exhibition.name,
            state: device.state,
          });
        }
      }
    }
    return devices;
  }, [exhibitions]);

  // Extract raw devices for AddDeviceModal (to check used ports)
  const existingDevices = useMemo(() => {
    const devices: Device[] = [];
    for (const exhibition of exhibitions) {
      for (const artwork of exhibition.artworks) {
        devices.push(...artwork.devices);
      }
    }
    return devices;
  }, [exhibitions]);

  // Navigation with browser history support
  const navigateTo = useCallback((view: ViewType, edit: boolean = false) => {
    const newHash = buildHash(view, edit);
    window.history.pushState(null, '', newHash || window.location.pathname);
    setCurrentView(view);
    setEditMode(edit);
  }, []);

  const openLogViewer = useCallback((deviceId?: string | null) => {
    setLogFilterDeviceId(deviceId || null);
    navigateTo('logs');
  }, [navigateTo]);

  const closeLogViewer = useCallback(() => {
    navigateTo('main');
    setLogFilterDeviceId(null);
  }, [navigateTo]);

  // Sync URL hash with view/edit mode
  useEffect(() => {
    const newHash = buildHash(currentView, editMode);
    if (window.location.hash !== newHash) {
      window.history.replaceState(null, '', newHash || window.location.pathname);
    }
  }, [currentView, editMode]);

  // Handle browser back/forward navigation
  useEffect(() => {
    const handlePopState = () => {
      const { view, editMode: newEditMode } = parseHash();
      setCurrentView(view);
      setEditMode(newEditMode);
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

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
  const handleUpdateExhibition = async (
    id: string,
    data: { name: string; enabled: boolean; schedules_enabled: boolean }
  ) => {
    try {
      await updateExhibition(id, data);
      showToast(`Exhibition "${data.name}" updated`, 'success');
      loadData();
    } catch {
      showToast('Failed to update exhibition', 'danger');
    }
  };

  const handleUpdateArtwork = async (
    id: string,
    data: {
      name: string;
      enabled: boolean;
      timeslice_enabled: boolean;
      schedules_enabled: boolean;
      protection_config?: ProtectionConfig | null;
    }
  ) => {
    try {
      await updateArtwork(id, data);
      showToast(`Artwork "${data.name}" updated`, 'success');
      loadData();
    } catch {
      showToast('Failed to update artwork', 'danger');
    }
  };

  const handleUpdateProtectionConfig = async (artworkId: string, config: ProtectionConfig | null) => {
    try {
      await updateArtwork(artworkId, { protection_config: config });
      showToast(config ? 'Protection config updated' : 'Protection config removed', 'success');
      loadData();
    } catch {
      showToast('Failed to update protection config', 'danger');
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

  // Open schedule manager modal
  const handleOpenSchedules = useCallback((id: string, type: 'exhibition' | 'artwork' | 'device', name: string) => {
    // For devices, get available actions
    let actions: { name: string }[] | undefined;
    if (type === 'device') {
      for (const exhibition of exhibitions) {
        for (const artwork of exhibition.artworks) {
          const device = artwork.devices.find(d => d.id === id);
          if (device?.actions) {
            actions = device.actions;
            break;
          }
        }
        if (actions) break;
      }
    }

    setScheduleModalContext({
      type,
      id,
      name,
      actions,
    });
  }, [exhibitions]);

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
        onEditModeChange={(edit) => navigateTo('main', edit)}
        onOpenCredentials={() => setShowCredentialsModal(true)}
        onOpenShellLibrary={() => setShowShellTemplatesModal(true)}
        onOpenEmailInventory={() => setShowEmailInventoryModal(true)}
        onOpenAdmin={() => setShowAdminModal(true)}
        onOpenLogs={() => openLogViewer()}
        onOpenTimeline={() => navigateTo('timeline')}
        onOpenAssets={() => navigateTo('assets')}
        onOpenQuickSchedule={() => setShowQuickScheduleModal(true)}
        showingLogs={currentView === 'logs'}
        showingTimeline={currentView === 'timeline'}
        showingAssets={currentView === 'assets'}
      />

      {/* Main Content View */}
      {currentView === 'main' && (
        <div className="main-content">
          {/* Service Health Banner */}
          <div className="m-3 mb-0">
            <ServiceHealthBanner services={serviceHealth} />
          </div>

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
              onOpenSchedules={handleOpenSchedules}
              onEditProtection={setProtectionArtwork}
              onOpenDisplayLinks={setDisplayLinksArtwork}
            />
          ))}
        </div>
      )}

      {/* State Timeline View */}
      {currentView === 'timeline' && (
        <StateTimelinePage
          onClose={() => navigateTo('main')}
          devices={allDevices}
        />
      )}

      {/* Asset Browser View */}
      {currentView === 'assets' && (
        <AssetBrowserPage
          onClose={() => navigateTo('main')}
        />
      )}

      {/* Log Viewer View */}
      {currentView === 'logs' && (
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
          existingDevices={existingDevices}
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
        templates={templates}
        onSaveAsTemplate={handleSaveDeviceAsTemplate}
        existingDevices={existingDevices}
        satelliteName={
          // Find satellite name for this device's exhibition
          editDeviceData
            ? exhibitions
                .find(e => e.artworks.some(a => a.devices.some(d => d.id === editDeviceData.id)))
                ?.satellite?.name ?? null
            : null
        }
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

      <QuickScheduleModal
        isOpen={showQuickScheduleModal}
        onClose={() => setShowQuickScheduleModal(false)}
        exhibitions={exhibitions}
        showToast={showToast}
      />

      {scheduleModalContext && (
        <ScheduleManagerModal
          isOpen={true}
          onClose={() => setScheduleModalContext(null)}
          targetType={scheduleModalContext.type}
          targetId={scheduleModalContext.id}
          targetName={scheduleModalContext.name}
          availableActions={scheduleModalContext.actions}
          showToast={showToast}
        />
      )}

      <ProtectionConfigModal
        isOpen={protectionArtwork !== null}
        artwork={protectionArtwork}
        onClose={() => setProtectionArtwork(null)}
        onSave={handleUpdateProtectionConfig}
      />

      {displayLinksArtwork && (
        <DisplayLinksModal
          isOpen={displayLinksArtwork !== null}
          onClose={() => setDisplayLinksArtwork(null)}
          artworkId={displayLinksArtwork.id}
          artworkName={displayLinksArtwork.name}
        />
      )}
    </div>
  );
}

export default App;
