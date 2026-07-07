import { Canvas } from "@react-three/fiber";
import { useMemo } from "react";
import { Character } from "../api";
import { resolveNpcLabel } from "../characterNames";
import { usePersistedRatio } from "../hooks/usePersistedRatio";
import { useLocale } from "../i18n";
import AnimatedAvatar, { CULTURAL_PROFILES, type CulturalProfile } from "./AnimatedAvatar";
import MeetingOrbitControls from "./MeetingOrbitControls";

const SPAWN_POSITIONS: Record<string, [number, number, number]> = {
  seat_opposite: [0, 0, -2.5],
  seat_side: [2.2, 0, -1.2],
  seat_adjacent: [-1.8, 0, -0.8],
  seat_user: [0, 0, 2],
};

const DEFAULT_PROFILE: CulturalProfile = {
  skin: "#e8b896",
  suit: "#444",
  accent: "#58a6ff",
  accessory: "none",
  pattern: "global",
  label: "Guest",
};

const CAMERA_LIMITS = {
  compact: { default: 5.5, min: 2.6, max: 9.5 },
  full: { default: 5.0, min: 2.2, max: 10 },
};

interface Props {
  characters: Character[];
  activeSpeaker: string | null;
  compact?: boolean;
}

function MeetingRoom() {
  return (
    <>
      <ambientLight intensity={0.5} />
      <directionalLight position={[5, 8, 5]} intensity={1.1} castShadow />
      <pointLight position={[-3, 4, 2]} intensity={0.45} color="#ffe4c4" />
      <pointLight position={[3, 3, -2]} intensity={0.3} color="#c4e4ff" />

      <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[14, 14]} />
        <meshStandardMaterial color="#2d333b" />
      </mesh>

      <mesh position={[0, 0.75, -0.5]} castShadow receiveShadow>
        <boxGeometry args={[3.5, 0.08, 1.8]} />
        <meshStandardMaterial color="#5c4033" />
      </mesh>

      <mesh position={[0, 2.2, -4.8]}>
        <planeGeometry args={[3, 1.2]} />
        <meshStandardMaterial color="#1f2937" emissive="#2563eb" emissiveIntensity={0.15} />
      </mesh>
      <mesh position={[-3.5, 0.4, -2]}>
        <coneGeometry args={[0.25, 0.5, 8]} />
        <meshStandardMaterial color="#2d6a4f" />
      </mesh>
      <mesh position={[3.5, 0.4, -2]}>
        <coneGeometry args={[0.25, 0.5, 8]} />
        <meshStandardMaterial color="#40916c" />
      </mesh>
    </>
  );
}

export default function MeetingScene({ characters, activeSpeaker, compact }: Props) {
  const { t, locale } = useLocale();
  const limits = compact ? CAMERA_LIMITS.compact : CAMERA_LIMITS.full;
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

  const avatars = useMemo(
    () =>
      characters.map((c) => {
        const base = CULTURAL_PROFILES[c.character_id] || DEFAULT_PROFILE;
        return {
          id: c.character_id,
          name: resolveNpcLabel(c.character_id, {}, c.display_name, locale),
          profile: {
            ...base,
            label: patternLabels[base.pattern],
          } as CulturalProfile,
          position: SPAWN_POSITIONS[c.spawn_point || "seat_opposite"] || [0, 0, -2],
        };
      }),
    [characters, patternLabels.east, patternLabels.west, patternLabels.global, locale],
  );

  const camera = compact
    ? { position: [0, 2.4, 5.2] as [number, number, number], fov: 48 }
    : { position: [0, 2.2, 4.5] as [number, number, number], fov: 55 };

  const step = compact ? 0.45 : 0.55;

  return (
    <div className="meeting-scene-root">
      <Canvas shadows camera={camera} dpr={compact ? 1 : undefined}>
        <color attach="background" args={["#1a1f2e"]} />
        <MeetingRoom />
        {avatars.map((a) => (
          <AnimatedAvatar
            key={a.id}
            position={a.position}
            profile={a.profile}
            name={a.name}
            active={activeSpeaker === a.id}
          />
        ))}
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
