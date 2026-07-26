import { KTX2Loader } from "three/examples/jsm/loaders/KTX2Loader.js";
import type { WebGLRenderer } from "three";

let rendererRef: WebGLRenderer | null = null;
let parseKtx2Loader: KTX2Loader | null = null;
let ktx2ReadyResolve: (() => void) | null = null;
const ktx2Ready = new Promise<void>((resolve) => {
  ktx2ReadyResolve = resolve;
});

const TRANSCODER_PATH = "/basis/";

function resetParseLoader() {
  parseKtx2Loader?.dispose();
  parseKtx2Loader = null;
}

export function ensureKtx2Loader(gl: WebGLRenderer): KTX2Loader {
  if (rendererRef !== gl) {
    rendererRef = gl;
    resetParseLoader();
  }
  const loader = createParseKtx2Loader();
  ktx2ReadyResolve?.();
  ktx2ReadyResolve = null;
  return loader;
}

export function createParseKtx2Loader(): KTX2Loader {
  if (!rendererRef) {
    throw new Error("KTX2 renderer not ready");
  }
  if (!parseKtx2Loader) {
    parseKtx2Loader = new KTX2Loader();
    parseKtx2Loader.setTranscoderPath(TRANSCODER_PATH);
    parseKtx2Loader.detectSupport(rendererRef);
  }
  return parseKtx2Loader;
}

export async function waitForKtx2Renderer(timeoutMs = 15000): Promise<WebGLRenderer | null> {
  if (rendererRef) return rendererRef;
  return Promise.race([
    ktx2Ready.then(() => rendererRef),
    new Promise<null>((resolve) => window.setTimeout(() => resolve(null), timeoutMs)),
  ]);
}
