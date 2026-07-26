export type GlbInspectResult = {
  animations: string[];
  meshCount: number;
  skinCount: number;
  nodeCount: number;
  isStatic: boolean;
};

function parseGlbJson(buffer: ArrayBuffer): GlbInspectResult {
  const view = new DataView(buffer);
  const magic = new TextDecoder().decode(new Uint8Array(buffer, 0, 4));
  if (magic !== "glTF") {
    throw new Error("Not a valid GLB file");
  }

  let offset = 12;
  const chunkLength = view.getUint32(offset, true);
  offset += 4;
  const chunkType = new TextDecoder().decode(new Uint8Array(buffer, offset, 4));
  offset += 4;
  if (chunkType !== "JSON") {
    throw new Error("GLB JSON chunk missing");
  }

  const jsonText = new TextDecoder().decode(new Uint8Array(buffer, offset, chunkLength));
  const data = JSON.parse(jsonText) as {
    animations?: Array<{ name?: string }>;
    meshes?: unknown[];
    skins?: unknown[];
    nodes?: unknown[];
  };

  const animations = (data.animations || []).map((anim, index) => anim.name?.trim() || `animation_${index}`);

  return {
    animations,
    meshCount: (data.meshes || []).length,
    skinCount: (data.skins || []).length,
    nodeCount: (data.nodes || []).length,
    isStatic: animations.length === 0,
  };
}

export async function inspectGlbUrl(url: string): Promise<GlbInspectResult> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to load GLB (${res.status})`);
  return parseGlbJson(await res.arrayBuffer());
}

export async function inspectGlbFile(file: File): Promise<GlbInspectResult> {
  return parseGlbJson(await file.arrayBuffer());
}
