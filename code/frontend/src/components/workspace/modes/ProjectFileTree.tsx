import { useEffect, useRef, useState } from 'react';
import { ChevronDown, ChevronRight, FilePlus2, FileText, Folder, FolderOpen, FolderPlus, X } from 'lucide-react';

export type WorkspaceFile = { path: string; size: number; kind: string };

type CreateMode = 'file' | 'folder' | null;

type ProjectFileTreeProps = {
  open: boolean;
  onClose: () => void;
  folders: string[];
  files: WorkspaceFile[];
  selectedPath: string;
  expandedFolders: Set<string>;
  onToggleFolder: (folder: string) => void;
  onOpenFile: (path: string) => void;
  onCreateFile: (path: string) => Promise<void> | void;
  onCreateFolder: (path: string) => Promise<void> | void;
  busy?: boolean;
};

const ROOTS = ['files', 'notebook', 'artifacts'] as const;

/** In-editor file tree (toggled from the path toolbar). */
export function ProjectFileTree({
  open,
  onClose,
  folders,
  files,
  selectedPath,
  expandedFolders,
  onToggleFolder,
  onOpenFile,
  onCreateFile,
  onCreateFolder,
  busy = false,
}: ProjectFileTreeProps) {
  const [createMode, setCreateMode] = useState<CreateMode>(null);
  const [draft, setDraft] = useState('');
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (createMode) inputRef.current?.focus();
  }, [createMode]);

  if (!open) return null;

  const topFolders = ROOTS.slice();
  const customFolders = folders.filter(
    (folder) => !ROOTS.includes(folder as (typeof ROOTS)[number]) && folder.includes('/'),
  );

  const startCreate = (mode: Exclude<CreateMode, null>) => {
    setCreateMode(mode);
    setDraft('');
  };

  const cancelCreate = () => {
    setCreateMode(null);
    setDraft('');
  };

  const submitCreate = async () => {
    const raw = draft.trim().replaceAll('\\', '/').replace(/^\/+/, '');
    if (!raw) return;
    const path = /^(files|notebook|artifacts)\//.test(raw) ? raw : `files/${raw}`;
    if (createMode === 'folder') await onCreateFolder(path);
    else await onCreateFile(path);
    cancelCreate();
  };

  return (
    <aside className="jarvis-file-tree" aria-label="Project files">
      <div className="jarvis-pane-heading jarvis-pane-heading-action">
        <span>Files</span>
        <div className="jarvis-file-tree-heading-actions">
          <button
            type="button"
            className={createMode === 'file' ? 'jarvis-icon-tool active' : 'jarvis-icon-tool'}
            onClick={() => startCreate('file')}
            title="New file"
            aria-label="New file"
          >
            <FilePlus2 className="h-4 w-4" />
          </button>
          <button
            type="button"
            className={createMode === 'folder' ? 'jarvis-icon-tool active' : 'jarvis-icon-tool'}
            onClick={() => startCreate('folder')}
            title="New folder"
            aria-label="New folder"
          >
            <FolderPlus className="h-4 w-4" />
          </button>
          <button type="button" className="jarvis-icon-tool" onClick={onClose} title="Hide files" aria-label="Hide files">
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      {createMode ? (
        <div className="jarvis-create-panel">
          <div className="jarvis-create-panel-label">
            {createMode === 'folder' ? 'New folder' : 'New file'}
            <span className="jarvis-muted"> in files/</span>
          </div>
          <div className="jarvis-new-file-row">
            <input
              ref={inputRef}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') void submitCreate();
                if (event.key === 'Escape') cancelCreate();
              }}
              placeholder={createMode === 'folder' ? 'experiments' : 'notes.md'}
              aria-label={createMode === 'folder' ? 'New folder name' : 'New file name'}
            />
            <button type="button" className="jarvis-create-add" onClick={() => void submitCreate()} disabled={!draft.trim() || busy}>
              Add
            </button>
            <button type="button" className="jarvis-create-cancel" onClick={cancelCreate} title="Cancel">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      ) : null}

      <div className="jarvis-file-tree-list">
        {topFolders.map((folder) => {
          const expanded = expandedFolders.has(folder);
          const children = files.filter((file) => file.path.startsWith(`${folder}/`));
          const nestedFolders = customFolders.filter((item) => item.startsWith(`${folder}/`));
          return (
            <div key={folder} className="jarvis-file-folder-group">
              <button
                type="button"
                className="jarvis-file-row folder"
                onClick={() => onToggleFolder(folder)}
                aria-expanded={expanded}
              >
                {expanded ? <ChevronDown className="h-3.5 w-3.5 shrink-0" /> : <ChevronRight className="h-3.5 w-3.5 shrink-0" />}
                {expanded ? <FolderOpen className="h-4 w-4 shrink-0" /> : <Folder className="h-4 w-4 shrink-0" />}
                <span className="truncate">{folder}</span>
                <em className="jarvis-file-count">{children.length}</em>
              </button>
              {expanded ? (
                <>
                  {nestedFolders.map((nested) => (
                    <div key={nested} className="jarvis-file-row nested folder-static" title={nested}>
                      <Folder className="h-4 w-4 shrink-0" />
                      <span className="truncate">{nested.slice(folder.length + 1)}</span>
                    </div>
                  ))}
                  {children.map((file) => (
                    <button
                      type="button"
                      key={file.path}
                      className={file.path === selectedPath ? 'jarvis-file-row nested active' : 'jarvis-file-row nested'}
                      title={file.path}
                      onClick={() => onOpenFile(file.path)}
                    >
                      <FileText className="h-4 w-4 shrink-0" />
                      <span className="truncate">{file.path.slice(folder.length + 1)}</span>
                    </button>
                  ))}
                </>
              ) : null}
            </div>
          );
        })}
      </div>
    </aside>
  );
}
