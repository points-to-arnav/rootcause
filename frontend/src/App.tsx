import React, { useEffect } from 'react';
import { useAppStore } from './store/useAppStore';
import { Navbar } from './components/Navbar';
import { SettingsModal } from './components/SettingsModal';
import { UploadPage } from './pages/UploadPage';
import { AnalystPage } from './pages/AnalystPage';
import { DashboardPage } from './pages/DashboardPage';

export function App() {
  const { currentTab, loadInitialSettings } = useAppStore();

  useEffect(() => {
    loadInitialSettings();
  }, [loadInitialSettings]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-indigo-500/30 selection:text-indigo-200">
      <Navbar />

      <main className="flex-1">
        {currentTab === 'upload' && <UploadPage />}
        {currentTab === 'analyst' && <AnalystPage />}
        {currentTab === 'dashboard' && <DashboardPage />}
      </main>

      <SettingsModal />
    </div>
  );
}

export default App;
