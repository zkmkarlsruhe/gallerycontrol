// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT
import { useState, useEffect } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE || '';

let cachedTemplates: Record<string, string> | null = null;

/**
 * Hook to get hostname template for a device type from /info endpoint.
 * Returns the template string or empty string if not configured.
 */
export function useHostnameTemplate(deviceType: 'netio' | 'anel'): string {
  const [template, setTemplate] = useState('');

  useEffect(() => {
    if (cachedTemplates !== null) {
      setTemplate(cachedTemplates[deviceType] ?? '');
      return;
    }

    fetch(`${API_BASE}/info`)
      .then(res => res.json())
      .then(data => {
        const templates: Record<string, string> = data.hostname_templates || {};
        cachedTemplates = templates;
        setTemplate(templates[deviceType] || '');
      })
      .catch(() => {
        cachedTemplates = {};
      });
  }, [deviceType]);

  return template;
}
