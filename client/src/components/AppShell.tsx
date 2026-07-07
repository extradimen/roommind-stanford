import { Link } from "react-router-dom";
import { useLocale } from "../i18n";
import LanguageSwitcher from "./LanguageSwitcher";

type Props = {
  children: React.ReactNode;
  showNav?: boolean;
};

export default function AppShell({ children, showNav = true }: Props) {
  const { t } = useLocale();

  return (
    <div className="app-shell">
      {showNav && (
        <nav className="app-nav">
          <Link to="/" className="app-nav-brand">
            {t.home.title}
            <span className="stanford-edition-badge">Stanford</span>
          </Link>
          <div className="app-nav-links">
            <Link to="/">{t.nav.home}</Link>
            <Link to="/system" className="nav-system">{t.nav.system}</Link>
            <LanguageSwitcher />
          </div>
        </nav>
      )}
      {children}
    </div>
  );
}
