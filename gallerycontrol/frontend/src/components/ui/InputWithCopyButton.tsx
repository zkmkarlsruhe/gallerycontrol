// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT
import { useState, useCallback } from 'react';

interface InputWithCopyButtonProps {
  value: string;
  label?: string;
  readOnly?: boolean;
  className?: string;
}

export function InputWithCopyButton({
  value,
  label,
  readOnly = true,
  className = '',
}: InputWithCopyButtonProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      // Fallback for older browsers
      const textarea = document.createElement('textarea');
      textarea.value = value;
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();
      try {
        document.execCommand('copy');
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      } catch {
        console.error('Failed to copy text');
      }
      document.body.removeChild(textarea);
    }
  }, [value]);

  return (
    <div className={`input-with-copy ${className}`}>
      {label && <label className="form-label">{label}</label>}
      <div className="input-group">
        <input
          type="text"
          className="form-control"
          value={value}
          readOnly={readOnly}
          onClick={(e) => (e.target as HTMLInputElement).select()}
        />
        <button
          type="button"
          className={`btn ${copied ? 'btn-success' : 'btn-outline-secondary'}`}
          onClick={handleCopy}
          title={copied ? 'Copied!' : 'Copy to clipboard'}
        >
          <i className={`bi ${copied ? 'bi-check-lg' : 'bi-clipboard'}`}></i>
        </button>
      </div>
    </div>
  );
}
