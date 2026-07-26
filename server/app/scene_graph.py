"""Sanitize scene_graph and plot_cast_binding in scene_config."""

from __future__ import annotations

from typing import Any

SCENE_GRAPH_KEYS = ("scene_graph", "plot_cast_binding")

ASSET_CATEGORIES = frozenset({"environment", "furniture", "avatar_slot", "decor"})
INSTANCE_ROLES = frozenset({"environment", "prop", "avatar_slot"})
CONSTRAINT_MODES = frozenset({"attach", "position_only", "inherit_scale"})
INHERIT_KEYS = frozenset({"position", "rotationY", "scale"})

DEFAULT_OFFICE_CHAIR_URL = "/static/props/office_chair-1-41805a48-web.glb"

CHAIR_FIT_HEIGHT = 0.72
CHAIR_GROUP_SCALE = 0.88

NEGOTIATION_CHAIR_POSES = [
    {"id": "chair_nw", "label": "chair_north_west", "position": [-0.58, 0.0, -1.34], "rotationY": 3.141592653589793, "scale": CHAIR_GROUP_SCALE},
    {"id": "chair_ne", "label": "chair_north_east", "position": [0.58, 0.0, -1.34], "rotationY": 3.141592653589793, "scale": CHAIR_GROUP_SCALE},
    {"id": "chair_sw", "label": "chair_south_west", "position": [-0.58, 0.0, 0.58], "rotationY": 0.0, "scale": CHAIR_GROUP_SCALE},
    {"id": "chair_se", "label": "chair_south_east", "position": [0.58, 0.0, 0.58], "rotationY": 0.0, "scale": CHAIR_GROUP_SCALE},
]


def _is_chair_asset_url(url: str) -> bool:
    lowered = url.strip().lower()
    if not lowered:
        return False
    if "conference_table" in lowered or "meeting_table" in lowered:
        return False
    return "office_chair" in lowered or "chair" in lowered


def ensure_negotiation_chairs(graph: dict[str, Any]) -> dict[str, Any]:
    """Add four meeting chairs when a chair asset exists or can be registered."""
    assets = dict(graph.get("assets") or {})
    chair_asset_id = next(
        (key for key, asset in assets.items() if _is_chair_asset_url(str(asset.get("model_url") or ""))),
        None,
    )
    if not chair_asset_id:
        chair_asset_id = "asset_office_chair"
        assets[chair_asset_id] = {
            "model_url": DEFAULT_OFFICE_CHAIR_URL,
            "label": chair_asset_id,
            "category": "furniture",
            "default_scale": 1.0,
        }

    instances = list(graph.get("instances") or [])
    chair_pose_by_id = {pose["id"]: pose for pose in NEGOTIATION_CHAIR_POSES}
    synced: list[dict[str, Any]] = []
    for item in instances:
        if not isinstance(item, dict):
            continue
        inst_id = str(item.get("id") or "")
        if str(item.get("asset_id") or "") == chair_asset_id and inst_id in chair_pose_by_id:
            pose = chair_pose_by_id[inst_id]
            synced.append(
                {
                    **item,
                    "transform": {
                        "position": list(pose["position"]),
                        "rotationY": pose["rotationY"],
                        "scale": pose.get("scale", CHAIR_GROUP_SCALE),
                    },
                }
            )
        else:
            synced.append(item)
    instances = synced
    existing_ids = {str(item.get("id") or "") for item in instances if isinstance(item, dict)}
    for pose in NEGOTIATION_CHAIR_POSES:
        if pose["id"] in existing_ids:
            continue
        instances.append(
            {
                "id": pose["id"],
                "asset_id": chair_asset_id,
                "role": "prop",
                "editor_label": pose["label"],
                "transform": {
                    "position": list(pose["position"]),
                    "rotationY": pose["rotationY"],
                    "scale": pose.get("scale", CHAIR_GROUP_SCALE),
                },
            }
        )

    return {**graph, "assets": assets, "instances": instances}


def _num(value: Any, fallback: float) -> float:
    try:
        n = float(value)
        return n if __import__("math").isfinite(n) else fallback
    except (TypeError, ValueError):
        return fallback


def _vec3(raw: Any, fallback: list[float]) -> list[float]:
    if not isinstance(raw, (list, tuple)) or len(raw) < 3:
        return list(fallback)
    return [_num(raw[0], fallback[0]), _num(raw[1], fallback[1]), _num(raw[2], fallback[2])]


def _sanitize_transform(raw: Any) -> dict[str, Any]:
    base = {"position": [0.0, 0.0, 0.0], "rotationY": 0.0, "scale": 1.0}
    if not isinstance(raw, dict):
        return base
    return {
        "position": _vec3(raw.get("position"), base["position"]),
        "rotationY": _num(raw.get("rotationY"), 0.0),
        "scale": max(0.1, min(3.0, _num(raw.get("scale"), 1.0))),
    }


def sanitize_scene_graph(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"version": 1, "assets": {}, "instances": [], "constraints": [], "camera": {}}

    assets_out: dict[str, Any] = {}
    assets = raw.get("assets")
    if isinstance(assets, dict):
        for key, item in assets.items():
            if not isinstance(key, str) or not isinstance(item, dict):
                continue
            url = str(item.get("model_url") or "").strip()
            cat = str(item.get("category") or "decor")
            if cat not in ASSET_CATEGORIES:
                cat = "decor"
            assets_out[key] = {
                "model_url": url,
                "label": str(item.get("label") or key),
                "category": cat,
                "default_scale": max(0.1, min(3.0, _num(item.get("default_scale"), 1.0))),
            }

    instances_out: list[dict[str, Any]] = []
    instances = raw.get("instances")
    if isinstance(instances, list):
        for item in instances:
            if not isinstance(item, dict):
                continue
            iid = str(item.get("id") or "").strip()
            aid = str(item.get("asset_id") or "").strip()
            if not iid or not aid or aid not in assets_out:
                continue
            role = str(item.get("role") or assets_out[aid]["category"])
            if role not in INSTANCE_ROLES:
                role = "prop"
            instances_out.append(
                {
                    "id": iid,
                    "asset_id": aid,
                    "role": role,
                    "editor_label": str(item.get("editor_label") or iid),
                    "transform": _sanitize_transform(item.get("transform")),
                    "locked": bool(item.get("locked")),
                }
            )

    instance_ids = {i["id"] for i in instances_out}
    constraints_out: list[dict[str, Any]] = []
    constraints = raw.get("constraints")
    if isinstance(constraints, list):
        for item in constraints:
            if not isinstance(item, dict):
                continue
            cid = str(item.get("id") or "").strip()
            child = str(item.get("child_id") or "").strip()
            parent = str(item.get("parent_id") or "").strip()
            if not cid or child not in instance_ids or parent not in instance_ids or child == parent:
                continue
            mode = str(item.get("mode") or "attach")
            if mode not in CONSTRAINT_MODES:
                mode = "attach"
            inherit_raw = item.get("inherit")
            inherit: list[str] = []
            if isinstance(inherit_raw, list):
                inherit = [str(x) for x in inherit_raw if str(x) in INHERIT_KEYS]
            if not inherit:
                inherit = ["position", "rotationY", "scale"] if mode == "attach" else ["position"]
            constraints_out.append(
                {
                    "id": cid,
                    "child_id": child,
                    "parent_id": parent,
                    "mode": mode,
                    "inherit": inherit,
                    "offset": _sanitize_transform(item.get("offset")),
                }
            )

    camera = raw.get("camera") if isinstance(raw.get("camera"), dict) else {}

    return {
        "version": int(raw.get("version") or 1),
        "assets": assets_out,
        "instances": instances_out,
        "constraints": constraints_out,
        "camera": camera,
    }


def sanitize_plot_cast_binding(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    seen_chars: set[str] = set()
    seen_inst: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        cid = str(item.get("character_id") or "").strip()
        iid = str(item.get("instance_id") or "").strip()
        if not cid or not iid or cid in seen_chars or iid in seen_inst:
            continue
        seen_chars.add(cid)
        seen_inst.add(iid)
        out.append({"character_id": cid, "instance_id": iid})
    return out
