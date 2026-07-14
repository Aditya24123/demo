import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type RefObject } from 'react';
import { createPortal } from 'react-dom';
import { SettingsIcon } from './JarvisIcons';

export function ProfileMenu({
  open,
  expanded,
  anchorRef,
  onClose,
  onOpenSettings,
}: {
  open: boolean;
  expanded: boolean;
  anchorRef: RefObject<HTMLButtonElement | null>;
  onClose: () => void;
  onOpenSettings: () => void;
}) {
  const menuRef = useRef<HTMLDivElement | null>(null);
  const settingsRef = useRef<HTMLButtonElement | null>(null);
  const [style, setStyle] = useState<CSSProperties | null>(null);

  useLayoutEffect(() => {
    if (!open) return undefined;

    const update = () => {
      const rect = anchorRef.current?.getBoundingClientRect();
      if (!rect) return;
      const height = menuRef.current?.offsetHeight || 112;
      const width = 248;
      const left = expanded
        ? Math.min(Math.max(8, rect.left), Math.max(8, window.innerWidth - width - 8))
        : 8;
      setStyle({
        position: 'fixed',
        left,
        top: Math.max(8, rect.top - height - 12),
        width,
        zIndex: 800,
      });
    };

    const frame = window.requestAnimationFrame(() => {
      update();
      window.requestAnimationFrame(update);
    });
    window.addEventListener('resize', update);
    window.addEventListener('scroll', update, true);
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener('resize', update);
      window.removeEventListener('scroll', update, true);
    };
  }, [anchorRef, expanded, open]);

  useEffect(() => {
    if (!open) return undefined;

    const previous = document.activeElement as HTMLElement | null;
    const anchor = anchorRef.current;
    const focusTimer = window.setTimeout(() => settingsRef.current?.focus(), 0);

    const onPointerDown = (event: PointerEvent) => {
      if (menuRef.current?.contains(event.target as Node) || anchor?.contains(event.target as Node)) return;
      onClose();
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== 'Tab' || !menuRef.current) return;
      const focusable = menuRef.current.querySelectorAll<HTMLElement>('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
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

    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      window.clearTimeout(focusTimer);
      document.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
      if (previous && typeof previous.focus === 'function') previous.focus();
      else anchor?.focus();
    };
  }, [anchorRef, onClose, open]);

  if (!open || !style) return null;

  return createPortal(
    <div
      ref={menuRef}
      className="jarvis-profile-menu"
      role="menu"
      aria-label="Profile menu"
      style={style}
      onMouseDown={(event) => event.stopPropagation()}
      onPointerDown={(event) => event.stopPropagation()}
    >
      <div className="jarvis-profile-menu-user">
        <span className="jarvis-avatar">R</span>
        <div className="min-w-0">
          <div className="truncate text-[14px] leading-5">Rudra</div>
          <div className="jarvis-muted truncate text-[12px] leading-4">Catalyst workspace</div>
        </div>
      </div>
      <div className="jarvis-menu-divider" role="separator" />
      <button
        ref={settingsRef}
        type="button"
        className="jarvis-profile-menu-item"
        role="menuitem"
        onClick={() => {
          onClose();
          onOpenSettings();
        }}
      >
        <SettingsIcon className="h-[18px] w-[18px]" strokeWidth={1.7} />
        <span>Settings</span>
      </button>
    </div>,
    document.body,
  );
}
