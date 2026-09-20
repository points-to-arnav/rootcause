import { useEffect } from 'react';
import { useAppStore } from './store/useAppStore';
import { AnalystPage } from './pages/AnalystPage';
import { DataPage } from './pages/DataPage';
import { OverviewPage } from './pages/OverviewPage';
import { SettingsDialog } from './components/settings/SettingsDialog';
import { MetricsDialog } from './components/metrics/MetricsDialog';
import { Toaster } from './components/ui/Toaster';

export default function App() {
  const tab = useAppStore((state) => state.tab);
  const bootstrap = useAppStore((state) => state.bootstrap);

  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  return (
    <>
      {tab === 'overview' ? <OverviewPage /> : null}
      {tab === 'analyst' ? <AnalystPage /> : null}
      {tab === 'data' ? <DataPage /> : null}
      <SettingsDialog />
      <MetricsDialog />
      <Toaster />
    </>
  );
}
