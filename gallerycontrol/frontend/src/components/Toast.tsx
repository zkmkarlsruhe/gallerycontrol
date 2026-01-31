// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT
interface ToastProps {
  message: string;
  type: 'success' | 'danger' | 'info';
}

export function Toast({ message, type }: ToastProps) {
  return (
    <div className={`toast-notification bg-${type}`}>
      {message}
    </div>
  );
}
