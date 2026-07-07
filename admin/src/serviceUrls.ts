/** Build service URLs using the browser's host (IP/domain), not localhost from config. */

export function pageHostname(configHost = "localhost"): string {
  if (typeof window !== "undefined") {
    const h = window.location.hostname;
    if (h && h !== "localhost" && h !== "127.0.0.1") return h;
  }
  if (configHost && configHost !== "auto" && configHost !== "localhost") return configHost;
  return "localhost";
}

export function serviceUrl(port: number, configHost?: string): string {
  const proto = typeof window !== "undefined" ? window.location.protocol : "http:";
  const host = pageHostname(configHost || "localhost");
  return `${proto}//${host}:${port}`;
}

export function rewriteServiceUrls(
  _urls: Record<string, string>,
  ports: { api: number; admin: number; client: number },
  configHost: string,
): Record<string, string> {
  return {
    api: serviceUrl(ports.api, configHost),
    admin: serviceUrl(ports.admin, configHost),
    client: serviceUrl(ports.client, configHost),
    health: `${serviceUrl(ports.api, configHost)}/health`,
  };
}
