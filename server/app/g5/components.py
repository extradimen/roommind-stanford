"""Strict declaration binding; not proof that an adapter implements its claims."""
from copy import deepcopy

from app.factorial_study import ARMS, digest


def specification(adapter):
    getter = getattr(adapter, "runtime_specification", None)
    value = getter() if getter else getattr(adapter, "specification", None)
    if not isinstance(value, dict) or not value:
        raise ValueError("Adapter must expose a nonempty specification")
    return deepcopy(value)


def verify_components(expected, arm, *, policy, cognition, governance):
    if set(expected) != {"policy", "cognition", "governance"}:
        raise ValueError("Incomplete component bindings")
    for name, adapter in (("policy", policy), ("cognition", cognition), ("governance", governance)):
        enabled = name == "policy" or ARMS[arm][name]
        if enabled:
            if adapter is None or digest(specification(adapter)) != digest(expected[name]):
                raise ValueError(f"Frozen {name} specification changed")
        elif adapter is not None:
            raise ValueError(f"Disabled {name} was supplied")
