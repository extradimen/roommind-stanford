export function resolveAssetUrl(url?: string): string | undefined {
  const trimmed = (url || "").trim();
  if (!trimmed) return undefined;
  if (/^https?:\/\//i.test(trimmed)) return trimmed;
  if (trimmed.startsWith("/")) return trimmed;
  return `/${trimmed.replace(/^\/+/, "")}`;
}

export function avatarScaleFromManifest(manifest?: Record<string, unknown>): number {
  const height = Number(manifest?.height);
  if (!Number.isFinite(height) || height <= 0) return 1;
  return Math.min(1.35, Math.max(0.75, height / 1.72));
}
