// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT
import { useState, useEffect, useRef } from 'react';

interface TouchSafeButtonProps {
  onClick: () => void;
  className?: string;
  children: React.ReactNode;
  confirmText?: string;
  timeout?: number;
}

const MOBILE_BREAKPOINT = 900;

export function TouchSafeButton({
  onClick,
  className = '',
  children,
  confirmText,
  timeout = 2000,
}: TouchSafeButtonProps) {
  const [isMobile, setIsMobile] = useState(() =>
    typeof window !== 'undefined' && window.innerWidth < MOBILE_BREAKPOINT
  );
  const [confirming, setConfirming] = useState(false);
  const timeoutRef = useRef<number | null>(null);

  // Listen for screen resize to update mobile detection
  useEffect(() => {
    const mediaQuery = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT}px)`);

    const handleChange = (e: MediaQueryListEvent | MediaQueryList) => {
      setIsMobile(e.matches);
      // Reset confirming state when switching modes
      if (!e.matches && confirming) {
        setConfirming(false);
        if (timeoutRef.current) {
          clearTimeout(timeoutRef.current);
        }
      }
    };

    // Set initial state
    handleChange(mediaQuery);

    // Add listener (using addEventListener for modern browsers)
    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener('change', handleChange);
    } else {
      // Fallback for older browsers
      mediaQuery.addListener(handleChange);
    }

    return () => {
      if (mediaQuery.removeEventListener) {
        mediaQuery.removeEventListener('change', handleChange);
      } else {
        mediaQuery.removeListener(handleChange);
      }
    };
  }, [confirming]);

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  const handleClick = () => {
    if (!isMobile) {
      // Desktop: single click executes immediately
      onClick();
      return;
    }

    // Mobile: require double-tap
    if (confirming) {
      // Second tap - execute action
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      setConfirming(false);
      onClick();
    } else {
      // First tap - enter confirm state
      setConfirming(true);
      timeoutRef.current = window.setTimeout(() => {
        setConfirming(false);
      }, timeout);
    }
  };

  // Generate confirm text if not provided (e.g., "ON" -> "ON?")
  // Only append ? if children is a simple string, otherwise use "Tap?"
  const displayConfirmText = confirmText ||
    (typeof children === 'string' ? `${children}?` : 'Tap?');

  return (
    <button
      type="button"
      className={`${className} ${confirming ? 'confirming' : ''}`}
      onClick={handleClick}
    >
      {confirming ? displayConfirmText : children}
    </button>
  );
}
