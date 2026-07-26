#!/usr/bin/env python3
"""Seed scenario 10 with asset-driven scene_graph (room, table, chairs, avatar slots)."""

from __future__ import annotations

import asyncio
import json
import math
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "server"))

ROOM_URL = "/static/props/meeting_room_shell-2-web.glb"
TABLE_URL = "/static/props/conference_table-6-web.glb"
CHAIR_URL = "/static/props/office_chair-1-41805a48-web.glb"
AVATAR_SLOT_ASSET = "asset_avatar_slot"

PI = math.pi
SEAT_SCALE = 1.25

SEATS = {
    "slot_supplier_ceo_global": {"position": [-0.55, 0.0, -1.18], "rotationY": 0.0},
    "slot_supplier_quality_manager": {"position": [0.55, 0.0, -1.18], "rotationY": 0.0},
    "slot_procurement_strategy_manager": {"position": [-0.55, 0.0, 0.42], "rotationY": PI},
    "slot_user": {"position": [0.55, 0.0, 0.42], "rotationY": PI},
}

CHAIRS = {
    "chair_nw": {"position": [-0.55, 0.0, -1.42], "rotationY": 0.0, "label": "chair_north_west"},
    "chair_ne": {"position": [0.55, 0.0, -1.42], "rotationY": 0.0, "label": "chair_north_east"},
    "chair_sw": {"position": [-0.55, 0.0, 0.66], "rotationY": PI, "label": "chair_south_west"},
    "chair_se": {"position": [0.55, 0.0, 0.66], "rotationY": PI, "label": "chair_south_east"},
}

PLOT_BINDING = [
    {"character_id": "supplier_ceo_global", "instance_id": "slot_supplier_ceo_global"},
    {"character_id": "supplier_quality_manager", "instance_id": "slot_supplier_quality_manager"},
    {"character_id": "procurement_strategy_manager", "instance_id": "slot_procurement_strategy_manager"},
    {"character_id": "user", "instance_id": "slot_user"},
]


def build_scene_graph(existing_camera: dict) -> dict:
    assets = {
        "asset_meeting_room": {
            "model_url": ROOM_URL,
            "label": "meeting_room",
            "category": "environment",
            "default_scale": 1.0,
        },
        "asset_conference_table": {
            "model_url": TABLE_URL,
            "label": "conference_table",
            "category": "furniture",
            "default_scale": 1.0,
        },
        "asset_office_chair": {
            "model_url": CHAIR_URL,
            "label": "office_chair",
            "category": "furniture",
            "default_scale": 1.0,
        },
        AVATAR_SLOT_ASSET: {
            "model_url": "",
            "label": "avatar_slot",
            "category": "avatar_slot",
            "default_scale": 1.0,
        },
    }

    instances = [
        {
            "id": "inst_meeting_room",
            "asset_id": "asset_meeting_room",
            "role": "environment",
            "editor_label": "meeting_room",
            "locked": True,
            "transform": {"position": [0.0, 0.0, 0.0], "rotationY": 0.0, "scale": 1.0},
        },
        {
            "id": "inst_conference_table",
            "asset_id": "asset_conference_table",
            "role": "prop",
            "editor_label": "conference_table",
            "transform": {"position": [0.0, 0.0, -0.4], "rotationY": 0.0, "scale": 1.0},
        },
    ]

    for cid, pose in CHAIRS.items():
        instances.append(
            {
                "id": cid,
                "asset_id": "asset_office_chair",
                "role": "prop",
                "editor_label": pose["label"],
                "transform": {
                    "position": pose["position"],
                    "rotationY": pose["rotationY"],
                    "scale": 1.0,
                },
            }
        )

    for sid, pose in SEATS.items():
        instances.append(
            {
                "id": sid,
                "asset_id": AVATAR_SLOT_ASSET,
                "role": "avatar_slot",
                "editor_label": sid,
                "transform": {
                    "position": pose["position"],
                    "rotationY": pose["rotationY"],
                    "scale": SEAT_SCALE,
                },
            }
        )

    camera = existing_camera if isinstance(existing_camera, dict) and existing_camera else {}
    if "full" not in camera:
        camera["full"] = {
            "position": [0.0, 2.3, 4.2],
            "fov": 55,
            "distance": 5.0,
            "min": 2.2,
            "max": 10,
        }
    if "compact" not in camera:
        camera["compact"] = {
            "position": [0.0, 2.5, 4.8],
            "fov": 48,
            "distance": 5.5,
            "min": 2.6,
            "max": 9.5,
        }

    return {
        "version": 1,
        "assets": assets,
        "instances": instances,
        "constraints": [],
        "camera": camera,
    }


async def main() -> None:
    engine = create_async_engine(
        "postgresql+asyncpg://roommind:roommind_dev@127.0.0.1:5432/roommind_stanford"
    )
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        row = (
            await session.execute(
                text("SELECT scene_config FROM scenario_templates WHERE id = 10")
            )
        ).fetchone()
        if not row:
            print("scenario 10 not found")
            return
        scene = dict(row[0] or {})
        existing_camera = (scene.get("scene_graph") or {}).get("camera")
        scene["scene_graph"] = build_scene_graph(existing_camera or {})
        scene["plot_cast_binding"] = PLOT_BINDING
        await session.execute(
            text("UPDATE scenario_templates SET scene_config = CAST(:cfg AS jsonb) WHERE id = 10"),
            {"cfg": json.dumps(scene)},
        )
        await session.commit()
        print("patched scenario 10")
        print("assets:", list(scene["scene_graph"]["assets"].keys()))
        print("instances:", [i["id"] for i in scene["scene_graph"]["instances"]])
        print("bindings:", scene["plot_cast_binding"])


if __name__ == "__main__":
    asyncio.run(main())
