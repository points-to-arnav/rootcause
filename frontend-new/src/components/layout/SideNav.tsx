import clsx from 'clsx';
import {
  Database,
  LayoutDashboard,
  MessageSquareText,
  Settings,
  Sparkles,
  Trash2,
} from 'lucide-react';
import { useAppStore } from '../../store/useAppStore';
import { formatNumber, pluralize } from '../../lib/format';
import type { TabId } from '../../types';
import { CacheBadge } from '../metrics/CacheBadge';

const items: { id: TabId; label: string; hint: string; icon: typeof Database }[] = [
  { id: 'overview', label: 'Overview', hint: 'What changed', icon: LayoutDashboard },
  { id: 'analyst', label: 'Ask', hint: 'Questions and answers', icon: MessageSquareText },
  { id: 'data', label: 'Data', hint: 'Tables, joins, quality', icon: Database },
];

export function SideNav() {
  const tab = useAppStore((state) => state.tab);
  const setTab = useAppStore((state) => state.setTab);
  const datasetId = useAppStore((state) => state.datasetId);
  const semantic = useAppStore((state) => state.semantic);
  const settings = useAppStore((state) => state.settings);
  const setSettingsOpen = useAppStore((state) => state.setSettingsOpen);
  const clearDataset = useAppStore((state) => state.clearDataset);

  const totalRows = semantic?.tables.reduce((sum, table) => sum + table.row_count, 0) ?? 0;

  const activeProvider = settings?.providers.find(
    (provider) => provider.id === settings.active_provider,
  );
  const modelName = activeProvider?.model.split('/').pop()?.replace(':free', '');

  return (
    <div className="flex h-full flex-col border-r border-line bg-surface">
      <div className="flex h-14 items-center gap-2.5 border-b border-line px-4">
        <span className="flex size-6 items-center justify-center rounded-md bg-accent/15 text-accent">
          <Sparkles className="size-3.5" aria-hidden="true" />
        </span>
        <span className="text-[15px] font-semibold tracking-tight text-ink">RootCause</span>
      </div>

      <nav className="p-2" aria-label="Sections">
        <ul className="space-y-0.5">
          {items.map((item) => {
            const active = tab === item.id;
            const Icon = item.icon;
            return (
              <li key={item.id}>
                <button
                  onClick={() => setTab(item.id)}
                  aria-current={active ? 'page' : undefined}
                  className={clsx(
                    'flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-left transition-colors',
                    active
                      ? 'bg-raised text-ink'
                      : 'text-ink-2 hover:bg-raised/60 hover:text-ink',
                  )}
                >
                  <Icon
                    className={clsx('size-4 shrink-0', active ? 'text-accent' : 'text-ink-3')}
                    aria-hidden="true"
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block text-[13px] font-medium leading-4">{item.label}</span>
                    <span className="block truncate text-[12px] leading-4 text-ink-3">
                      {item.hint}
                    </span>
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="mt-auto border-t border-line p-3">
        {datasetId && semantic ? (
          <div className="rounded-md border border-line bg-raised/50 p-2.5">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="truncate font-mono text-[12px] text-ink" title={datasetId}>
                  {datasetId}
                </p>
                <p className="mt-0.5 text-[12px] leading-4 text-ink-3">
                  {pluralize(semantic.tables.length, 'table')} · {formatNumber(totalRows, 0)} rows
                </p>
              </div>
              <button
                onClick={clearDataset}
                aria-label="Unload this dataset"
                title="Unload this dataset"
                className="-m-1 rounded-md p-1 text-ink-3 transition-colors hover:bg-overlay hover:text-down"
              >
                <Trash2 className="size-3.5" aria-hidden="true" />
              </button>
            </div>
          </div>
        ) : (
          <p className="px-0.5 text-[12px] leading-4 text-ink-3">
            No dataset loaded. Open Data to add one.
          </p>
        )}

        <CacheBadge className="mt-2 w-full" />

        <button
          onClick={() => setSettingsOpen(true)}
          className="mt-2 flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-ink-2 transition-colors hover:bg-raised hover:text-ink"
        >
          <Settings className="size-3.5 shrink-0 text-ink-3" aria-hidden="true" />
          <span className="min-w-0 flex-1">
            <span className="block text-[12px] leading-4">
              {activeProvider?.label ?? 'Model'}
            </span>
            <span className="block truncate font-mono text-[12px] leading-4 text-ink-3">
              {modelName ?? 'Not configured'}
            </span>
          </span>
          {activeProvider && !activeProvider.available ? (
            <span
              className="size-1.5 shrink-0 rounded-full bg-warn"
              title="This provider is not configured"
            />
          ) : null}
        </button>
      </div>
    </div>
  );
}
