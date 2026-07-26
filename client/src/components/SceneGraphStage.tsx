import { useMemo } from "react";
import type { Character, PlayerCharacter } from "../api";
import type { AvatarManifest } from "../avatarManifest";
import { resolveAssetUrl } from "../avatarManifest";
import { resolveNpcLabel, resolvePlayerLabel } from "../characterNames";
import { type CharacterSide } from "../characterSide";
import { useLocale } from "../i18n";
import {
  characterByInstance,
  computeWorldTransforms,
  resolveBindingModelUrl,
  resolveSceneGraph,
  sanitizePlotCastBinding,
} from "../sceneGraph";
import { CHAIR_FIT_HEIGHT, isChairAssetUrl } from "../sceneChairs";
import GltfPropModel from "./GltfPropModel";
import SceneAvatar, { buildSceneAvatarProfile } from "./SceneAvatar";

type SceneSide = CharacterSide | "user";

type Props = {
  sceneConfig: Record<string, unknown> | undefined;
  characters: Character[];
  playerCharacter?: PlayerCharacter | null;
  activeSpeaker?: string | null;
  patternLabels: { east: string; west: string; global: string };
  sideMap: Record<string, CharacterSide>;
  sideLabels: Record<CharacterSide, string> & { user: string };
};

function asManifest(raw: unknown): AvatarManifest | undefined {
  return raw as AvatarManifest | undefined;
}

export function SceneLighting() {
  return (
    <>
      <hemisphereLight args={["#fff8ef", "#8a7f72", 0.5]} />
      <ambientLight intensity={0.38} color="#fff5e8" />
      <directionalLight
        position={[1, 7, 4]}
        intensity={0.7}
        color="#fff2dc"
        castShadow
        shadow-mapSize={[1024, 1024]}
      />
      <directionalLight position={[0, 3, 7]} intensity={0.35} color="#c8e4ff" />
    </>
  );
}

export function useSceneGraphFromConfig(sceneConfig: Record<string, unknown> | undefined) {
  return useMemo(() => resolveSceneGraph(sceneConfig), [sceneConfig]);
}

export default function SceneGraphStage({
  sceneConfig,
  characters,
  playerCharacter,
  activeSpeaker,
  patternLabels,
  sideMap,
  sideLabels,
}: Props) {
  const { locale } = useLocale();
  const graph = useMemo(() => resolveSceneGraph(sceneConfig), [sceneConfig]);
  if (!graph) return null;

  const bindings = sanitizePlotCastBinding(sceneConfig?.plot_cast_binding);
  const instToChar = characterByInstance(bindings);
  const worlds = useMemo(() => computeWorldTransforms(graph), [graph]);

  const manifestByChar = useMemo(() => {
    const map = new Map<string, AvatarManifest | undefined>();
    for (const c of characters) {
      map.set(c.character_id, asManifest(c.avatar_manifest));
    }
    if (playerCharacter && typeof playerCharacter === "object") {
      map.set("user", asManifest(playerCharacter.avatar_manifest));
    }
    return map;
  }, [characters, playerCharacter]);

  const propsAndEnv = graph.instances.filter((i) => i.role !== "avatar_slot");

  const boundAvatars = graph.instances
    .filter((i) => i.role === "avatar_slot" && instToChar.has(i.id))
    .map((inst) => {
      const charId = instToChar.get(inst.id)!;
      const world = worlds.get(inst.id) || inst.transform;
      const manifest = manifestByChar.get(charId);
      const modelUrl = resolveBindingModelUrl(graph, inst.id, manifest);
      if (!modelUrl || !resolveAssetUrl(modelUrl)) return null;

      const isUser = charId === "user";
      const side: SceneSide = isUser ? "user" : sideMap[charId] || "opponent";

      return {
        charId,
        world,
        manifest: { ...manifest, model_url: modelUrl },
        name: isUser
          ? resolvePlayerLabel(playerCharacter || undefined) || playerCharacter?.character_name || "You"
          : resolveNpcLabel(
              charId,
              {},
              characters.find((c) => c.character_id === charId)?.display_name ||
                characters.find((c) => c.character_id === charId)?.character_name ||
                charId,
              locale,
            ),
        side,
        sideLabel: isUser ? sideLabels.user : sideLabels[side],
        profile: buildSceneAvatarProfile(charId, manifest, patternLabels),
      };
    })
    .filter((x): x is NonNullable<typeof x> => !!x);

  return (
    <>
      <SceneLighting />
      {propsAndEnv.map((inst) => {
        const asset = graph.assets[inst.asset_id];
        const url = resolveAssetUrl(asset?.model_url);
        if (!url) return null;
        const world = worlds.get(inst.id) || inst.transform;
        const isChair = isChairAssetUrl(url);
        const nativeScale = inst.role === "environment" || !isChair;
        return (
          <group
            key={inst.id}
            position={world.position}
            rotation={[0, world.rotationY, 0]}
            scale={world.scale}
          >
            <GltfPropModel
              url={url}
              instanceId={inst.id}
              seated={false}
              nativeScale={nativeScale}
              fitHeight={isChair ? CHAIR_FIT_HEIGHT : undefined}
            />
          </group>
        );
      })}
      {boundAvatars.map((a) => (
        <SceneAvatar
          key={a.charId}
          characterId={a.charId}
          position={a.world.position}
          rotationY={a.world.rotationY}
          seatScale={a.world.scale}
          profile={a.profile}
          manifest={a.manifest}
          name={a.name}
          sideLabel={a.sideLabel}
          side={a.side}
          active={activeSpeaker === a.charId}
          pose="sit"
        />
      ))}
    </>
  );
}
