import { useEffect, useState } from "react";
import { api } from "./api";
import { useLocale } from "./i18n";
import { pageHostname, serviceUrl } from "./serviceUrls";

export default function ClientLink() {
  const { t } = useLocale();
  const [url, setUrl] = useState("");

  useEffect(() => {
    api.getPlatformConfig()
      .then((c) => {
        const host = pageHostname(c.hosts.public_host);
        setUrl(serviceUrl(c.ports.client, host));
      })
      .catch(() => {
        setUrl(serviceUrl(5183));
      });
  }, []);

  if (!url) return <span className="muted">{t.clientLink.loading}</span>;

  return (
    <a href={url} target="_blank" rel="noreferrer">
      {t.clientLink.open}
    </a>
  );
}
