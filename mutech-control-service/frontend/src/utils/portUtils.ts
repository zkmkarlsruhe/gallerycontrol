/**
 * Port conversion utilities for outlet-based devices (NETIO, ANEL).
 *
 * Convention:
 * - Database stores 0-indexed ports (0, 1, 2...)
 * - UI displays 1-indexed for users (Port 1, Port 2, Port 3...)
 */

export const portUtils = {
  /** Convert 0-indexed DB port to 1-indexed UI display */
  dbToUI: (dbPort: number | null | undefined): number => (dbPort ?? 0) + 1,

  /** Convert 1-indexed UI value to 0-indexed DB port */
  uiToDB: (uiPort: number): number => uiPort - 1,
};
