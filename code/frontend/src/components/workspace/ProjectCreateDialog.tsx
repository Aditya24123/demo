import { useEffect, useId, useRef, useState, type FormEvent } from 'react';
import { createPortal } from 'react-dom';
import { useCatalystProjects } from '@/catalyst/bridge/hooks';
import type { ProjectVM } from '@/catalyst/bridge/viewModels';
import { XIcon } from './JarvisIcons';

export function ProjectCreateDialog({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (project: ProjectVM) => void;
}) {
  const { createProject } = useCatalystProjects();
  const titleId = useId();
  const nameRef = useRef<HTMLInputElement | null>(null);
  const dialogRef = useRef<HTMLFormElement | null>(null);
  const savingRef = useRef(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    savingRef.current = saving;
  }, [saving]);

  useEffect(() => {
    if (!open) return undefined;

    const previous = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const focusTimer = window.setTimeout(() => nameRef.current?.focus(), 0);

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !savingRef.current) {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== 'Tab' || !dialogRef.current) return;
      const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
        'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('keydown', onKeyDown);
    return () => {
      window.clearTimeout(focusTimer);
      document.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = previousOverflow;
      previous?.focus?.();
    };
  }, [onClose, open]);

  if (!open) return null;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!name.trim() || saving) return;
    setSaving(true);
    savingRef.current = true;
    setError(null);
    try {
      const project = await createProject({ name: name.trim(), description: description.trim() || undefined });
      onCreated(project);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not create project');
    } finally {
      setSaving(false);
      savingRef.current = false;
    }
  }

  return createPortal(
    <div
      className="jarvis-dialog-backdrop"
      role="presentation"
      onMouseDown={() => {
        if (!savingRef.current) onClose();
      }}
    >
      <form
        ref={dialogRef}
        className="jarvis-project-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onSubmit={submit}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="jarvis-dialog-header">
          <h2 id={titleId}>New project</h2>
          <button
            type="button"
            className="jarvis-icon-button"
            onClick={onClose}
            disabled={saving}
            title="Close"
            aria-label="Close"
          >
            <XIcon className="h-4 w-4" />
          </button>
        </div>
        <label className="jarvis-form-label" htmlFor="project-name">Name</label>
        <input
          ref={nameRef}
          id="project-name"
          className="jarvis-form-input"
          value={name}
          onChange={(event) => setName(event.target.value)}
          maxLength={120}
          required
          disabled={saving}
          autoComplete="off"
        />
        <label className="jarvis-form-label" htmlFor="project-description">
          Description <span className="jarvis-muted">(optional)</span>
        </label>
        <textarea
          id="project-description"
          className="jarvis-form-input jarvis-form-textarea"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          maxLength={500}
          rows={3}
          disabled={saving}
        />
        {error ? <div className="jarvis-form-error" role="alert">{error}</div> : null}
        <div className="jarvis-dialog-actions">
          <button type="button" className="jarvis-secondary-button" onClick={onClose} disabled={saving}>
            Cancel
          </button>
          <button type="submit" className="jarvis-primary-button" disabled={!name.trim() || saving}>
            {saving ? 'Creating...' : 'Create project'}
          </button>
        </div>
      </form>
    </div>,
    document.body,
  );
}
