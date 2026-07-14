import { useEffect, useState, type ComponentType, type ReactNode } from 'react';
import type { ProjectVM } from '@/catalyst/bridge/viewModels';
import { PlusIcon, JarvisRawIcon } from './JarvisIcons';

type RailIcon = ComponentType<{ className?: string; strokeWidth?: number }>;
type JarvisIconName = Parameters<typeof JarvisRawIcon>[0]['name'];

function readCollapsed(key: string, fallback = false): boolean {
  if (typeof window === 'undefined') return fallback;
  const raw = window.localStorage.getItem(key);
  if (raw === '1') return true;
  if (raw === '0') return false;
  return fallback;
}

function writeCollapsed(key: string, collapsed: boolean) {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(key, collapsed ? '1' : '0');
}

function SectionHeader({
  label,
  collapsed,
  onToggle,
  action,
}: {
  label: string;
  collapsed: boolean;
  onToggle: () => void;
  action?: ReactNode;
}) {
  return (
    <div className="jarvis-section-label-row">
      <button
        type="button"
        className="jarvis-section-label"
        onClick={onToggle}
        aria-expanded={!collapsed}
        title={collapsed ? `Expand ${label}` : `Collapse ${label}`}
      >
        <span className={collapsed ? 'jarvis-section-chevron collapsed' : 'jarvis-section-chevron'} aria-hidden="true">
          <JarvisRawIcon name="chevronDown" />
        </span>
        <span className="jarvis-section-label-text">{label}</span>
      </button>
      {action}
    </div>
  );
}

export function ProjectsSection({
  projects,
  activeProjectId,
  loading,
  error,
  onRetry,
  onAdd,
  onSelect,
  onRename,
  onDelete,
}: {
  projects: ProjectVM[];
  activeProjectId: string | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  onAdd: () => void;
  onSelect: (projectId: string) => void;
  onRename: (projectId: string, name: string) => void;
  onDelete: (projectId: string) => void;
}) {
  const [menuProjectId, setMenuProjectId] = useState<string | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameDraft, setRenameDraft] = useState('');
  const [collapsed, setCollapsed] = useState(() => readCollapsed('catalyst-rail-projects-collapsed', false));

  useEffect(() => {
    writeCollapsed('catalyst-rail-projects-collapsed', collapsed);
  }, [collapsed]);

  return (
    <section className="jarvis-sidebar-section">
      <SectionHeader
        label="Projects"
        collapsed={collapsed}
        onToggle={() => setCollapsed((v) => !v)}
        action={
          <button
            type="button"
            className="jarvis-section-action"
            onClick={(event) => {
              event.stopPropagation();
              onAdd();
            }}
            title="Create project"
            aria-label="Create project"
          >
            <PlusIcon className="h-4 w-4" />
          </button>
        }
      />
      <div className={collapsed ? 'jarvis-section-body collapsed' : 'jarvis-section-body'}>
        {loading ? <div className="jarvis-project-state">Loading projects...</div> : null}
        {!loading && error ? (
          <div className="jarvis-project-state jarvis-project-state-error">
            <span>{error}</span>
            <button type="button" onClick={onRetry}>
              Retry
            </button>
          </div>
        ) : null}
        {!loading && !error && projects.length === 0 ? <div className="jarvis-project-state">No projects yet.</div> : null}
        {!loading && !error
          ? projects.map((project) => (
              <div key={project.projectId} className="jarvis-chat-row-wrap">
                {renamingId === project.projectId ? (
                  <input
                    className="jarvis-chat-rename-input"
                    value={renameDraft}
                    autoFocus
                    onChange={(event) => setRenameDraft(event.target.value)}
                    onBlur={() => {
                      if (renameDraft.trim()) onRename(project.projectId, renameDraft);
                      setRenamingId(null);
                    }}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter') {
                        if (renameDraft.trim()) onRename(project.projectId, renameDraft);
                        setRenamingId(null);
                      }
                      if (event.key === 'Escape') setRenamingId(null);
                    }}
                    aria-label="Rename project"
                  />
                ) : (
                  <button
                    type="button"
                    className={project.projectId === activeProjectId ? 'jarvis-project-row active' : 'jarvis-project-row'}
                    onClick={() => onSelect(project.projectId)}
                    onContextMenu={(event) => {
                      event.preventDefault();
                      setMenuProjectId(project.projectId);
                    }}
                    title={`${project.name} ? right-click for more`}
                  >
                    <JarvisRawIcon name="projects" className="h-4 w-4 shrink-0 opacity-80" />
                    <span className="truncate">{project.name}</span>
                  </button>
                )}
                {menuProjectId === project.projectId ? (
                  <div className="jarvis-chat-menu" role="menu">
                    <button
                      type="button"
                      onClick={() => {
                        setRenameDraft(project.name);
                        setRenamingId(project.projectId);
                        setMenuProjectId(null);
                      }}
                    >
                      Rename
                    </button>
                    <button
                      type="button"
                      className="danger"
                      onClick={() => {
                        onDelete(project.projectId);
                        setMenuProjectId(null);
                      }}
                    >
                      Delete
                    </button>
                    <button type="button" onClick={() => setMenuProjectId(null)}>
                      Cancel
                    </button>
                  </div>
                ) : null}
              </div>
            ))
          : null}
      </div>
    </section>
  );
}

export function SidebarSection({ label, children }: { label: string; children: ReactNode }) {
  return (
    <section className="jarvis-sidebar-section">
      <div className="jarvis-section-label">
        <span className="jarvis-section-label-text">{label}</span>
      </div>
      <div className="jarvis-section-body">{children}</div>
    </section>
  );
}

export function ChatsSection({
  sessions,
  activeSessionId,
  loading,
  showArchived,
  onToggleArchived,
  onSelect,
  onRename,
  onArchive,
  onRestore,
  onDelete,
}: {
  sessions: Array<{ id: string; title: string; archived?: boolean }>;
  activeSessionId: string | null;
  loading: boolean;
  showArchived: boolean;
  onToggleArchived: () => void;
  onSelect: (sessionId: string) => void;
  onRename: (sessionId: string, title: string) => void;
  onArchive: (sessionId: string) => void;
  onRestore: (sessionId: string) => void;
  onDelete: (sessionId: string) => void;
}) {
  const [menuSessionId, setMenuSessionId] = useState<string | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameDraft, setRenameDraft] = useState('');
  const [collapsed, setCollapsed] = useState(() => readCollapsed('catalyst-rail-chats-collapsed', false));
  const visible = sessions
    .filter((session) => (showArchived ? Boolean(session.archived) : !session.archived))
    .slice(0, 24);

  useEffect(() => {
    writeCollapsed('catalyst-rail-chats-collapsed', collapsed);
  }, [collapsed]);

  return (
    <section className="jarvis-sidebar-section jarvis-chats-section">
      <SectionHeader
        label="Chats"
        collapsed={collapsed}
        onToggle={() => setCollapsed((v) => !v)}
        action={
          <button
            type="button"
            className="jarvis-section-action"
            onClick={(event) => {
              event.stopPropagation();
              onToggleArchived();
            }}
            title={showArchived ? 'Show active chats' : 'Show archived chats'}
            style={{ width: 'auto', minWidth: 28, padding: '0 8px', fontSize: 11 }}
          >
            {showArchived ? 'Active' : 'Archived'}
          </button>
        }
      />
      <div className={collapsed ? 'jarvis-section-body collapsed' : 'jarvis-section-body'}>
        {loading ? <div className="jarvis-project-state">Loading chats...</div> : null}
        {!loading && visible.length === 0 ? (
          <div className="jarvis-project-state">{showArchived ? 'No archived chats.' : 'No chats yet.'}</div>
        ) : null}
        {!loading
          ? visible.map((session) => (
              <div key={session.id} className="jarvis-chat-row-wrap">
                {renamingId === session.id ? (
                  <input
                    className="jarvis-chat-rename-input"
                    value={renameDraft}
                    autoFocus
                    onChange={(event) => setRenameDraft(event.target.value)}
                    onBlur={() => {
                      if (renameDraft.trim()) onRename(session.id, renameDraft);
                      setRenamingId(null);
                    }}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter') {
                        if (renameDraft.trim()) onRename(session.id, renameDraft);
                        setRenamingId(null);
                      }
                      if (event.key === 'Escape') setRenamingId(null);
                    }}
                    aria-label="Rename chat"
                  />
                ) : (
                  <button
                    type="button"
                    className={session.id === activeSessionId ? 'jarvis-recent-row active' : 'jarvis-recent-row'}
                    onClick={() => onSelect(session.id)}
                    onContextMenu={(event) => {
                      event.preventDefault();
                      setMenuSessionId(session.id);
                    }}
                    title={`${session.title} ? right-click for more`}
                  >
                    <span className="truncate">{session.title}</span>
                  </button>
                )}
                {menuSessionId === session.id ? (
                  <div className="jarvis-chat-menu" role="menu">
                    <button
                      type="button"
                      onClick={() => {
                        setRenameDraft(session.title);
                        setRenamingId(session.id);
                        setMenuSessionId(null);
                      }}
                    >
                      Rename
                    </button>
                    {session.archived ? (
                      <button
                        type="button"
                        onClick={() => {
                          onRestore(session.id);
                          setMenuSessionId(null);
                        }}
                      >
                        Restore
                      </button>
                    ) : (
                      <button
                        type="button"
                        onClick={() => {
                          onArchive(session.id);
                          setMenuSessionId(null);
                        }}
                      >
                        Archive
                      </button>
                    )}
                    <button
                      type="button"
                      className="danger"
                      onClick={() => {
                        onDelete(session.id);
                        setMenuSessionId(null);
                      }}
                    >
                      Delete
                    </button>
                    <button type="button" onClick={() => setMenuSessionId(null)}>
                      Cancel
                    </button>
                  </div>
                ) : null}
              </div>
            ))
          : null}
      </div>
    </section>
  );
}

export function SidebarRow({
  icon: Icon,
  iconName,
  iconSrc,
  iconClass,
  label,
  active = false,
  onClick,
}: {
  icon?: RailIcon;
  iconName?: JarvisIconName;
  iconSrc?: string;
  iconClass?: string;
  label: string;
  active?: boolean;
  onClick?: () => void;
}) {
  return (
    <button type="button" className={active ? 'jarvis-sidebar-row active' : 'jarvis-sidebar-row'} onClick={onClick}>
      {iconSrc ? (
        <img
          src={iconSrc}
          alt=""
          className={['jarvis-rail-icon-img', iconClass].filter(Boolean).join(' ')}
          draggable={false}
        />
      ) : iconName ? (
        <JarvisRawIcon name={iconName} className="h-5 w-5 shrink-0" />
      ) : Icon ? (
        <Icon className="h-5 w-5 shrink-0" strokeWidth={1.9} />
      ) : null}
      <span className="truncate">{label}</span>
    </button>
  );
}

export function CollapsedButton({
  icon: Icon,
  iconName,
  iconSrc,
  iconClass,
  label,
  active = false,
  onClick,
}: {
  icon?: RailIcon;
  iconName?: JarvisIconName;
  iconSrc?: string;
  iconClass?: string;
  label: string;
  active?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      className={active ? 'jarvis-collapsed-button active' : 'jarvis-collapsed-button'}
      onClick={onClick}
      title={label}
      aria-label={label}
    >
      {iconSrc ? (
        <img
          src={iconSrc}
          alt=""
          className={['jarvis-rail-icon-img', iconClass].filter(Boolean).join(' ')}
          draggable={false}
        />
      ) : iconName ? (
        <JarvisRawIcon name={iconName} className="h-5 w-5" />
      ) : Icon ? (
        <Icon className="h-5 w-5" strokeWidth={1.9} />
      ) : null}
    </button>
  );
}
