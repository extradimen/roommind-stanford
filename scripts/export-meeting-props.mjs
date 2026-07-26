/**
 * Export procedural meeting room shell and conference table as GLB props.
 * Run: node scripts/export-meeting-props.mjs
 */
import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import * as THREE from "../client/node_modules/three/build/three.module.js";
import { GLTFExporter } from "../client/node_modules/three/examples/jsm/exporters/GLTFExporter.js";

// GLTFExporter expects browser FileReader when serializing buffers.
if (typeof globalThis.FileReader === "undefined") {
  globalThis.FileReader = class FileReader {
    result = null;
    onload = null;
    onerror = null;
    readAsArrayBuffer(blob) {
      try {
        if (blob instanceof ArrayBuffer) this.result = blob;
        else if (ArrayBuffer.isView(blob)) this.result = blob.buffer;
        else if (typeof blob?.arrayBuffer === "function") {
          blob.arrayBuffer().then((buf) => {
            this.result = buf;
            this.onload?.({ target: this });
          });
          return;
        } else {
          this.result = blob;
        }
        queueMicrotask(() => this.onload?.({ target: this }));
      } catch (err) {
        queueMicrotask(() => this.onerror?.(err));
      }
    }
  };
}

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT_DIR = path.resolve(__dirname, "../server/data/props");
console.log("export-meeting-props: start", OUT_DIR);

function meshBox(w, h, d, color, metalness = 0, roughness = 0.9) {
  const geo = new THREE.BoxGeometry(w, h, d);
  const mat = new THREE.MeshStandardMaterial({ color, metalness, roughness });
  return new THREE.Mesh(geo, mat);
}

function meshPlane(w, h, color) {
  const geo = new THREE.PlaneGeometry(w, h);
  const mat = new THREE.MeshStandardMaterial({ color, roughness: 0.92, side: THREE.DoubleSide });
  return new THREE.Mesh(geo, mat);
}

function add(group, mesh, x, y, z, rx = 0, ry = 0, rz = 0) {
  mesh.position.set(x, y, z);
  mesh.rotation.set(rx, ry, rz);
  mesh.name = mesh.name || `part_${group.children.length}`;
  group.add(mesh);
  return mesh;
}

function buildMeetingRoom() {
  const root = new THREE.Group();
  root.name = "meeting_room";

  const floor = "#b8a898";
  const wall = "#ddd5c8";
  const whiteWall = "#f2f2f0";
  const ceiling = "#f2ebe3";
  const trim = "#c4b8a8";

  add(root, meshPlane(14, 14, floor), 0, 0, 0, -Math.PI / 2, 0, 0).name = "floor";

  add(root, meshPlane(14, 4.8, whiteWall), 0, 2.2, -5.2).name = "wall_north";
  add(root, meshPlane(12, 4.8, wall), -6.8, 2.2, 0, 0, Math.PI / 2, 0).name = "wall_west";
  add(root, meshPlane(12, 4.8, wall), 6.8, 2.2, 0, 0, -Math.PI / 2, 0).name = "wall_east";

  // South window bay (simplified)
  add(root, meshPlane(11, 4.2, "#87ceeb"), 0, 2.2, 5.45).name = "window_sky";
  add(root, meshBox(2.5, 4.8, 0.12, wall), -5.55, 2.2, 5.18).name = "wall_south_w";
  add(root, meshBox(2.5, 4.8, 0.12, wall), 5.55, 2.2, 5.18).name = "wall_south_e";
  add(root, meshBox(11, 0.1, 0.35, "#e8e4dc"), 0, 0.32, 5.1).name = "window_sill";

  add(root, meshPlane(14, 12, ceiling), 0, 4.2, 0, Math.PI / 2, 0, 0).name = "ceiling";

  for (const x of [-1.2, 1.2]) {
    add(root, meshPlane(1.4, 0.7, "#fffaf0"), x, 4.05, -0.2, Math.PI / 2, 0, 0).name = `light_panel_${x}`;
  }

  add(root, meshBox(14, 0.08, 0.06, trim), 0, 0.12, -5.05).name = "baseboard_n";
  add(root, meshBox(14, 0.08, 0.06, trim), 0, 0.12, 5.05).name = "baseboard_s";

  return root;
}

function buildConferenceTable() {
  const root = new THREE.Group();
  root.name = "conference_table";

  const wood = "#6b4f3a";
  const dark = "#4a3728";

  // Origin at floor under table center; tabletop center at local (0, 0.75, 0)
  add(root, meshBox(3.8, 0.08, 1.65, wood, 0, 0.72), 0, 0.75, 0).name = "table_top";
  add(root, meshBox(1.6, 0.012, 0.38, dark), 0, 0.795, 0).name = "table_inset";
  for (const x of [-0.55, 0.55]) {
    add(root, meshBox(0.22, 0.02, 0.22, "#e8e0d4", 0, 0.6), x, 0.79, 0).name = `coaster_${x}`;
  }
  add(root, meshBox(0.2, 0.76, 0.2, dark, 0, 0.8), 0, 0.38, 0).name = "table_leg";

  return root;
}

async function exportGlb(object, filename) {
  const exporter = new GLTFExporter();
  const arrayBuffer = await new Promise((resolve, reject) => {
    exporter.parse(
      object,
      (result) => {
        if (result instanceof ArrayBuffer) resolve(result);
        else reject(new Error("Expected binary GLB"));
      },
      (err) => reject(err),
      { binary: true },
    );
  });
  fs.mkdirSync(OUT_DIR, { recursive: true });
  const outPath = path.join(OUT_DIR, filename);
  fs.writeFileSync(outPath, Buffer.from(arrayBuffer));
  console.log("wrote", outPath, arrayBuffer.byteLength, "bytes");
  return outPath;
}

const room = buildMeetingRoom();
const table = buildConferenceTable();

await exportGlb(room, "meeting_room_shell-1.glb");
await exportGlb(table, "conference_table-1.glb");
