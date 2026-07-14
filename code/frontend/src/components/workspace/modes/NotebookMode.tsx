import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Eye, EyeOff, FileStack } from 'lucide-react';
import { api } from '@/lib/api';
import { useCatalystProjects } from '@/catalyst/bridge/hooks';
import { useAppStore } from '@/catalyst/ui-state/appStore';
import { useLayoutStore } from '@/catalyst/ui-state/layoutStore';
import { AgentChatBody } from '../AgentChatBody';
import { ProjectCreateDialog } from '../ProjectCreateDialog';
import { ProjectFileTree, type WorkspaceFile } from './ProjectFileTree';

const DEFAULT_NOTEBOOK_PATH = 'notebook/research.md';
const FILES_OPEN_KEY = 'catalyst-notebook-files-open';
const AUTOSAVE_MS = 700;

// Icons8 glyphs (ios-glyphs) ? white for dark UI.
const ICON_SAVING = 'https://img.icons8.com/ios-glyphs/30/ffffff/pull-request.png';
const ICON_SAVED = 'https://img.icons8.com/ios-glyphs/30/ffffff/checkmark--v1.png';

type WorkspaceSnapshot = {
  folders: string[];
  files: WorkspaceFile[];
  codex: {
    thread_id?: string | null;
    last_run_at?: string | null;
    runtime?: { available?: boolean; sdk_installed?: boolean };
  };
};

type SaveState = 'saved' | 'saving' | 'error';

function isNotebookPath(path: string): boolean {
  return path === DEFAULT_NOTEBOOK_PATH || path.endsWith('/research.md');
}

function readFilesOpenDefault(): boolean {
  if (typeof window === 'undefined') return false;
  return window.localStorage.getItem(FILES_OPEN_KEY) === '1';
}

export function NotebookMode() {
  const { projects, activeProjectId, loadProjects, selectProject } = useCatalystProjects();
  const addToast = useAppStore((s) => s.addToast);
  const project = projects.find((item) => item.projectId === activeProjectId) || null;

  const [snapshot, setSnapshot] = useState<WorkspaceSnapshot | null>(null);
  const [selectedPath, setSelectedPath] = useState(DEFAULT_NOTEBOOK_PATH);
  const [content, setContent] = useState('');
  const [savedContent, setSavedContent] = useState('');
  const [loading, setLoading] = useState(false);
  const [saveState, setSaveState] = useState<SaveState>('saved');
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [filesOpen, setFilesOpen] = useState(readFilesOpenDefault);
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(() => new Set());
  const [createBusy, setCreateBusy] = useState(false);
  const [previewMarkdown, setPreviewMarkdown] = useState(false);

  const dirty = content !== savedContent;
  const files = useMemo(() => snapshot?.files || [], [snapshot]);
  const isMarkdownFile = /\.md$/i.test(selectedPath);

  const contentRef = useRef(content);
  const savedRef = useRef(savedContent);
  const pathRef = useRef(selectedPath);
  const projectRef = useRef(activeProjectId);
  contentRef.current = content;
  savedRef.current = savedContent;
  pathRef.current = selectedPath;
  projectRef.current = activeProjectId;

  const setFilesOpenPersist = useCallback((open: boolean) => {
    setFilesOpen(open);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(FILES_OPEN_KEY, open ? '1' : '0');
    }
  }, []);

  const loadFileContent = useCallback(async (projectId: string, path: string) => {
    if (isNotebookPath(path) && path === DEFAULT_NOTEBOOK_PATH) {
      const notebook = (await api.getProjectNotebook(projectId)) as { content?: string; path?: string };
      return {
        path: notebook.path || DEFAULT_NOTEBOOK_PATH,
        content: String(notebook.content ?? ''),
      };
    }
    const file = (await api.getProjectFile(projectId, path)) as { content: string; path?: string };
    return { path: file.path || path, content: String(file.content ?? '') };
  }, []);

  const refreshSnapshot = useCallback(async (projectId: string) => {
    const next = (await api.getProjectWorkspace(projectId)) as WorkspaceSnapshot;
    setSnapshot(next);
    return next;
  }, []);

  const load = useCallback(async () => {
    if (!activeProjectId) return;
    setLoading(true);
    setError(null);
    try {
      const path = selectedPath || DEFAULT_NOTEBOOK_PATH;
      const [nextSnapshot, file] = await Promise.all([
        api.getProjectWorkspace(activeProjectId) as Promise<WorkspaceSnapshot>,
        loadFileContent(activeProjectId, path),
      ]);
      setSnapshot(nextSnapshot);
      setSelectedPath(file.path);
      setContent(file.content);
      setSavedContent(file.content);
      setSaveState('saved');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not load project workspace');
    } finally {
      setLoading(false);
    }
  }, [activeProjectId, loadFileContent, selectedPath]);

  useEffect(() => {
    if (!projects.length) void loadProjects();
  }, [loadProjects, projects.length]);

  useEffect(() => {
    if (!activeProjectId) return;
    setSelectedPath(DEFAULT_NOTEBOOK_PATH);
    setContent('');
    setSavedContent('');
    setError(null);
    setSaveState('saved');
    setPreviewMarkdown(false);
    setExpandedFolders(new Set());
  }, [activeProjectId]);

  useEffect(() => {
    if (!activeProjectId) return undefined;
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [activeProjectId, selectedPath, load]);

  useEffect(() => {
    const onRefresh = () => void load();
    window.addEventListener('catalyst:project-refresh', onRefresh);
    return () => window.removeEventListener('catalyst:project-refresh', onRefresh);
  }, [load]);

  const persistContent = useCallback(async (projectId: string, path: string, text: string) => {
    if (path === DEFAULT_NOTEBOOK_PATH) {
      await api.putProjectNotebook(projectId, text);
    } else {
      await api.putProjectFile(projectId, path, text);
    }
  }, []);

  // Live autosave ? no manual save button.
  useEffect(() => {
    if (!activeProjectId || !dirty) return undefined;
    setSaveState('saving');
    const timer = window.setTimeout(() => {
      const projectId = projectRef.current;
      const path = pathRef.current;
      const text = contentRef.current;
      if (!projectId || text === savedRef.current) {
        setSaveState('saved');
        return;
      }
      void (async () => {
        try {
          await persistContent(projectId, path, text);
          // Only mark saved if content hasn't moved on again.
          if (contentRef.current === text && pathRef.current === path) {
            setSavedContent(text);
            setSaveState('saved');
          }
        } catch (cause) {
          const message = cause instanceof Error ? cause.message : 'Autosave failed';
          setError(message);
          setSaveState('error');
        }
      })();
    }, AUTOSAVE_MS);
    return () => window.clearTimeout(timer);
  }, [activeProjectId, content, dirty, persistContent]);

  const openFile = async (path: string) => {
    if (!activeProjectId || path === selectedPath) return;
    // Flush pending edits before switching.
    if (dirty) {
      try {
        setSaveState('saving');
        await persistContent(activeProjectId, selectedPath, content);
        setSavedContent(content);
        setSaveState('saved');
      } catch {
        if (!window.confirm('Unsaved changes could not be saved. Switch file anyway?')) return;
      }
    }
    setLoading(true);
    setError(null);
    try {
      const file = await loadFileContent(activeProjectId, path);
      // Material artifacts open in the main structure viewer (not as JSON text only).
      if (/\.catalyst\.json$/i.test(file.path) || file.content.includes('"catalyst_material"')) {
        try {
          const art = JSON.parse(file.content) as { type?: string; material_id?: string; formula_pretty?: string };
          if (art?.type === 'catalyst_material' && art.material_id) {
            const selectNode = useAppStore.getState().selectNode;
            const setRailMode = useLayoutStore.getState().setRailMode;
            const setWorkspaceTab = useLayoutStore.getState().setWorkspaceTab;
            setRailMode('home');
            setWorkspaceTab('structure');
            await selectNode(String(art.material_id));
            addToast(`Opened ${art.formula_pretty || art.material_id} in structure viewer`, 'success');
            setSelectedPath(file.path);
            setContent(file.content);
            setSavedContent(file.content);
            setSaveState('saved');
            return;
          }
        } catch {
          /* fall through to normal editor */
        }
      }
      setSelectedPath(file.path);
      setContent(file.content);
      setSavedContent(file.content);
      setSaveState('saved');
      const root = file.path.split('/')[0];
      if (root) setExpandedFolders((prev) => new Set(prev).add(root));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not open project file');
    } finally {
      setLoading(false);
    }
  };

  const createFile = async (path: string) => {
    if (!activeProjectId) return;
    setCreateBusy(true);
    setError(null);
    try {
      await api.putProjectFile(activeProjectId, path, '');
      await refreshSnapshot(activeProjectId);
      setExpandedFolders((prev) => new Set(prev).add(path.split('/')[0]));
      setFilesOpenPersist(true);
      await openFile(path);
      addToast(`Created ${path}`, 'success');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not create file');
    } finally {
      setCreateBusy(false);
    }
  };

  const createFolder = async (path: string) => {
    if (!activeProjectId) return;
    setCreateBusy(true);
    setError(null);
    try {
      await api.createProjectFolder(activeProjectId, path);
      await refreshSnapshot(activeProjectId);
      setExpandedFolders((prev) => new Set(prev).add(path.split('/')[0] || 'files'));
      setFilesOpenPersist(true);
      addToast(`Folder ${path}`, 'success');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not create folder');
    } finally {
      setCreateBusy(false);
    }
  };

  const toggleFolder = (folder: string) => {
    setExpandedFolders((prev) => {
      const next = new Set(prev);
      if (next.has(folder)) next.delete(folder);
      else next.add(folder);
      return next;
    });
  };

  if (!project || !activeProjectId) {
    return (
      <section className="jarvis-notebook-empty">
        <div>
          <h1>Open a project notebook</h1>
          <p>Projects own notebook notes, files, artifacts, runs, and a workspace agent thread.</p>
          <div className="jarvis-notebook-empty-actions">
            <button type="button" className="jarvis-primary-button" onClick={() => setCreateOpen(true)}>
              Create project
            </button>
            {projects.length ? (
              <div className="jarvis-notebook-project-list">
                {projects.slice(0, 8).map((item) => (
                  <button
                    key={item.projectId}
                    type="button"
                    className="jarvis-secondary-button"
                    onClick={() => {
                      selectProject(item.projectId);
                      setSelectedPath(DEFAULT_NOTEBOOK_PATH);
                    }}
                  >
                    Open {item.name}
                  </button>
                ))}
              </div>
            ) : null}
          </div>
        </div>
        {createOpen ? (
          <ProjectCreateDialog
            open
            onClose={() => setCreateOpen(false)}
            onCreated={(created) => {
              setCreateOpen(false);
              selectProject(created.projectId);
              setSelectedPath(DEFAULT_NOTEBOOK_PATH);
            }}
          />
        ) : null}
      </section>
    );
  }

  return (
    <section className="jarvis-notebook-shell">
      <div
        className="jarvis-notebook-grid"
        style={{
          gridTemplateColumns: filesOpen
            ? '220px minmax(0, 1fr) minmax(320px, 400px)'
            : 'minmax(0, 1fr) minmax(320px, 400px)',
        }}
      >
        {filesOpen ? (
          <ProjectFileTree
            open
            onClose={() => setFilesOpenPersist(false)}
            folders={snapshot?.folders || ['files', 'notebook', 'artifacts']}
            files={files}
            selectedPath={selectedPath}
            expandedFolders={expandedFolders}
            onToggleFolder={toggleFolder}
            onOpenFile={(path) => void openFile(path)}
            onCreateFile={(path) => createFile(path)}
            onCreateFolder={(path) => createFolder(path)}
            busy={createBusy}
          />
        ) : null}

        <div className="jarvis-notebook-main">
          <header className="jarvis-notebook-main-header">
            <div className="min-w-0">
              <span className="jarvis-notebook-eyebrow">PROJECT WORKSPACE</span>
              <h1 className="truncate">{project.name}</h1>
            </div>
          </header>

          <main className="jarvis-notebook-editor">
            <div className="jarvis-pane-toolbar">
              <div className="jarvis-editor-path-row">
                <button
                  type="button"
                  className={filesOpen ? 'jarvis-icon-tool active' : 'jarvis-icon-tool'}
                  onClick={() => setFilesOpenPersist(!filesOpen)}
                  title={filesOpen ? 'Hide files' : 'Show files'}
                  aria-label={filesOpen ? 'Hide files' : 'Show files'}
                  aria-pressed={filesOpen}
                >
                  <FileStack className="h-4 w-4" />
                </button>
                <strong className="truncate">{selectedPath}</strong>
                {loading ? <span className="jarvis-muted text-xs">Loading?</span> : null}
              </div>
              <div className="jarvis-editor-toolbar-right">
                {isMarkdownFile ? (
                  <button
                    type="button"
                    className={previewMarkdown ? 'jarvis-icon-tool active' : 'jarvis-icon-tool'}
                    onClick={() => setPreviewMarkdown((v) => !v)}
                    title={previewMarkdown ? 'Edit markdown' : 'Preview markdown'}
                    aria-label={previewMarkdown ? 'Edit markdown' : 'Preview markdown'}
                    aria-pressed={previewMarkdown}
                  >
                    {previewMarkdown ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                ) : null}
                <div
                  className={
                    saveState === 'error'
                      ? 'jarvis-save-status error'
                      : saveState === 'saving' || dirty
                        ? 'jarvis-save-status saving'
                        : 'jarvis-save-status saved'
                  }
                  title={saveState === 'saving' || dirty ? 'Saving?' : saveState === 'error' ? 'Save failed' : 'Saved'}
                  aria-live="polite"
                >
                  <img
                    src={saveState === 'saving' || dirty ? ICON_SAVING : ICON_SAVED}
                    alt={saveState === 'saving' || dirty ? 'Saving' : 'Saved'}
                    width={18}
                    height={18}
                    className={saveState === 'saving' || dirty ? 'jarvis-save-icon spin-soft' : 'jarvis-save-icon'}
                  />
                </div>
              </div>
            </div>
            {previewMarkdown && isMarkdownFile ? (
              <div className="jarvis-notebook-preview jarvis-prose" aria-label="Markdown preview">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{content || '_Empty document_'}</ReactMarkdown>
              </div>
            ) : (
              <textarea
                value={content}
                onChange={(event) => setContent(event.target.value)}
                className="jarvis-notebook-textarea"
                aria-label="Project text editor"
                spellCheck
              />
            )}
          </main>
        </div>

        {/* Same copilot as materials mode ? surface follows notebook rail. */}
        <aside className="jarvis-notebook-agent">
          <AgentChatBody />
        </aside>
      </div>
      {error ? (
        <div className="jarvis-notebook-error" role="alert">
          {error}
        </div>
      ) : null}
    </section>
  );
}
