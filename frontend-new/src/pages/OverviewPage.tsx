import { useEffect } from 'react';
import clsx from 'clsx';
import { LayoutDashboard, RefreshCw } from 'lucide-react';
import { useAppStore } from '../store/useAppStore';
import { AppShell } from '../components/layout/AppShell';
import { AlertList } from '../components/dashboard/AlertList';
import { KpiCard } from '../components/dashboard/KpiCard';
import { ChartView } from '../components/charts/ChartView';
import { Button } from '../components/ui/Button';
import { EmptyState } from '../components/ui/EmptyState';
import { Panel, PanelHeader } from '../components/ui/Panel';
import { Skeleton, SkeletonText } from '../components/ui/Skeleton';


export function OverviewPage() {
  const datasetId = useAppStore((state) => state.datasetId);
  const dashboard = useAppStore((state) => state.dashboard);
  const loading = useAppStore((state) => state.dashboardLoading);
  const loadDashboard = useAppStore((state) => state.loadDashboard);
  const setTab = useAppStore((state) => state.setTab);
  const ask = useAppStore((state) => state.ask);

  useEffect(() => {
    if (datasetId) void loadDashboard();
  }, [datasetId, loadDashboard]);

  function investigate(question: string) {
    setTab('analyst');
    void ask(question);
  }

  if (!datasetId) {
    return (
      <AppShell title="Overview">
        <EmptyState
          icon={LayoutDashboard}
          title="No dataset loaded"
          body="Load a spreadsheet or CSV and RootCause will profile it, then summarise what is happening in it."
          actions={
            <Button variant="primary" onClick={() => setTab('data')}>
              Go to Data
            </Button>
          }
        />
      </AppShell>
    );
  }

  // The server decides which panels a dataset supports, so they are rendered in
  // the order it sends rather than looked up by a fixed set of names.
  const presentCharts = (dashboard?.panels ?? []).filter((panel) => panel.chart && panel.result);

  return (
    <AppShell
      title="Overview"
      description={
        dashboard?.period?.label ? `Period: ${dashboard.period.label}` : undefined
      }
      actions={
        <Button
          size="sm"
          onClick={() => loadDashboard()}
          loading={loading}
          icon={<RefreshCw className="size-3.5" aria-hidden="true" />}
        >
          Refresh
        </Button>
      }
    >
      <div className="mx-auto w-full max-w-6xl space-y-4 px-4 py-5">
        {loading && !dashboard ? <OverviewSkeleton /> : null}

        {dashboard ? (
          <>
            {dashboard.summary ? (
              <Panel className="reveal">
                <p className="max-w-[72ch] text-[15px] leading-7 text-ink">{dashboard.summary}</p>
              </Panel>
            ) : null}

            {dashboard.kpis.length > 0 ? (
              <div
                className={clsx(
                  'grid gap-3 sm:grid-cols-2',
                  dashboard.kpis.length === 5 ? 'xl:grid-cols-5' : 'xl:grid-cols-4',
                )}
              >
                {dashboard.kpis.map((kpi) => (
                  <KpiCard key={kpi.metric} kpi={kpi} periodLabel={dashboard.period?.label} />
                ))}
              </div>
            ) : null}

            {presentCharts.length > 0 ? (
              <div className="grid gap-4 lg:grid-cols-2">
                {presentCharts.map((panel) => (
                  <Panel
                    key={panel.id}
                    flush
                    className={
                      /* A time series is the one chart that earns the full width. */
                      panel.id === 'panel_trend' && presentCharts.length > 1
                        ? 'lg:col-span-2'
                        : undefined
                    }
                  >
                    <PanelHeader title={panel.title} />
                    <div className="p-3">
                      <ChartView
                        spec={panel.chart}
                        result={panel.result}
                        height={panel.id === 'panel_trend' ? 240 : 280}
                      />
                    </div>
                  </Panel>
                ))}
              </div>
            ) : null}

            <Panel flush>
              <PanelHeader
                title="What to look at"
                description="Ranked by how much each one affects the numbers above."
              />
              <AlertList alerts={dashboard.alerts} onInvestigate={investigate} />
            </Panel>
          </>
        ) : null}

        {!loading && !dashboard ? (
          <Panel>
            <EmptyState
              icon={LayoutDashboard}
              title="No overview yet"
              body="RootCause could not build a summary for this dataset. Try again, or ask a question directly."
              actions={
                <>
                  <Button variant="primary" onClick={() => loadDashboard()}>
                    Try again
                  </Button>
                  <Button onClick={() => setTab('analyst')}>Ask a question</Button>
                </>
              }
            />
          </Panel>
        ) : null}
      </div>
    </AppShell>
  );
}

function OverviewSkeleton() {
  return (
    <div className="space-y-4">
      <Panel>
        <SkeletonText lines={3} />
      </Panel>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {Array.from({ length: 5 }, (_, index) => (
          <Panel key={index}>
            <Skeleton className="h-3 w-24" />
            <Skeleton className="mt-3 h-6 w-28" />
            <Skeleton className="mt-3 h-3 w-16" />
          </Panel>
        ))}
      </div>
      <Panel>
        <Skeleton className="h-[240px] w-full" />
      </Panel>
    </div>
  );
}
