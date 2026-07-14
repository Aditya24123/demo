import { useEffect } from 'react';
import { useCatalystLayout } from '@/catalyst/bridge/hooks';
import { WorkspaceShell } from '@/components/workspace/WorkspaceShell';

function App() {
  const { theme, density } = useCatalystLayout();

  useEffect(() => {
    const root = window.document.documentElement;
    const isLight = theme === 'light';
    root.classList.toggle('light', isLight);
    root.classList.toggle('dark', !isLight);
    root.setAttribute('data-theme', theme);
  }, [theme]);

  useEffect(() => {
    const root = window.document.documentElement;
    root.setAttribute('data-density', density);
  }, [density]);

  return <WorkspaceShell />;
}

export default App;
