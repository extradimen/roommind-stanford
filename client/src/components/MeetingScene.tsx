import { Canvas } from "@react-three/fiber";
import { useEffect, useMemo } from "react";
import * as THREE from "three";
import { Character, PlayerCharacter } from "../api";
import { buildCharacterSideMap, type CharacterSide } from "../characterSide";
import { usePersistedRatio } from "../hooks/usePersistedRatio";
import { preloadGltf } from "../hooks/useLoadedGltf";
import { useLocale } from "../i18n";
import { DEFAULT_CAMERA } from "../sceneLayout";
import { collectBoundAvatarModelUrls, hasActiveSceneGraph, resolveSceneGraph } from "../sceneGraph";
import MeetingOrbitControls from "./MeetingOrbitControls";
import SceneGraphStage from "./SceneGraphStage";
import { ensureKtx2Loader } from "../hooks/gltfKtx2";

interface Props {
  characters: Character[];
  playerCharacter?: PlayerCharacter | null;
  activeSpeaker: string | null;
  compact?: boolean;
  sceneConfig?: Record<string, unknown>;
}

function AvatarPreloader({
  sceneConfig,
  characters,
  playerCharacter,
}: {
  sceneConfig?: Record<string, unknown>;
  characters: Character[];
  playerCharacter?: PlayerCharacter | null;
}) {
  useEffect(() => {
    const urls = collectBoundAvatarModelUrls(sceneConfig, characters, playerCharacter);
    for (const url of urls) void preloadGltf(url);
  }, [sceneConfig, characters, playerCharacter]);
  return null;
}

export default function MeetingScene({
  characters,
  playerCharacter,
  activeSpeaker,
  compact,
  sceneConfig,
}: Props) {
  const { t } = useLocale();
  const sideMap = buildCharacterSideMap(characters);
  const sideLabels: Record<CharacterSide, string> = {
    player_ally: t.game.sideAlly,
    opponent: t.game.sideOpponent,
  };
  const sceneGraph = useMemo(() => resolveSceneGraph(sceneConfig), [sceneConfig]);
  const useSceneGraph = hasActiveSceneGraph(sceneConfig);

  const cameraPreset = {
    ...(compact ? DEFAULT_CAMERA.compact : DEFAULT_CAMERA.full),
    ...(compact ? sceneGraph?.camera?.compact : sceneGraph?.camera?.full),
  };
  const limits = { default: cameraPreset.distance, min: cameraPreset.min, max: cameraPreset.max };
  const storageKey = compact
    ? "roommind-stanford:scene-distance:compact"
    : "roommind-stanford:scene-distance:full";
  const [distance, setDistance] = usePersistedRatio(
    storageKey,
    limits.default,
    limits.min,
    limits.max,
  );

  const patternLabels = {
    east: t.system.sections.culture.badges.east,
    west: t.system.sections.culture.badges.west,
    global: t.system.sections.culture.badges.global,
  };

  const camera = { position: cameraPreset.position, fov: cameraPreset.fov };
  const step = compact ? 0.45 : 0.55;

  return (
    <div className="meeting-scene-root">
      <Canvas
        shadows
        camera={camera}
        dpr={compact ? 1 : undefined}
        gl={{ antialias: true, alpha: false, powerPreference: "high-performance" }}
        onCreated={({ gl }) => {
          ensureKtx2Loader(gl);
          gl.outputColorSpace = THREE.SRGBColorSpace;
          gl.toneMapping = THREE.ACESFilmicToneMapping;
          gl.toneMappingExposure = 1.05;
        }}
      >
        <color attach="background" args={["#d8cfc4"]} />
        <fog attach="fog" args={["#d8cfc4", 8, 18]} />
        {useSceneGraph && (
          <>
            <AvatarPreloader
              sceneConfig={sceneConfig}
              characters={characters}
              playerCharacter={playerCharacter}
            />
            <SceneGraphStage
            sceneConfig={sceneConfig}
            characters={characters}
            playerCharacter={playerCharacter}
            activeSpeaker={activeSpeaker}
            patternLabels={patternLabels}
            sideMap={sideMap}
            sideLabels={{ ...sideLabels, user: t.game.sideYou }}
            />
          </>
        )}
        <MeetingOrbitControls
          compact={compact}
          distance={distance}
          minDistance={limits.min}
          maxDistance={limits.max}
          onDistanceChange={setDistance}
        />
      </Canvas>

      <div className="scene-zoom-controls" aria-label={t.game.zoomDistance}>
        <button
          type="button"
          className="scene-zoom-btn"
          title={t.game.zoomIn}
          aria-label={t.game.zoomIn}
          onClick={() => setDistance(distance - step)}
        >
          +
        </button>
        <input
          type="range"
          className="scene-zoom-slider"
          min={limits.min}
          max={limits.max}
          step={0.1}
          value={distance}
          aria-label={t.game.zoomDistance}
          onChange={(e) => setDistance(parseFloat(e.target.value))}
        />
        <button
          type="button"
          className="scene-zoom-btn"
          title={t.game.zoomOut}
          aria-label={t.game.zoomOut}
          onClick={() => setDistance(distance + step)}
        >
          −
        </button>
        <button
          type="button"
          className="scene-zoom-reset"
          title={t.game.resetView}
          aria-label={t.game.resetView}
          onClick={() => setDistance(limits.default)}
        >
          ⟲
        </button>
      </div>
    </div>
  );
}
