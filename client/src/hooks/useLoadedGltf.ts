import { useEffect, useState } from "react";
import type { Group } from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { MeshoptDecoder } from "three/examples/jsm/libs/meshopt_decoder.module.js";
import { enqueueGltfLoad } from "./gltfLoadQueue";
import { createParseKtx2Loader, waitForKtx2Renderer } from "./gltfKtx2";

export type GltfLoadState = "loading" | "ready" | "error";

/** Bump when optimized avatar binaries change to avoid stale browser cache. */
const AVATAR_CACHE_VERSION = "20260709i";

const templateByUrl = new Map<string, Group>();

function withCacheBust(url: string): string {
  const sep = url.includes("?") ? "&" : "?";
  return `${url}${sep}v=${AVATAR_CACHE_VERSION}`;
}

function parseGlbBuffer(buffer: ArrayBuffer, url: string) {
  return MeshoptDecoder.ready.then(() => {
    const loader = new GLTFLoader();
    loader.setMeshoptDecoder(MeshoptDecoder);
    loader.setKTX2Loader(createParseKtx2Loader());
    return new Promise<Group>((resolve, reject) => {
      loader.parse(
        buffer,
        "",
        (gltf) => resolve(gltf.scene),
        (err) => reject(err ?? new Error(`parse failed: ${url}`)),
      );
    });
  });
}

function resolveTemplate(url: string, parsed: Group): Group {
  const existing = templateByUrl.get(url);
  if (existing) return existing;
  const template = parsed.clone(true);
  template.userData.sourceUrl = url;
  templateByUrl.set(url, template);
  return template;
}

async function loadGltfTemplate(url: string, abort?: AbortSignal): Promise<Group> {
  const cached = templateByUrl.get(url);
  if (cached) return cached;

  const renderer = await waitForKtx2Renderer();
  if (!renderer) throw new Error("KTX2 renderer not ready");

  const res = await fetch(withCacheBust(url), abort ? { signal: abort } : undefined);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const buffer = await res.arrayBuffer();
  const parsed = await parseGlbBuffer(buffer, url);
  return resolveTemplate(url, parsed);
}

/** Warm the GLB template cache before SceneGraph avatars mount. */
export function preloadGltf(url: string, instanceId = "preload"): Promise<void> {
  if (!url || templateByUrl.has(url)) return Promise.resolve();
  return enqueueGltfLoad(async () => {
    if (templateByUrl.has(url)) return;
    await loadGltfTemplate(url);
  }).then(
    () => undefined,
    (err) => {
      console.error("[GLB] preload failed:", instanceId, url, err);
    },
  );
}

export function useLoadedGltf(url: string, instanceId: string, timeoutMs = 120000) {
  const [state, setState] = useState<GltfLoadState>("loading");
  const [scene, setScene] = useState<Group | null>(null);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setState("loading");
    setScene(null);
    setProgress(0);

    const cached = templateByUrl.get(url);
    if (cached) {
      setScene(cached);
      setState("ready");
      setProgress(100);
      return () => {
        cancelled = true;
      };
    }

    enqueueGltfLoad(async () => {
      for (let attempt = 1; attempt <= 2; attempt++) {
        const abort = new AbortController();
        const timer = window.setTimeout(() => {
          if (!cancelled) {
            abort.abort();
            setState("error");
          }
        }, timeoutMs);

        try {
          const template = await loadGltfTemplate(url, abort.signal);
          if (cancelled) return;
          setScene(template);
          setState("ready");
          return;
        } catch (err) {
          if (cancelled || abort.signal.aborted) return;
          if (attempt < 2) {
            console.warn("[GLB] retry:", instanceId, url, err);
            await new Promise((resolve) => window.setTimeout(resolve, 1200));
            continue;
          }
          console.error("[GLB] load failed:", instanceId, url, err);
          setState("error");
        } finally {
          window.clearTimeout(timer);
        }
      }
    });

    return () => {
      cancelled = true;
    };
  }, [url, instanceId, timeoutMs]);

  return { state, scene, progress };
}
