import { HashRouter, NavLink, Route, Routes } from 'react-router-dom';
import { DataProvider, useAtlasState } from './data/DataContext';
import { ExploreProvider } from './data/explore';
import { useTheme, type ThemeChoice } from './lib/theme';
import type { Mode } from './lib/palette';
import ExplorePage from './pages/ExplorePage';
import LabPage from './pages/LabPage';
import AboutPage from './pages/AboutPage';

const THEME_NEXT: Record<ThemeChoice, ThemeChoice> = { system: 'light', light: 'dark', dark: 'system' };
const THEME_LABEL: Record<ThemeChoice, string> = { system: '시스템', light: '라이트', dark: '다크' };

function Header({ choice, onTheme }: { choice: ThemeChoice; onTheme: () => void }) {
  return (
    <header className="site-header">
      <NavLink to="/" className="brand" end>
        Lab Atlas <span className="brand-sub">연구실 지형도</span>
      </NavLink>
      <nav aria-label="주 메뉴">
        <NavLink to="/" end>탐색</NavLink>
        <NavLink to="/about">방법론</NavLink>
        <button className="theme-btn" onClick={onTheme} aria-label={`테마 전환 (현재 ${THEME_LABEL[choice]})`}>
          테마: {THEME_LABEL[choice]}
        </button>
      </nav>
    </header>
  );
}

function Routed({ mode }: { mode: Mode }) {
  const s = useAtlasState();
  if (s.status === 'loading') return <p className="state" role="status">데이터를 불러오는 중…</p>;
  if (s.status === 'error') return <p className="state" role="alert">데이터를 불러오지 못했습니다: {s.message}</p>;
  return (
    <Routes>
      <Route path="/" element={<ExplorePage mode={mode} />} />
      <Route path="/lab/:id" element={<LabPage mode={mode} />} />
      <Route path="/about" element={<AboutPage />} />
      <Route path="*" element={<ExplorePage mode={mode} />} />
    </Routes>
  );
}

export default function App() {
  const { choice, mode, setChoice } = useTheme();
  return (
    <HashRouter>
      <DataProvider>
        <ExploreProvider>
          <a href="#main" className="skip" onClick={(e) => { e.preventDefault(); document.getElementById('main')?.focus(); }}>
            본문으로 건너뛰기
          </a>
          <Header choice={choice} onTheme={() => setChoice(THEME_NEXT[choice])} />
          <div id="main" tabIndex={-1} className="main">
            <Routed mode={mode} />
          </div>
        </ExploreProvider>
      </DataProvider>
    </HashRouter>
  );
}
