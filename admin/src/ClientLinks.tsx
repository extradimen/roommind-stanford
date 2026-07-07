import { useEffect, useState } from "react";
import { api } from "./api";
import { useLocale } from "./i18n";
import { pageHostname, serviceUrl } from "./serviceUrls";

export default function ClientLinks() {
  const { t } = useLocale();
  const [clientUrl, setClientUrl] = useState("");

  useEffect(() => {
    api.getPlatformConfig()
      .then((c) => {
        const host = pageHostname(c.hosts.public_host);
        setClientUrl(serviceUrl(c.ports.client, host));
      })
      .catch(() => {
        setClientUrl(serviceUrl(5183));
      });
  }, []);

  if (!clientUrl) {
    return <span className="muted">{t.clientLink.loading}</span>;
  }

  return (
    <div className="client-links">
      <a href={clientUrl} target="_blank" rel="noreferrer">
        {t.clientLink.open}
      </a>
      <a href={`${clientUrl.replace(/\/$/, "")}/system`} target="_blank" rel="noreferrer">
        {t.clientLink.systemArch}
      </a>
    </div>
  );
}
