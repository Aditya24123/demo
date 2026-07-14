import { ACTIVE_PROJECT_STORAGE_KEY } from '../appStoreTypes';

export function readStoredProjectId(): string | null {
  try {
    return window.localStorage.getItem(ACTIVE_PROJECT_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function storeActiveProjectId(projectId: string | null): void {
  try {
    if (projectId) window.localStorage.setItem(ACTIVE_PROJECT_STORAGE_KEY, projectId);
    else window.localStorage.removeItem(ACTIVE_PROJECT_STORAGE_KEY);
  } catch {
    // Storage can be unavailable in hardened browser contexts.
  }
}

let _toastSeq = 0;
export function nextToastId(): string {
  _toastSeq += 1;
  return `toast-${_toastSeq}`;
}
