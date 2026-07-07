import { useRef, useState } from "react";
import { api } from "../api";
import { useLocale } from "../i18n";

type Props = {
  manifest: Record<string, unknown>;
  onChange: (manifest: Record<string, unknown>) => void;
};

export default function AvatarUpload({ manifest, onChange }: Props) {
  const { t } = useLocale();
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  const imageUrl = typeof manifest.image_url === "string" ? manifest.image_url : "";
  const modelUrl = typeof manifest.model_url === "string" ? manifest.model_url : "";

  const upload = async (file: File) => {
    setUploading(true);
    setError("");
    try {
      const result = await api.uploadAvatar(file);
      const ext = file.name.toLowerCase();
      const patch =
        ext.endsWith(".glb") || ext.endsWith(".gltf")
          ? { model_url: result.url, image_url: undefined }
          : { image_url: result.url, model_url: undefined };
      onChange({ ...manifest, ...patch });
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
          {uploading ? t.scenarioEditor.avatarUploading : t.scenarioEditor.avatarUpload}
        </button>
        {(imageUrl || modelUrl) && (
          <button
            type="button"
            className="btn small"
            onClick={() => onChange({ ...manifest, image_url: undefined, model_url: undefined })}
          >
            {t.scenarioEditor.avatarClearImport}
          </button>
        )}
      </div>
      <input
        ref={inputRef}
        type="file"
        accept=".png,.jpg,.jpeg,.webp,.gif,.glb,.gltf"
        hidden
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) upload(file);
          e.target.value = "";
        }}
      />
      <p className="muted">{t.scenarioEditor.avatarUploadHint}</p>
      {imageUrl && (
        <div className="avatar-preview">
          <img src={imageUrl} alt="" />
          <code>{imageUrl}</code>
        </div>
      )}
      {modelUrl && (
        <p className="muted">
          {t.scenarioEditor.avatarModelReady}: <code>{modelUrl}</code>
        </p>
      )}
      {error && <p className="error">{error}</p>}
    </div>
  );
}
