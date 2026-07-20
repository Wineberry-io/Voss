import { render } from 'solid-js/web';
import { invoke } from '@tauri-apps/api/core';
import { getCurrentWindow } from '@tauri-apps/api/window';
import App from './App';
import OrchestrationConsole from './orchestration/OrchestrationConsole';
import { applyThemeOverrides } from './theme/applyTheme';
import { getBundledTheme } from './themes/themeCatalog';
import { applyThemeToRuntime, getCommittedTheme } from './themes/themeRuntime';
import './index.css';

const root = document.getElementById('root');
if (!root) throw new Error('No #root element');

async function applySavedTheme(): Promise<void> {
  // Apply default theme (Voss Ignite) before first render.
  applyThemeToRuntime(getCommittedTheme());

  try {
    const activeThemeId = await invoke<string | null>('load_active_theme_id');
    const theme = activeThemeId ? getBundledTheme(activeThemeId) : undefined;
    if (theme) {
      applyThemeToRuntime(theme);
    }
  } catch (e) {
    console.error('[voss-app] active theme load error:', e);
  }

  try {
    const overrides = await invoke<Record<string, string>>('get_theme_overrides');
    if (Object.keys(overrides).length > 0) {
      applyThemeOverrides(overrides);
    }
  } catch (e) {
    console.error('[voss-app] theme override error:', e);
  }
}

void applySavedTheme()
  .finally(() => {
    render(
      () =>
        getCurrentWindow().label === 'orchestration' ? (
          <OrchestrationConsole />
        ) : (
          <App />
        ),
      root,
    );
  });
