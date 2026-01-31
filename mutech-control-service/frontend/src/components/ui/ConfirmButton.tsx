// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT
import { useState, useEffect, useRef } from 'react';

interface ConfirmButtonProps {
  onConfirm: () => void;
  className?: string;
  children: React.ReactNode;
  confirmText?: string;
  timeout?: number;
  disabled?: boolean;
  title?: string;
}

export function ConfirmButton({
  onConfirm,
  className = '',
  children,
  confirmText = 'Confirm?',
  timeout = 2000,
  disabled = false,
  title,
}: ConfirmButtonProps) {
  const [confirming, setConfirming] = useState(false);
  const timeoutRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  const handleClick = () => {
    if (confirming) {
      // Second click - execute action
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      setConfirming(false);
      onConfirm();
    } else {
      // First click - enter confirm state
      setConfirming(true);
      timeoutRef.current = window.setTimeout(() => {
        setConfirming(false);
      }, timeout);
    }
  };

  return (
    <button
      className={`${className} ${confirming ? 'confirming' : ''}`}
      onClick={handleClick}
      disabled={disabled}
      title={title}
    >
      {confirming ? confirmText : children}
    </button>
  );
}
