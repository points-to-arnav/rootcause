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
    <div className="min-h-screen bg-[#050505] text-[#EDEDED] flex flex-col font-sans selection:bg-cyan-500/20 selection:text-cyan-200 relative z-10">
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
