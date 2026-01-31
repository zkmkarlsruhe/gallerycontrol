// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT
import type { ServiceHealth } from '../types';

interface ServiceHealthBannerProps {
  services: ServiceHealth[];
}

export function ServiceHealthBanner({ services }: ServiceHealthBannerProps) {
  // Filter to only show services that are not online
  const unhealthyServices = services.filter(s => s.status !== 'online');

  if (unhealthyServices.length === 0) {
    return null;
  }

  return (
    <div className="service-health-banner">
      {unhealthyServices.map(service => (
        <div
          key={service.service_id}
          className={`alert alert-${service.status === 'offline' ? 'danger' : 'warning'} d-flex align-items-center mb-2`}
          role="alert"
        >
          <i className={`bi ${service.status === 'offline' ? 'bi-exclamation-triangle-fill' : 'bi-exclamation-circle-fill'} me-2`}></i>
          <div className="flex-grow-1">
            <strong>{service.name}</strong>
            <span className="ms-2 text-muted">({service.description})</span>
            {service.error && (
              <span className="ms-2">- {service.error}</span>
            )}
            {service.affects_device_types.length > 0 && (
              <span className="ms-2 badge bg-secondary">
                Affects: {service.affects_device_types.join(', ')}
              </span>
            )}
          </div>
          <span className={`badge ${service.status === 'offline' ? 'bg-danger' : 'bg-warning'}`}>
            {service.status.toUpperCase()}
          </span>
        </div>
      ))}
    </div>
  );
}
