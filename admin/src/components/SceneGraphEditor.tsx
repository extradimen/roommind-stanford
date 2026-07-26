import { useCallback, useMemo, useRef, useState } from "react";
import { api, type Character } from "../api";
import { useLocale } from "../i18n";
import { DEFAULT_CAMERA, round3, type CameraPreset } from "../sceneLayout";
import NumericInput from "./NumericInput";
import {
  addAsset,
  addConstraint,
  createEmptySceneGraph,
  getConstraintForChild,
  getEditableTransform,
  instancesForAsset,
  prunePlotBindings,
  removeAsset,
  removeConstraint,
  removeInstance,
  setEditableTransform,
  spawnInstanceFromAsset,
  updateAsset,
  type AssetCategory,
  type ConstraintMode,
  type PlotCastBinding,
  type SceneGraph,
  type SceneTransform,
} from "../sceneGraph";
import SceneGraphPreview from "./SceneGraphPreview";

type Props = {
  graph: SceneGraph;
  onChange: (graph: SceneGraph) => void;
  plotBindings?: PlotCastBinding[];
  onPlotBindingsChange?: (bindings: PlotCastBinding[]) => void;
  characters?: Character[];
  playerCharacter?: Record<string, unknown> | null;
};

function radToDeg(r: number): number {
  return Math.round((r * 180) / Math.PI);
}

function degToRad(d: number): number {
  return (d * Math.PI) / 180;
}

const CATEGORY_OPTIONS: AssetCategory[] = ["environment", "furniture", "avatar_slot", "decor"];
const CONSTRAINT_MODES: ConstraintMode[] = ["attach", "position_only", "inherit_scale"];

function assetFileName(url: string): string {
  const trimmed = url.trim();
  if (!trimmed) return "—";
  return trimmed.split("/").pop() || trimmed;
}

export default function SceneGraphEditor({
  graph,
  onChange,
  plotBindings,
  onPlotBindingsChange,
  characters = [],
  playerCharacter,
}: Props) {
  const { t } = useLocale();
  const [selectedId, setSelectedId] = useState<string | null>(graph.instances[0]?.id ?? null);
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [assetCategory, setAssetCategory] = useState<AssetCategory>("furniture");
  const graphRef = useRef(graph);
  graphRef.current = graph;

  const selected = graph.instances.find((i) => i.id === selectedId);
  const selectedAsset = selectedAssetId ? graph.assets[selectedAssetId] : undefined;
  const assetInstances = selectedAssetId ? instancesForAsset(graph, selectedAssetId) : [];
  const editable = selected ? getEditableTransform(graph, selected.id) : null;
  const constraint = selected ? getConstraintForChild(graph, selected.id) : undefined;

  const updateGraph = useCallback(
    (next: SceneGraph) => {
      graphRef.current = next;
      onChange(next);
    },
    [onChange],
  );

  const handleUpload = async (file: File | null) => {
    if (!file) return;
    setUploading(true);
    setUploadError("");
    try {
      const res = await api.uploadProp(file);
      const assetId = `asset_${Math.random().toString(36).slice(2, 10)}`;
      const { graph: next } = addAsset(
        graphRef.current,
        {
          model_url: res.url,
          label: assetId,
          category: assetCategory,
          default_scale: 1,
        },
        assetId,
      );
      updateGraph(next);
    } catch (err) {
      setUploadError(String(err));
    } finally {
      setUploading(false);
    }
  };

  const spawnFromAsset = (assetId: string) => {
    updateGraph(spawnInstanceFromAsset(graphRef.current, assetId));
  };

  const deleteAsset = (assetId: string) => {
    const refs = instancesForAsset(graphRef.current, assetId);
    const msg =
      refs.length > 0
        ? t.sceneVisual.deleteAssetConfirmWithInstances.replace("{n}", String(refs.length))
        : t.sceneVisual.deleteAssetConfirm;
    if (!window.confirm(msg)) return;
    const next = removeAsset(graphRef.current, assetId);
    updateGraph(next);
    if (selectedAssetId === assetId) setSelectedAssetId(null);
    if (refs.some((i) => i.id === selectedId)) setSelectedId(null);
    if (plotBindings && onPlotBindingsChange) {
      onPlotBindingsChange(prunePlotBindings(plotBindings, next));
    }
  };

  const selectInstance = (instanceId: string) => {
    setSelectedId(instanceId);
    setSelectedAssetId(null);
  };

  const selectAsset = (assetId: string) => {
    setSelectedAssetId(assetId);
    setSelectedId(null);
  };

  const handleTransformChange = (instanceId: string, transform: SceneTransform) => {
    updateGraph(setEditableTransform(graphRef.current, instanceId, transform));
  };

  const updateEditable = (patch: Partial<SceneTransform>) => {
    if (!selected || !editable) return;
    handleTransformChange(selected.id, { ...editable, ...patch });
  };

  const updatePosition = (axis: 0 | 1 | 2, value: number) => {
    if (!editable) return;
    const pos: [number, number, number] = [...editable.position];
    pos[axis] = value;
    updateEditable({ position: pos });
  };

  const captureCamera = (position: [number, number, number], distance: number) => {
    const full = { ...DEFAULT_CAMERA.full, ...graphRef.current.camera?.full };
    updateGraph({
      ...graphRef.current,
      camera: {
        ...graphRef.current.camera,
        full: { ...full, position, distance },
      },
    });
  };

  const updateCamera = (mode: "compact" | "full", patch: Partial<CameraPreset>) => {
    const fallback = DEFAULT_CAMERA[mode];
    const cam = { ...fallback, ...graphRef.current.camera?.[mode] };
    updateGraph({
      ...graphRef.current,
      camera: {
        ...graphRef.current.camera,
        [mode]: { ...cam, ...patch },
      },
    });
  };

  const updateCameraPosition = (mode: "compact" | "full", axis: 0 | 1 | 2, value: number) => {
    const fallback = DEFAULT_CAMERA[mode];
    const cam = { ...fallback, ...graphRef.current.camera?.[mode] };
    const pos: [number, number, number] = [...cam.position];
    pos[axis] = value;
    updateCamera(mode, { position: pos });
  };

  const resetGraph = () => {
    if (!window.confirm(t.sceneVisual.resetStageConfirm)) return;
    updateGraph(createEmptySceneGraph());
    setSelectedId(null);
  };

  const migrateNote = useMemo(() => {
    if (graph.instances.length) return null;
    return t.sceneVisual.stageEmptyHint;
  }, [graph.instances.length, t.sceneVisual.stageEmptyHint]);

  return (
    <section className="scene-graph-editor">
      <div className="section-header">
        <div>
          <h2>{t.sceneVisual.stageSection}</h2>
          <p className="muted">{t.sceneVisual.stageHint}</p>
        </div>
        <button type="button" className="btn" onClick={resetGraph}>
          {t.sceneVisual.resetStage}
        </button>
      </div>

      {migrateNote && <p className="muted">{migrateNote}</p>}

      <div className="scene-graph-layout">
        <aside className="scene-graph-sidebar">
          <h3>{t.sceneVisual.assetLibrary}</h3>
          <p className="muted">{t.sceneVisual.assetLibraryHint}</p>
          <div className="scene-graph-upload">
            <label>
              {t.sceneVisual.assetCategory}
              <select value={assetCategory} onChange={(e) => setAssetCategory(e.target.value as AssetCategory)}>
                {CATEGORY_OPTIONS.map((c) => (
                  <option key={c} value={c}>
                    {t.sceneVisual.assetCategories[c]}
                  </option>
                ))}
              </select>
            </label>
            <p className="muted" style={{ fontSize: "0.85rem", margin: 0 }}>
              {t.sceneVisual.assetCategoryHint}
            </p>
            <label className="btn">
              {uploading ? t.common.saving : t.sceneVisual.uploadGlb}
              <input
                type="file"
                accept=".glb,.gltf"
                hidden
                disabled={uploading}
                onChange={(e) => {
                  void handleUpload(e.target.files?.[0] ?? null);
                  e.target.value = "";
                }}
              />
            </label>
            {uploadError && <p className="error">{uploadError}</p>}
          </div>

          <ul className="scene-graph-asset-list">
            {Object.entries(graph.assets).map(([id, asset]) => {
              const refCount = instancesForAsset(graph, id).length;
              return (
                <li key={id} className={selectedAssetId === id ? "active" : ""}>
                  <button type="button" className="scene-graph-asset-btn" onClick={() => selectAsset(id)}>
                    <code>{id}</code>
                    <span className="asset-meta-filename">{assetFileName(asset.model_url)}</span>
                    <span className="asset-meta-badge">{t.sceneVisual.assetCategories[asset.category]}</span>
                    {refCount > 0 && (
                      <span className="muted asset-meta-refs">
                        {t.sceneVisual.assetInstanceCount.replace("{n}", String(refCount))}
                      </span>
                    )}
                  </button>
                  <div className="scene-graph-asset-actions">
                    <button type="button" className="btn" onClick={() => spawnFromAsset(id)}>
                      {t.sceneVisual.spawnInstance}
                    </button>
                    <button type="button" className="btn danger" onClick={() => deleteAsset(id)}>
                      {t.common.delete}
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>

          {selectedAsset && selectedAssetId && (
            <div className="scene-graph-asset-detail">
              <h4>{t.sceneVisual.assetDetail}</h4>
              <dl className="asset-detail-grid">
                <dt>{t.sceneVisual.assetId}</dt>
                <dd><code>{selectedAssetId}</code></dd>
                <dt>{t.sceneVisual.assetFile}</dt>
                <dd>
                  {selectedAsset.model_url ? (
                    <a href={selectedAsset.model_url} target="_blank" rel="noreferrer">
                      {assetFileName(selectedAsset.model_url)}
                    </a>
                  ) : (
                    <span className="muted">—</span>
                  )}
                </dd>
                <dt>{t.sceneVisual.assetCategory}</dt>
                <dd>
                  <select
                    value={selectedAsset.category}
                    onChange={(e) =>
                      updateGraph(updateAsset(graphRef.current, selectedAssetId, { category: e.target.value as AssetCategory }))
                    }
                  >
                    {CATEGORY_OPTIONS.map((c) => (
                      <option key={c} value={c}>
                        {t.sceneVisual.assetCategories[c]}
                      </option>
                    ))}
                  </select>
                </dd>
                <dt>{t.sceneVisual.assetDefaultScale}</dt>
                <dd>
                  <NumericInput
                    value={selectedAsset.default_scale ?? 1}
                    step={0.05}
                    min={0.1}
                    max={3}
                    onCommit={(v) =>
                      updateGraph(
                        updateAsset(graphRef.current, selectedAssetId, {
                          default_scale: v,
                        }),
                      )
                    }
                  />
                </dd>
              </dl>
              {assetInstances.length > 0 && (
                <div className="asset-detail-refs">
                  <strong>{t.sceneVisual.assetUsedBy}</strong>
                  <ul>
                    {assetInstances.map((inst) => (
                      <li key={inst.id}>
                        <button type="button" className="btn linkish" onClick={() => selectInstance(inst.id)}>
                          {inst.editor_label} <code>{inst.id}</code>
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          <h3>{t.sceneVisual.instanceList}</h3>
          <p className="muted">{t.sceneVisual.instanceListHint}</p>
          <ul className="scene-graph-instance-list">
            {graph.instances.map((inst) => (
              <li key={inst.id}>
                <button
                  type="button"
                  className={`seat-layout-char-btn${selectedId === inst.id ? " active" : ""}`}
                  onClick={() => selectInstance(inst.id)}
                >
                  <strong>{inst.editor_label}</strong>
                  <code>{inst.id}</code>
                </button>
                {!inst.locked && (
                  <button
                    type="button"
                    className="btn danger"
                    onClick={() => {
                      updateGraph(removeInstance(graphRef.current, inst.id));
                      if (selectedId === inst.id) setSelectedId(null);
                    }}
                  >
                    {t.common.delete}
                  </button>
                )}
              </li>
            ))}
          </ul>
        </aside>

        <div className="scene-graph-main">
          <SceneGraphPreview
            graph={graph}
            selectedId={selectedId}
            onSelect={setSelectedId}
            onTransformChange={handleTransformChange}
            onCaptureCamera={captureCamera}
            editableTransform={editable}
            onEditablePatch={updateEditable}
            plotBindings={plotBindings}
            characters={characters}
            playerCharacter={playerCharacter}
          />

          <p className="muted" style={{ margin: "0.5rem 0 0", fontSize: "0.85rem" }}>
            {t.sceneVisual.viewOrbitHint}
          </p>

          <details className="seat-layout-advanced" style={{ marginTop: "0.75rem" }}>
            <summary>{t.sceneVisual.cameraSection}</summary>
            <p className="muted">{t.sceneVisual.cameraHint}</p>
            {(["full", "compact"] as const).map((mode) => {
              const fallback = DEFAULT_CAMERA[mode];
              const cam: CameraPreset = { ...fallback, ...graph.camera?.[mode] };
              const title = mode === "compact" ? t.sceneVisual.cameraCompact : t.sceneVisual.cameraFull;
              return (
                <div key={mode} className="char-card">
                  <strong>{title}</strong>
                  <div className="row" style={{ gap: "0.75rem", flexWrap: "wrap", alignItems: "flex-end" }}>
                    <label>
                      {t.sceneVisual.cameraDistance}
                      <NumericInput
                        value={cam.distance}
                        step="any"
                        min={1}
                        max={15}
                        onCommit={(v) => updateCamera(mode, { distance: v })}
                      />
                    </label>
                    <label>
                      FOV
                      <NumericInput
                        value={cam.fov}
                        step={1}
                        min={20}
                        max={90}
                        onCommit={(v) => updateCamera(mode, { fov: v })}
                      />
                    </label>
                    <label>
                      {t.sceneVisual.cameraMin}
                      <NumericInput
                        value={cam.min}
                        step="any"
                        min={1}
                        max={15}
                        onCommit={(v) => updateCamera(mode, { min: v })}
                      />
                    </label>
                    <label>
                      {t.sceneVisual.cameraMax}
                      <NumericInput
                        value={cam.max}
                        step="any"
                        min={2}
                        max={20}
                        onCommit={(v) => updateCamera(mode, { max: v })}
                      />
                    </label>
                    {(["X", "Y", "Z"] as const).map((label, i) => (
                      <label key={`${mode}-${label}`}>
                        {t.sceneVisual.cameraPos} {label}
                        <NumericInput
                          value={cam.position[i as 0 | 1 | 2]}
                          step="any"
                          onCommit={(v) => updateCameraPosition(mode, i as 0 | 1 | 2, v)}
                        />
                      </label>
                    ))}
                  </div>
                </div>
              );
            })}
          </details>

          {selected && editable && (
            <div className="scene-graph-props">
              <h3>{t.sceneVisual.instanceProps}</h3>
              <label>
                {t.sceneVisual.instanceLabel}
                <input
                  value={selected.editor_label}
                  onChange={(e) =>
                    updateGraph({
                      ...graphRef.current,
                      instances: graphRef.current.instances.map((i) =>
                        i.id === selected.id ? { ...i, editor_label: e.target.value } : i,
                      ),
                    })
                  }
                />
              </label>

              <div className="seat-numeric-grid">
                <span>{t.sceneVisual.position} X</span>
                <NumericInput
                  value={editable.position[0]}
                  step="any"
                  onCommit={(v) => updatePosition(0, v)}
                />
                <span>Y</span>
                <NumericInput
                  value={editable.position[1]}
                  step="any"
                  onCommit={(v) => updatePosition(1, v)}
                />
                <span>Z</span>
                <NumericInput
                  value={editable.position[2]}
                  step="any"
                  onCommit={(v) => updatePosition(2, v)}
                />
                <span>{t.sceneVisual.rotationDeg}</span>
                <NumericInput
                  value={radToDeg(editable.rotationY)}
                  step="any"
                  onCommit={(v) => updateEditable({ rotationY: degToRad(v) })}
                />
                <span>{t.sceneVisual.scale}</span>
                <NumericInput
                  value={editable.scale}
                  step={0.05}
                  min={0.1}
                  max={3}
                  onCommit={(v) => updateEditable({ scale: v })}
                />
              </div>
              <label className="scene-scale-slider">
                <span>{t.sceneVisual.scaleSlider}</span>
                <input
                  type="range"
                  min={0.1}
                  max={3}
                  step={0.05}
                  value={editable.scale}
                  onChange={(e) => updateEditable({ scale: parseFloat(e.target.value) })}
                />
                <span className="muted">{round3(editable.scale)}</span>
              </label>

              <h4>{t.sceneVisual.constraintSection}</h4>
              <label>
                {t.sceneVisual.constraintParent}
                <select
                  value={constraint?.parent_id ?? ""}
                  onChange={(e) => {
                    const parentId = e.target.value;
                    if (!parentId) {
                      updateGraph(removeConstraint(graphRef.current, selected.id));
                      return;
                    }
                    updateGraph(addConstraint(graphRef.current, selected.id, parentId, constraint?.mode ?? "attach"));
                  }}
                >
                  <option value="">{t.sceneVisual.noConstraint}</option>
                  {graph.instances
                    .filter((i) => i.id !== selected.id)
                    .map((i) => (
                      <option key={i.id} value={i.id}>
                        {i.editor_label}
                      </option>
                    ))}
                </select>
              </label>
              {constraint && (
                <label>
                  {t.sceneVisual.constraintMode}
                  <select
                    value={constraint.mode}
                    onChange={(e) =>
                      updateGraph(
                        addConstraint(graphRef.current, selected.id, constraint.parent_id, e.target.value as ConstraintMode),
                      )
                    }
                  >
                    {CONSTRAINT_MODES.map((m) => (
                      <option key={m} value={m}>
                        {t.sceneVisual.constraintModes[m]}
                      </option>
                    ))}
                  </select>
                </label>
              )}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
