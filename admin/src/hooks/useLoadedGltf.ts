import { useEffect, useState } from "react";
import type { Group } from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { MeshoptDecoder } from "three/examples/jsm/libs/meshopt_decoder.module.js";
import { enqueueGltfLoad } from "./gltfLoadQueue";
import { createParseKtx2Loader, waitForKtx2Renderer } from "./gltfKtx2";

export type GltfLoadState = "loading" | "ready" | "error";

const AVATAR_CACHE_VERSION = "20260709h";
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

export function useLoadedGltf(url: string, instanceId: string, timeoutMs = 120000) {
  const [state, setState] = useState<GltfLoadState>("loading");
  const [scene, setScene] = useState<Group | null>(null);

  useEffect(() => {
    let cancelled = false;
    setState("loading");
    setScene(null);

    const cached = templateByUrl.get(url);
    if (cached) {
      setScene(cached);
      setState("ready");
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
          const cachedAgain = templateByUrl.get(url);
          if (cachedAgain) {
            if (cancelled) return;
            setScene(cachedAgain);
            setState("ready");
            return;
          }

          const renderer = await waitForKtx2Renderer(30000);
          if (cancelled) return;
          if (!renderer) throw new Error("KTX2 renderer not ready");

          const res = await fetch(withCacheBust(url), { signal: abort.signal });
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          const buffer = await res.arrayBuffer();
          if (cancelled) return;

          const parsed = await parseGlbBuffer(buffer, url);
          if (cancelled) return;
          const template = resolveTemplate(url, parsed);
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

  return { state, scene };
}
