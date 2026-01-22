/**
 * Reachability status indicator for device forms.
 */

import type { ReachabilityStatus } from '../../../hooks/useHostReachability';

interface ReachabilityIndicatorProps {
  status: ReachabilityStatus;
  error?: string | null;
}

export function ReachabilityIndicator({ status, error }: ReachabilityIndicatorProps) {
  return (
    <span className={`reachability-indicator status-${status}`} title={error || ''}>
      {status === 'checking' && <i className="bi bi-arrow-repeat spin"></i>}
      {status === 'reachable' && <i className="bi bi-check-circle-fill"></i>}
      {status === 'unreachable' && <i className="bi bi-x-circle-fill"></i>}
    </span>
  );
}

/**
 * Get CSS class for host input based on reachability status.
 */
export function getHostInputClass(status: ReachabilityStatus): string {
  if (status === 'unreachable') return 'is-invalid';
  if (status === 'reachable') return 'is-valid';
  return '';
}
