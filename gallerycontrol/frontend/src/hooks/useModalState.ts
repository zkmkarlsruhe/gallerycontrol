// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT

import { useState, useCallback } from 'react';

/**
 * All modal names used in the application.
 */
export type ModalName =
  | 'addExhibition'
  | 'credentials'
  | 'shellTemplates'
  | 'emailInventory'
  | 'admin'
  | 'quickSchedule'
  | 'editExhibition'
  | 'editArtwork'
  | 'editDevice'
  | 'addArtwork'
  | 'addDevice'
  | 'schedule'
  | 'protection'
  | 'displayLinks';

interface ModalState<T = unknown> {
  isOpen: boolean;
  context: T | null;
}

type ModalStates = {
  [K in ModalName]: ModalState;
};

interface UseModalStateReturn {
  /** Check if a modal is open */
  isOpen: (name: ModalName) => boolean;
  /** Open a modal, optionally with context data */
  open: <T>(name: ModalName, context?: T) => void;
  /** Close a modal and clear its context */
  close: (name: ModalName) => void;
  /** Get the context data for a modal */
  getContext: <T>(name: ModalName) => T | null;
}

const createInitialState = (): ModalStates => ({
  addExhibition: { isOpen: false, context: null },
  credentials: { isOpen: false, context: null },
  shellTemplates: { isOpen: false, context: null },
  emailInventory: { isOpen: false, context: null },
  admin: { isOpen: false, context: null },
  quickSchedule: { isOpen: false, context: null },
  editExhibition: { isOpen: false, context: null },
  editArtwork: { isOpen: false, context: null },
  editDevice: { isOpen: false, context: null },
  addArtwork: { isOpen: false, context: null },
  addDevice: { isOpen: false, context: null },
  schedule: { isOpen: false, context: null },
  protection: { isOpen: false, context: null },
  displayLinks: { isOpen: false, context: null },
});

/**
 * Custom hook for managing modal state across the application.
 * Consolidates multiple useState calls into a single state manager.
 */
export function useModalState(): UseModalStateReturn {
  const [modalStates, setModalStates] = useState<ModalStates>(createInitialState);

  const isOpen = useCallback((name: ModalName): boolean => {
    return modalStates[name]?.isOpen ?? false;
  }, [modalStates]);

  const open = useCallback(<T,>(name: ModalName, context?: T): void => {
    setModalStates(prev => ({
      ...prev,
      [name]: { isOpen: true, context: context ?? null },
    }));
  }, []);

  const close = useCallback((name: ModalName): void => {
    setModalStates(prev => ({
      ...prev,
      [name]: { isOpen: false, context: null },
    }));
  }, []);

  const getContext = useCallback(<T,>(name: ModalName): T | null => {
    return (modalStates[name]?.context as T) ?? null;
  }, [modalStates]);

  return {
    isOpen,
    open,
    close,
    getContext,
  };
}
