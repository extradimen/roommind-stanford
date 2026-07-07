import { Link, Navigate, Route, Routes } from "react-router-dom";
import ClientLinks from "./ClientLinks";
import LanguageSwitcher from "./components/LanguageSwitcher";
import { useLocale } from "./i18n";
import Dashboard from "./pages/Dashboard";
import LLMSettings from "./pages/LLMSettings";
import OrchestrationSettings from "./pages/OrchestrationSettings";
import PlatformSettings from "./pages/PlatformSettings";
import ScenarioEditor from "./pages/ScenarioEditor";
import ScenarioList from "./pages/ScenarioList";
import SessionDebug from "./pages/SessionDebug";

export default function App() {
  const { t } = useLocale();

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-head">
          <div className="brand">{t.brand}</div>
          <LanguageSwitcher className="sidebar-lang" />
        </div>
        <nav>
          <Link to="/">{t.nav.dashboard}</Link>
          <Link to="/platform">{t.nav.platform}</Link>
          <Link to="/llm">{t.nav.llm}</Link>
          <Link to="/scenarios">{t.nav.scenarios}</Link>
          <Link to="/sessions/debug">{t.nav.sessionDebug}</Link>
        </nav>
        <div className="sidebar-footer">
          <ClientLinks />
        </div>
      </aside>
      <main className="content">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/platform" element={<PlatformSettings />} />
          <Route path="/llm" element={<LLMSettings />} />
          <Route path="/scenarios" element={<ScenarioList />} />
          <Route path="/scenarios/new" element={<ScenarioEditor />} />
          <Route path="/scenarios/:id/orchestration" element={<OrchestrationSettings />} />
          <Route path="/scenarios/:id" element={<ScenarioEditor />} />
          <Route path="/dispatch" element={<Navigate to="/scenarios" replace />} />
          <Route path="/sessions/debug" element={<SessionDebug />} />
        </Routes>
      </main>
    </div>
  );
}
