// @ts-nocheck
import { api } from '@/lib/api';
import { normalizeProject } from '../../bridge/normalizers';
import type { AppState } from '../appStoreTypes';
import { readStoredProjectId, storeActiveProjectId } from './helpers';

type SetState = any;
type GetState = any;

export function createProjectActions(set: SetState, get: GetState): Partial<AppState> {
  return {
  loadProjects: async () => {
    set({ projectsLoading: true, projectsError: null });
    try {
      const data = await api.getProjects();
      const projects: ProjectVM[] = (data?.projects || []).map(normalizeProject);
      const preferredId = get().activeProjectId || readStoredProjectId();
      const activeProjectId = preferredId && projects.some((project) => project.projectId === preferredId) ? preferredId : null;
      storeActiveProjectId(activeProjectId);
      set({ projects, activeProjectId, projectsLoading: false });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Could not load projects';
      set({ projectsLoading: false, projectsError: message });
      throw err;
    }
  },

  createProject: async (input) => {
    try {
      const project = normalizeProject(await api.createProject(input));
      set((state) => ({
        projects: [project, ...state.projects.filter((item) => item.projectId !== project.projectId)],
        activeProjectId: project.projectId,
        projectsError: null,
      }));
      storeActiveProjectId(project.projectId);
      const sessionId = get().currentSessionId;
      if (sessionId && !sessionId.startsWith('local-')) {
        void api.patchSession(sessionId, { context: { project_id: project.projectId } }).catch(() => {});
      }
      return project;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Could not create project';
      set({ projectsError: message });
      throw err;
    }
  },

  selectProject: (projectId) => {
    storeActiveProjectId(projectId);
    set({ activeProjectId: projectId });
    const sessionId = get().currentSessionId;
    if (sessionId && !sessionId.startsWith('local-')) {
      void api.patchSession(sessionId, { context: { project_id: projectId } }).catch(() => {});
    }
  },

  renameProject: async (projectId, name) => {
    const clean = String(name || '').trim();
    if (!clean) return;
    try {
      const updated = normalizeProject(await api.patchProject(projectId, { name: clean }));
      set((state) => ({
        projects: state.projects.map((item) => (item.projectId === projectId ? updated : item)),
      }));
      get().addToast('Project renamed', 'success');
    } catch {
      get().addToast('Could not rename project', 'error');
    }
  },

  deleteProject: async (projectId) => {
    try {
      await api.deleteProject(projectId);
      set((state) => {
        const projects = state.projects.filter((item) => item.projectId !== projectId);
        const activeProjectId = state.activeProjectId === projectId ? null : state.activeProjectId;
        if (activeProjectId === null) storeActiveProjectId(null);
        return { projects, activeProjectId };
      });
      get().addToast('Project deleted', 'success');
    } catch {
      get().addToast('Could not delete project', 'error');
    }
  },

  };
}
