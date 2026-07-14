import { useEffect, useRef, useState } from 'react';
import { useCatalystLayout, useCatalystProjects, useCatalystSessions } from '@/catalyst/bridge/hooks';
import type { RailMode } from './types';
import { JarvisRawIcon } from './JarvisIcons';
import { ProfileMenu } from './ProfileMenu';
import { ProjectCreateDialog } from './ProjectCreateDialog';
import { SettingsDialog } from './SettingsDialog';
import { ChatsSection, CollapsedButton, ProjectsSection, SidebarRow, SidebarSection } from './workspaceRailParts';

type JarvisIconName = Parameters<typeof JarvisRawIcon>[0]['name'];

const PRIMARY_ITEMS: Array<{
  id: RailMode;
  label: string;
  iconSrc?: string;
  iconName?: JarvisIconName;
  iconClass?: string;
}> = [
  { id: 'home', label: 'Materials', iconSrc: '/icons/workspace-home.png', iconClass: 'rail-icon-workspace' },
  { id: 'genes', label: 'Genes', iconName: 'genes' },
  { id: 'notebook', label: 'Notebook', iconName: 'library' },
  { id: 'graph', label: 'Graph', iconSrc: '/icons/graph-merge.png', iconClass: 'rail-icon-graph' },
  { id: 'candidates', label: 'Candidates', iconSrc: '/icons/candidates.png' },
  { id: 'add_material', label: 'Research', iconSrc: '/icons/research.png', iconClass: 'rail-icon-research' },
];

function isMobileOverlayViewport() {
  return typeof window !== 'undefined' && window.matchMedia('(max-width: 900px)').matches;
}

export function WorkspaceRail({ mode, setMode }: { mode: RailMode; setMode: (mode: RailMode) => void }) {
  const { railExpanded: expanded, setRailExpanded } = useCatalystLayout();
  const {
    projects,
    activeProjectId,
    isLoading,
    error,
    loadProjects,
    selectProject,
    renameProject,
    deleteProject,
  } = useCatalystProjects();
  const {
    sessions,
    currentSessionId,
    isLoading: sessionsLoading,
    createSession,
    switchSession,
    renameSession,
    archiveSession,
    deleteSession,
    loadSessions,
  } = useCatalystSessions();
  const [profileOpen, setProfileOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [showArchivedChats, setShowArchivedChats] = useState(false);
  const profileRef = useRef<HTMLButtonElement | null>(null);

  // Sessions are loaded in app initialize ? only refresh if the list is empty.
  useEffect(() => {
    if (!sessions.length && !sessionsLoading) void loadSessions();
  }, [loadSessions, sessions.length, sessionsLoading]);

  useEffect(() => {
    if (!expanded) return undefined;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      if (profileOpen || createOpen || settingsOpen) return;
      if (!isMobileOverlayViewport()) return;
      setRailExpanded(false);
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [createOpen, expanded, profileOpen, setRailExpanded, settingsOpen]);

  const collapseIfOverlay = () => {
    if (isMobileOverlayViewport()) setRailExpanded(false);
  };

  const openAndSetMode = (nextMode: RailMode) => {
    setRailExpanded(true);
    setMode(nextMode);
  };

  const startNewSession = async () => {
    // Keep current mode (notebook/graph/etc.) ? only start a fresh agent transcript.
    await createSession();
    collapseIfOverlay();
  };

  return (
    <>
      {expanded ? (
        <button
          type="button"
          className="jarvis-sidebar-backdrop"
          aria-label="Collapse sidebar"
          onClick={() => setRailExpanded(false)}
        />
      ) : null}

      <aside
        id="catalyst-jarvis-sidebar"
        className={expanded ? 'jarvis-sidebar jarvis-sidebar-expanded' : 'jarvis-sidebar jarvis-sidebar-collapsed'}
        aria-label="Catalyst navigation"
      >
        <div className="jarvis-sidebar-header">
          {expanded ? (
            <button type="button" className="jarvis-brand" onClick={() => { setMode('home'); collapseIfOverlay(); }} title="Catalyst">
              <img src="/catalyst-logo.svg" alt="" className="jarvis-brand-logo" />
              <span>Catalyst</span>
            </button>
          ) : (
            <button type="button" className="jarvis-collapsed-brand" onClick={() => setRailExpanded(true)} title="Expand sidebar" aria-label="Expand sidebar">
              <img src="/catalyst-logo.svg" alt="" className="jarvis-brand-logo" />
            </button>
          )}

          {expanded ? (
            <button type="button" className="jarvis-icon-button" onClick={() => setRailExpanded(false)} title="Collapse sidebar" aria-label="Collapse sidebar">
              <JarvisRawIcon name="panel" className="h-5 w-5" />
            </button>
          ) : null}
        </div>

        <div className="jarvis-sidebar-scroll">
          {expanded ? (
            <>
              <div className="jarvis-pinned-actions">
                <SidebarRow iconName="newChat" label="New session" onClick={() => void startNewSession()} />
              </div>

              <SidebarSection label="Explore">
                {PRIMARY_ITEMS.map((item) => (
                  <SidebarRow
                    key={item.id}
                    iconSrc={item.iconSrc}
                    iconName={item.iconName}
                    iconClass={item.iconClass}
                    label={item.label}
                    active={mode === item.id}
                    onClick={() => {
                      setMode(item.id);
                      collapseIfOverlay();
                    }}
                  />
                ))}
              </SidebarSection>

              <ProjectsSection
                projects={projects}
                activeProjectId={activeProjectId}
                loading={isLoading}
                error={error}
                onRetry={() => void loadProjects()}
                onAdd={() => setCreateOpen(true)}
                onSelect={(projectId) => {
                  selectProject(projectId);
                  setMode('notebook');
                  collapseIfOverlay();
                }}
                onRename={(projectId, name) => void renameProject(projectId, name)}
                onDelete={(projectId) => {
                  if (window.confirm('Delete this project permanently?')) void deleteProject(projectId);
                }}
              />

              <ChatsSection
                sessions={sessions}
                activeSessionId={currentSessionId}
                loading={sessionsLoading}
                showArchived={showArchivedChats}
                onToggleArchived={() => setShowArchivedChats((value) => !value)}
                onSelect={(sessionId) => {
                  void switchSession(sessionId);
                  collapseIfOverlay();
                }}
                onRename={(sessionId, title) => void renameSession(sessionId, title)}
                onArchive={(sessionId) => void archiveSession(sessionId, true)}
                onRestore={(sessionId) => void archiveSession(sessionId, false)}
                onDelete={(sessionId) => {
                  if (window.confirm('Delete this chat permanently?')) void deleteSession(sessionId);
                }}
              />
            </>
          ) : (
            <div className="jarvis-collapsed-stack">
              <CollapsedButton iconName="newChat" label="New session" onClick={() => void startNewSession()} />
              {PRIMARY_ITEMS.map((item) => (
                <CollapsedButton
                  key={item.id}
                  iconSrc={item.iconSrc}
                  iconName={item.iconName}
                  iconClass={item.iconClass}
                  label={item.label}
                  active={mode === item.id}
                  onClick={() => openAndSetMode(item.id)}
                />
              ))}
            </div>
          )}
        </div>

        <div className="jarvis-sidebar-footer">
          <button
            ref={profileRef}
            type="button"
            className={expanded ? 'jarvis-user-row' : 'jarvis-collapsed-profile'}
            title="Profile"
            aria-label="Profile"
            aria-haspopup="menu"
            aria-expanded={profileOpen}
            onClick={() => setProfileOpen((value) => !value)}
          >
            <span className="jarvis-avatar">R</span>
            {expanded ? (
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[14px] leading-5">Rudra</span>
                <span className="jarvis-muted block truncate text-[12px] leading-4">Catalyst workspace</span>
              </span>
            ) : null}
            {expanded ? <JarvisRawIcon name="chevronDown" className="h-4 w-4 text-[var(--color-text-secondary)]" /> : null}
          </button>
        </div>

        {profileOpen ? (
          <ProfileMenu
            open
            expanded={expanded}
            anchorRef={profileRef}
            onClose={() => setProfileOpen(false)}
            onOpenSettings={() => setSettingsOpen(true)}
          />
        ) : null}
        {createOpen ? (
          <ProjectCreateDialog
            open
            onClose={() => setCreateOpen(false)}
            onCreated={() => {
              setCreateOpen(false);
              setMode('notebook');
              collapseIfOverlay();
            }}
          />
        ) : null}
        {settingsOpen ? <SettingsDialog open onClose={() => setSettingsOpen(false)} /> : null}
      </aside>
    </>
  );
}
