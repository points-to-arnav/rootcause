import { useEffect } from 'react';
import type { ReactNode } from 'react';
import { Menu, X } from 'lucide-react';
import { useAppStore } from '../../store/useAppStore';
import { SideNav } from './SideNav';

interface AppShellProps {
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
  /** Pages that own their own scrolling, such as the chat thread. */
  fillHeight?: boolean;
}

export function AppShell({
  title,
  description,
  actions,
  children,
  fillHeight = false,
}: AppShellProps) {
  const navOpen = useAppStore((state) => state.navOpen);
  const setNavOpen = useAppStore((state) => state.setNavOpen);

  useEffect(() => {
    if (!navOpen) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setNavOpen(false);
    }
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [navOpen, setNavOpen]);

  return (
    <div className="flex h-dvh overflow-hidden bg-ground">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-70 focus:rounded-md focus:bg-accent focus:px-3 focus:py-1.5 focus:text-white"
      >
        Skip to content
      </a>

      {/* Permanent rail from lg up; drawer below it. */}
      <aside className="hidden w-56 shrink-0 lg:block">
        <SideNav />
      </aside>

      {navOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="absolute inset-0 bg-black/60"
            onClick={() => setNavOpen(false)}
            aria-hidden="true"
          />
          <div className="absolute inset-y-0 left-0 w-60">
            <SideNav />
          </div>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-3 border-b border-line bg-surface px-4">
          <button
            onClick={() => setNavOpen(!navOpen)}
            aria-label={navOpen ? 'Close menu' : 'Open menu'}
            aria-expanded={navOpen}
            className="-ml-1 rounded-md p-1.5 text-ink-2 transition-colors hover:bg-raised hover:text-ink lg:hidden"
          >
            {navOpen ? (
              <X className="size-4" aria-hidden="true" />
            ) : (
              <Menu className="size-4" aria-hidden="true" />
            )}
          </button>

          <div className="min-w-0 flex-1">
            <h1 className="truncate text-[15px] font-semibold leading-5 text-ink">{title}</h1>
            {description ? (
              <p className="truncate text-[12px] leading-4 text-ink-3">{description}</p>
            ) : null}
          </div>

          {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
        </header>

        <main
          id="main"
          className={
            fillHeight
              ? 'flex min-h-0 flex-1 flex-col'
              : 'flex-1 overflow-y-auto'
          }
        >
          {children}
        </main>
      </div>
    </div>
  );
}
