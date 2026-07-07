import { FormEvent, useEffect, useState } from "react";
import { api, PlatformConfig } from "../api";
import { useLocale } from "../i18n";
import { rewriteServiceUrls } from "../serviceUrls";

export default function PlatformSettings() {
  const { t } = useLocale();
  const [config, setConfig] = useState<PlatformConfig | null>(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    api.getPlatformConfig().then(setConfig).catch((e) => setMsg(String(e)));
  }, []);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    if (!config) return;
    setSaving(true);
    setMsg("");
    try {
      const updated = await api.updatePlatformConfig({
        ports: config.ports,
        hosts: config.hosts,
        database: config.database,
      });
      setConfig(updated);
      setMsg(updated.restart_note);
    } catch (err) {
      setMsg(String(err));
    } finally {
      setSaving(false);
    }
  };

  const displayUrls = config
    ? rewriteServiceUrls(config.urls, config.ports, config.detected_public_host || config.hosts.public_host)
    : { api: "", admin: "", client: "", health: "" };

  const applyAutoHost = () => {
    if (!config) return;
    setConfig({ ...config, hosts: { ...config.hosts, public_host: "auto" } });
    setMsg(t.platform.setAutoHint);
  };

  const applyCurrentBrowserHost = () => {
    if (!config) return;
    const h = window.location.hostname;
    if (!h) return;
    setConfig({ ...config, hosts: { ...config.hosts, public_host: h } });
    setMsg(t.platform.setHostHint.replace("{host}", h));
  };

  if (!config) return <div>{t.common.loading}</div>;

  return (
    <div>
      <h1>{t.platform.title}</h1>
      <p className="muted">
        {t.platform.subtitle} <code>config/platform.json</code> {t.platform.and} <code>.env</code>
      </p>

      <form onSubmit={save} className="form-panel wide">
        <section>
          <h2>{t.platform.servicePorts}</h2>
          <div className="row">
            <label>
              {t.platform.apiPort}
              <input
                type="number"
                value={config.ports.api}
                onChange={(e) =>
                  setConfig({ ...config, ports: { ...config.ports, api: parseInt(e.target.value) } })
                }
              />
            </label>
            <label>
              {t.platform.adminPort}
              <input
                type="number"
                value={config.ports.admin}
                onChange={(e) =>
                  setConfig({ ...config, ports: { ...config.ports, admin: parseInt(e.target.value) } })
                }
              />
            </label>
            <label>
              {t.platform.clientPort}
              <input
                type="number"
                value={config.ports.client}
                onChange={(e) =>
                  setConfig({ ...config, ports: { ...config.ports, client: parseInt(e.target.value) } })
                }
              />
            </label>
            <label>
              {t.platform.postgresPort}
              <input
                type="number"
                value={config.ports.postgres}
                onChange={(e) =>
                  setConfig({ ...config, ports: { ...config.ports, postgres: parseInt(e.target.value) } })
                }
              />
            </label>
            <label>
              {t.platform.redisPort}
              <input
                type="number"
                value={config.ports.redis}
                onChange={(e) =>
                  setConfig({ ...config, ports: { ...config.ports, redis: parseInt(e.target.value) } })
                }
              />
            </label>
          </div>
        </section>

        <section>
          <h2>{t.platform.hosts}</h2>
          <div className="row">
            <label>
              {t.platform.apiBind}
              <input
                value={config.hosts.api_bind}
                onChange={(e) =>
                  setConfig({ ...config, hosts: { ...config.hosts, api_bind: e.target.value } })
                }
                placeholder="0.0.0.0"
              />
            </label>
            <label>
              {t.platform.publicHost}
              <input
                value={config.hosts.public_host}
                onChange={(e) =>
                  setConfig({ ...config, hosts: { ...config.hosts, public_host: e.target.value } })
                }
                placeholder={t.platform.publicHostPlaceholder}
              />
            </label>
          </div>
          <p className="hint">
            {t.platform.hostHint} <code>auto</code> {t.platform.hostHintAuto}
            {config.detected_public_host ? (
              <>{t.platform.detected} <code>{config.detected_public_host}</code>）</>
            ) : null}
            {t.platform.hostHintDomain}
            <button type="button" className="btn small" onClick={applyAutoHost} style={{ marginLeft: "0.5rem" }}>
              {t.platform.autoDetect}
            </button>
            <button type="button" className="btn small" onClick={applyCurrentBrowserHost} style={{ marginLeft: "0.5rem" }}>
              {t.platform.useCurrentHost}
            </button>
          </p>
        </section>

        <section>
          <h2>{t.platform.database}</h2>
          <div className="row">
            <label>
              {t.platform.dbUser}
              <input
                value={config.database.user}
                onChange={(e) =>
                  setConfig({ ...config, database: { ...config.database, user: e.target.value } })
                }
              />
            </label>
            <label>
              {t.platform.dbPassword}
              <input
                value={config.database.password}
                onChange={(e) =>
                  setConfig({ ...config, database: { ...config.database, password: e.target.value } })
                }
              />
            </label>
            <label>
              {t.platform.dbName}
              <input
                value={config.database.name}
                onChange={(e) =>
                  setConfig({ ...config, database: { ...config.database, name: e.target.value } })
                }
              />
            </label>
          </div>
        </section>

        <section>
          <h2>{t.platform.currentUrls}</h2>
          <p className="hint">{t.platform.urlsHint}</p>
          <ul className="port-list">
            <li>{t.dashboard.api}: <a href={displayUrls.api} target="_blank" rel="noreferrer">{displayUrls.api}</a></li>
            <li>{t.dashboard.admin}: <a href={displayUrls.admin} target="_blank" rel="noreferrer">{displayUrls.admin}</a></li>
            <li>{t.dashboard.client}: <a href={displayUrls.client} target="_blank" rel="noreferrer">{displayUrls.client}</a></li>
          </ul>
        </section>

        <button type="submit" className="btn primary" disabled={saving}>
          {saving ? t.common.saving : t.platform.saveConfig}
        </button>
        {msg && <p className="hint">{msg}</p>}
      </form>
    </div>
  );
}
