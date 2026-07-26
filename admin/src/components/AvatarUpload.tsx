import { useRef, useState } from "react";
import { api } from "../api";
import { useLocale } from "../i18n";
import GlbInspectPanel from "./GlbInspectPanel";

type Props = {
  manifest: Record<string, unknown>;
  onChange: (manifest: Record<string, unknown>) => void;
  /** When true, show warning if model_url is missing */
  required?: boolean;
};

function gltfManifest(patch: Record<string, unknown>): Record<string, unknown> {
  return { avatar_style: "gltf", ...patch };
}

export default function AvatarUpload({ manifest, onChange, required }: Props) {
  const { t } = useLocale();
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const modelUrl = typeof manifest.model_url === "string" ? manifest.model_url : "";
  const missing = required && !modelUrl;

  const upload = async (file: File) => {
    const ext = file.name.toLowerCase();
    if (!ext.endsWith(".glb") && !ext.endsWith(".gltf")) {
      setError(t.scenarioEditor.avatarGlbOnly);
      return;
    }
    setUploading(true);
    setError("");
    setSuccess("");
    try {
      const result = await api.uploadAvatar(file);
      onChange(gltfManifest({ model_url: result.url }));
      setSuccess(
        result.warning
          ? `${t.scenarioEditor.avatarUploadSavedHint} ${result.warning}`
          : t.scenarioEditor.avatarUploadSavedHint,
      );
    } catch (e) {
      setError(String(e));
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="avatar-upload">
      <div className="row">
        <button type="button" className="btn" disabled={uploading} onClick={() => inputRef.current?.click()}>
          {uploading ? t.scenarioEditor.avatarUploading : t.scenarioEditor.avatarUploadGlb}
        </button>
        {modelUrl && (
          <button
            type="button"
            className="btn small"
            onClick={() => onChange(gltfManifest({}))}
          >
            {t.scenarioEditor.avatarClearImport}
          </button>
        )}
      </div>
      <input
        ref={inputRef}
        type="file"
        accept=".glb,.gltf"
        hidden
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) upload(file);
          e.target.value = "";
        }}
      />
      <p className="muted">{t.scenarioEditor.avatarUploadGlbHint}</p>
      {missing && <p className="error">{t.scenarioEditor.avatarGlbRequired}</p>}
      {modelUrl && (
        <>
          <p className="muted">
            {t.scenarioEditor.avatarModelReady}: <code>{modelUrl}</code>
          </p>
          <GlbInspectPanel modelUrl={modelUrl} />
        </>
      )}
      {success && <p className="success">{success}</p>}
      {error && <p className="error">{error}</p>}
    </div>
  );
}
