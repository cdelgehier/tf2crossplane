"""Read Infra XRD YAML files to discover available spec fields and status outputs."""

from pathlib import Path

import yaml


def load_xrd(xrd_dir: Path, xrd_plural: str) -> dict:
    """
    Find and load the XRD YAML for the given plural name.

    Searches xrd_dir recursively for an xrd.yaml whose spec.names.plural matches
    xrd_plural (e.g. "xkmskeys"). Returns the parsed dict or raises FileNotFoundError.
    """
    for path in sorted(xrd_dir.rglob("xrd.yaml")):
        with open(path) as f:
            doc = yaml.safe_load(f)
        if not isinstance(doc, dict):
            continue
        plural = doc.get("spec", {}).get("names", {}).get("plural", "")
        if plural == xrd_plural:
            return doc

    raise FileNotFoundError(
        f"No XRD with spec.names.plural='{xrd_plural}' found under {xrd_dir}"
    )


def xrd_spec_properties(xrd: dict) -> dict:
    """Return the spec.properties dict from an XRD's openAPIV3Schema (first version)."""
    try:
        versions = xrd["spec"]["versions"]
        schema = versions[0]["schema"]["openAPIV3Schema"]
        return schema["properties"]["spec"]["properties"]
    except (KeyError, IndexError):  # fmt: skip
        return {}


def xrd_kind(xrd: dict) -> str:
    """Return the composite kind (e.g. 'XKMSKey') from an XRD."""
    return xrd.get("spec", {}).get("names", {}).get("kind", "")


def xrd_group(xrd: dict) -> str:
    """Return the API group from an XRD."""
    return xrd.get("spec", {}).get("group", "")
