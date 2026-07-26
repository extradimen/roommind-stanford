#!/usr/bin/env python3
"""Export meeting room shell and conference table as GLB props with PBR materials."""

from __future__ import annotations

import sys
from pathlib import Path

import trimesh
from trimesh.visual.material import PBRMaterial

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "server" / "data" / "props"

# Palette aligned with the former procedural MeetingRoom component.
COLORS = {
    "floor": "#b8a898",
    "wall": "#ddd5c8",
    "north_wall": "#f2f2f0",
    "ceiling": "#f2ebe3",
    "trim": "#c4b8a8",
    "sky": "#87ceeb",
    "sill": "#e8e4dc",
    "light_panel": "#fffaf0",
    "frame": "#3a3a3a",
    "wood": "#6b4f3a",
    "wood_dark": "#4a3728",
    "coaster": "#e8e0d4",
}


def hex_to_rgba(hex_color: str, alpha: float = 1.0) -> list[float]:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))
    return [r, g, b, alpha]


def part(w: float, h: float, d: float, color: str) -> trimesh.Trimesh:
    mesh = trimesh.creation.box(extents=(w, h, d))
    mesh.visual.material = PBRMaterial(
        baseColorFactor=hex_to_rgba(color),
        metallicFactor=0.0,
        roughnessFactor=0.9,
    )
    return mesh


def build_meeting_room() -> trimesh.Scene:
    scene = trimesh.Scene()

    def add(mesh: trimesh.Trimesh, pos: tuple[float, float, float], name: str) -> None:
        mesh.apply_translation(pos)
        scene.add_geometry(mesh, geom_name=name)

    # Floor — horizontal slab at y=0
    add(part(14, 0.05, 14, COLORS["floor"]), (0, 0.025, 0), "floor")

    # North wall (plain white, z = -5.2)
    add(part(14, 4.8, 0.12, COLORS["north_wall"]), (0, 2.2, -5.2), "wall_north")

    # Side walls
    add(part(0.12, 4.8, 12, COLORS["wall"]), (-6.8, 2.2, 0), "wall_west")
    add(part(0.12, 4.8, 12, COLORS["wall"]), (6.8, 2.2, 0), "wall_east")

    # South window bay — flanking columns + sky backdrop
    add(part(2.5, 4.8, 0.12, COLORS["wall"]), (-5.55, 2.2, 5.18), "wall_south_w")
    add(part(2.5, 4.8, 0.12, COLORS["wall"]), (5.55, 2.2, 5.18), "wall_south_e")
    add(part(11, 4.2, 0.04, COLORS["sky"]), (0, 2.2, 5.45), "window_sky")
    add(part(11, 0.1, 0.35, COLORS["sill"]), (0, 0.32, 5.1), "window_sill")

    # Window mullions
    for x in (-3.6, -1.2, 1.2, 3.6):
        add(part(0.1, 3.85, 0.08, COLORS["frame"]), (x, 2.05, 5.16), f"mullion_{x}")
    add(part(10.8, 0.14, 0.14, COLORS["frame"]), (0, 0.22, 5.16), "frame_bottom")
    add(part(10.8, 0.14, 0.14, COLORS["frame"]), (0, 3.88, 5.16), "frame_top")

    # Ceiling
    add(part(14, 0.08, 12, COLORS["ceiling"]), (0, 4.2, 0), "ceiling")

    # Ceiling light panels (emissive look via brighter color)
    for x in (-1.2, 1.2):
        panel = part(1.4, 0.04, 0.7, COLORS["light_panel"])
        panel.visual.material = PBRMaterial(
            baseColorFactor=hex_to_rgba("#fffaf0"),
            emissiveFactor=hex_to_rgba("#ffe9c7")[:3],
            metallicFactor=0.0,
            roughnessFactor=0.6,
        )
        add(panel, (x, 4.05, -0.2), f"light_panel_{x}")

    # Baseboards
    add(part(14, 0.08, 0.06, COLORS["trim"]), (0, 0.12, -5.05), "baseboard_n")
    add(part(14, 0.08, 0.06, COLORS["trim"]), (0, 0.12, 5.05), "baseboard_s")

    return scene


# Raise tabletop center above legacy 0.75 m (≈ +24 cm; surface ~1.03 m).
TABLE_HEIGHT_LIFT = 0.24


def build_conference_table() -> trimesh.Scene:
    scene = trimesh.Scene()
    lift = TABLE_HEIGHT_LIFT

    def add(mesh: trimesh.Trimesh, pos: tuple[float, float, float], name: str) -> None:
        mesh.apply_translation(pos)
        scene.add_geometry(mesh, geom_name=name)

    add(part(3.8, 0.08, 1.65, COLORS["wood"]), (0, 0.75 + lift, 0), "table_top")
    add(part(1.6, 0.012, 0.38, COLORS["wood_dark"]), (0, 0.795 + lift, 0), "table_inset")
    for x in (-0.55, 0.55):
        add(part(0.22, 0.02, 0.22, COLORS["coaster"]), (x, 0.79 + lift, 0), f"coaster_{x}")
    add(part(0.2, 0.76, 0.2, COLORS["wood_dark"]), (0, 0.38 + lift, 0), "table_leg")
    return scene


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    room_path = OUT / "meeting_room_shell-2.glb"
    table_path = OUT / "conference_table-6.glb"
    build_meeting_room().export(room_path)
    build_conference_table().export(table_path)
    print("wrote", room_path, room_path.stat().st_size)
    print("wrote", table_path, table_path.stat().st_size)

    sys.path.insert(0, str(REPO / "server"))
    from app.avatar_assets import optimize_glb_for_web

    urls: list[str] = []
    for p in (room_path, table_path):
        web = optimize_glb_for_web(p)
        if web:
            print("optimized", web.name, web.stat().st_size)
            urls.append(f"/static/props/{web.name}")
    if urls:
        print("urls:", urls)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
