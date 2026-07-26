import { useEffect, useState } from "react";
import { inspectGlbUrl, type GlbInspectResult } from "../glbInspect";
import { useLocale } from "../i18n";

type Props = {
  modelUrl: string;
};

export default function GlbInspectPanel({ modelUrl }: Props) {
  const { t } = useLocale();
  const [info, setInfo] = useState<GlbInspectResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!modelUrl) {
      setInfo(null);
      setError("");
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError("");
    inspectGlbUrl(modelUrl)
      .then((result) => {
        if (!cancelled) setInfo(result);
      })
      .catch((e) => {
        if (!cancelled) {
          setInfo(null);
          setError(String(e));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [modelUrl]);

  if (!modelUrl) return null;

  const viewerUrl = `https://gltf-viewer.donmccurdy.com/#model=${encodeURIComponent(
    `${window.location.origin}${modelUrl.startsWith("/") ? modelUrl : `/${modelUrl}`}`,
  )}`;

  return (
    <div className="glb-inspect-panel">
      <strong>{t.scenarioEditor.avatarGlbInspect}</strong>
      {loading && <p className="muted">{t.scenarioEditor.avatarGlbInspecting}</p>}
      {error && <p className="error">{error}</p>}
      {info && (
        <>
          <ul className="glb-inspect-stats">
            <li>{t.scenarioEditor.avatarGlbMeshes}: {info.meshCount}</li>
            <li>{t.scenarioEditor.avatarGlbSkins}: {info.skinCount}</li>
            <li>{t.scenarioEditor.avatarGlbNodes}: {info.nodeCount}</li>
          </ul>
          <p className="glb-inspect-animations-title">{t.scenarioEditor.avatarGlbAnimations}</p>
          {info.animations.length > 0 ? (
            <ul className="glb-inspect-animations">
              {info.animations.map((name) => (
                <li key={name}>
                  <code>{name}</code>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">{t.scenarioEditor.avatarGlbNoAnimations}</p>
          )}
        </>
      )}
      <a className="glb-inspect-link" href={viewerUrl} target="_blank" rel="noreferrer">
        {t.scenarioEditor.avatarGlbOpenViewer}
      </a>
    </div>
  );
}
