import { useState } from 'react';
import { useAppStore } from '../store/useAppStore';
import { AppShell } from '../components/layout/AppShell';
import { Dropzone } from '../components/data/Dropzone';
import { JoinGraph } from '../components/data/JoinGraph';
import { QualityReport } from '../components/data/QualityReport';
import { SchemaExplorer } from '../components/data/SchemaExplorer';
import { Button } from '../components/ui/Button';
import { Panel, PanelHeader } from '../components/ui/Panel';
import { Skeleton } from '../components/ui/Skeleton';
import { formatDate, formatNumber, pluralize } from '../lib/format';

export function DataPage() {
  const semantic = useAppStore((state) => state.semantic);
  const qualityIssues = useAppStore((state) => state.qualityIssues);
  const ingesting = useAppStore((state) => state.ingesting);
  const restoring = useAppStore((state) => state.restoring);
  const uploadFiles = useAppStore((state) => state.uploadFiles);
  const loadSample = useAppStore((state) => state.loadSample);
  const setTab = useAppStore((state) => state.setTab);

  const [selectedTable, setSelectedTable] = useState('');
  const [replacing, setReplacing] = useState(false);

  if (restoring) {
    return (
      <AppShell title="Data">
        <div className="mx-auto w-full max-w-6xl space-y-4 px-4 py-5">
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      </AppShell>
    );
  }

  if (!semantic) {
    return (
      <AppShell title="Data" description="Load the data you want to ask questions about">
        <div className="mx-auto w-full max-w-2xl px-4 py-10">
          <h2 className="text-[22px] font-semibold tracking-tight text-ink">
            Start with your numbers
          </h2>
          <p className="mt-1.5 max-w-prose text-[15px] leading-7 text-ink-2">
            RootCause reads your spreadsheet, works out what each column means, finds the links
            between tables, and flags anything that would make an answer misleading. Nothing
            leaves your machine.
          </p>
          <div className="mt-6">
            <Dropzone onFiles={uploadFiles} onLoadSample={loadSample} busy={ingesting} />
          </div>
        </div>
      </AppShell>
    );
  }

  const totalRows = semantic.tables.reduce((sum, table) => sum + table.row_count, 0);
  // GET /semantic carries no quality_summary (only the upload response does), and
  // the store always holds the /semantic shape, so count from the issue list.
  const summary = {
    total: qualityIssues.length,
    high: qualityIssues.filter((issue) => issue.severity === 'high').length,
  };

  return (
    <AppShell
      title="Data"
      description={semantic.dataset_id}
      actions={
        <>
          <Button size="sm" onClick={() => setReplacing(!replacing)}>
            {replacing ? 'Cancel' : 'Replace data'}
          </Button>
          <Button size="sm" variant="primary" onClick={() => setTab('analyst')}>
            Ask a question
          </Button>
        </>
      }
    >
      <div className="mx-auto w-full max-w-6xl space-y-4 px-4 py-5">
        {replacing ? (
          <Dropzone
            compact
            onFiles={(files) => {
              setReplacing(false);
              void uploadFiles(files);
            }}
            onLoadSample={() => {
              setReplacing(false);
              void loadSample();
            }}
            busy={ingesting}
          />
        ) : null}

        <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-line bg-line sm:grid-cols-4">
          <Stat label="Tables" value={formatNumber(semantic.tables.length, 0)} />
          <Stat label="Rows" value={formatNumber(totalRows, 0)} />
          <Stat
            label="Links between tables"
            value={formatNumber(semantic.relationships.length, 0)}
          />
          <Stat
            label="Most recent date"
            value={formatDate(semantic.time.max ?? semantic.time.anchor_date)}
          />
        </dl>

        <SchemaExplorer
          semantic={semantic}
          selectedTable={selectedTable || semantic.tables[0]?.name || ''}
          onSelectTable={setSelectedTable}
        />

        <div className="grid gap-4 lg:grid-cols-2">
          <Panel flush>
            <PanelHeader
              title="Data quality"
              description={
                summary.total > 0
                  ? `${pluralize(summary.total, 'issue')} found · ${summary.high} serious`
                  : 'Nothing to flag'
              }
            />
            <div className="max-h-96 overflow-y-auto">
              <QualityReport issues={qualityIssues} />
            </div>
          </Panel>

          <Panel flush>
            <PanelHeader
              title="How the tables connect"
              description="Detected from matching values, not from declared keys."
            />
            <div className="max-h-96 overflow-y-auto">
              <JoinGraph relationships={semantic.relationships} />
            </div>
          </Panel>
        </div>
      </div>
    </AppShell>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-surface px-3.5 py-3">
      <dt className="text-[12px] text-ink-3">{label}</dt>
      <dd className="tnum mt-0.5 font-mono text-[18px] font-semibold text-ink">{value}</dd>
    </div>
  );
}
