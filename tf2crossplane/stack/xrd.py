"""Generate the XRD for a Stack (Composition of Compositions)."""

from tf2crossplane.settings import ResourceDef, StackSettings
from tf2crossplane.stack.reader import load_xrd, xrd_spec_properties


def _plural(kind: str) -> str:
    """'StackVM' → 'xstackvms'  (lowercase x-prefix + plural)."""
    lower = kind.lower()
    plural = lower + "s" if not lower.endswith("s") else lower
    return f"x{plural}"


def _composite_kind(kind: str) -> str:
    """'StackVM' → 'XStackVM'."""
    return f"X{kind}"


def _claim_kind(kind: str) -> str:
    """'StackVM' → 'StackVM' (the Claim keeps the plain name)."""
    return kind


def _build_resource_section(resource: ResourceDef, xrd_dir, group: str) -> dict:
    """
    Build the spec properties block for one resource slot.

    For optional resources three modes are supported:
    - create: fields forwarded from the Infra XRD (filtered to resource.expose)
    - existingId: string — cloud-native identifier (ARN, resource ID…), resource not managed
    - import: string — cloud-native identifier, Crossplane adopts the resource
    """
    try:
        infra_xrd = load_xrd(xrd_dir, resource.xrd)
        infra_props = xrd_spec_properties(infra_xrd)
    except FileNotFoundError:
        infra_props = {}

    # Keep only the exposed fields (or all if expose is empty)
    if resource.expose:
        exposed = {k: v for k, v in infra_props.items() if k in resource.expose}
    else:
        # Exclude internal Crossplane fields
        skip = {"providerConfig", "writeConnectionSecretToRef"}
        exposed = {k: v for k, v in infra_props.items() if k not in skip}

    section: dict = {"type": "object", "properties": exposed}

    if resource.optional:
        section["properties"]["existingId"] = {
            "type": "string",
            "description": (
                f"Cloud-native identifier of a pre-existing {resource.name} resource "
                f"(ARN, resource ID…). When set, no {resource.name} is created — "
                "the identifier is passed directly to dependent resources."
            ),
        }
        section["properties"]["import"] = {
            "type": "string",
            "description": (
                f"Cloud-native identifier of a pre-existing {resource.name} resource "
                "to import. Crossplane will adopt and manage it going forward."
            ),
        }

    return section


def generate_stack_xrd(
    settings: StackSettings,
    infra_xrds: dict[str, dict],
) -> dict:
    """
    Build the XRD manifest for a Stack.

    Parameters
    ----------
    settings:
        StackSettings with name, group, version, resources, wires.
    infra_xrds:
        Mapping of resource logical name → loaded XRD dict (from reader.load_xrd).
    """
    plural = _plural(settings.name)
    composite_kind = _composite_kind(settings.name)

    # Build spec.properties: one sub-object per resource + providerConfig
    spec_properties: dict = {
        "providerConfig": {
            "type": "string",
            "description": "Name of the ProviderConfig to use for all composed resources.",
        }
    }

    for resource in settings.resources:
        infra_xrd = infra_xrds.get(resource.name, {})
        infra_props = xrd_spec_properties(infra_xrd) if infra_xrd else {}

        if resource.expose:
            exposed = {k: v for k, v in infra_props.items() if k in resource.expose}
        else:
            skip = {"providerConfig", "writeConnectionSecretToRef"}
            exposed = {k: v for k, v in infra_props.items() if k not in skip}

        section: dict = {"type": "object", "properties": dict(exposed)}

        if resource.optional:
            section["properties"]["existingId"] = {
                "type": "string",
                "description": (
                    f"Cloud-native identifier of a pre-existing {resource.name} "
                    "(ARN, resource ID…). When set no resource is created; "
                    "the identifier is forwarded to dependent resources."
                ),
            }
            section["properties"]["import"] = {
                "type": "string",
                "description": (
                    f"Cloud-native identifier of a pre-existing {resource.name} "
                    "to adopt. Crossplane will manage it going forward."
                ),
            }

        spec_properties[resource.name] = section

    # status.outputs: one entry per wire source so consumers can read resolved IDs
    status_properties: dict = {}
    for wire in settings.wires:
        # wire.source = "kms.outputs.key_id" → status key = "kmsKeyId"
        parts = wire.source.split(".")
        if len(parts) >= 3:
            resource_name, _, field = parts[0], parts[1], parts[2]
            status_key = _to_camel(f"{resource_name}_{field}")
            status_properties[status_key] = {
                "type": "string",
                "description": f"Resolved output: {wire.source}",
            }

    schema: dict = {
        "type": "object",
        "properties": {
            "spec": {
                "type": "object",
                "required": ["providerConfig"],
                "properties": spec_properties,
            },
        },
    }
    if status_properties:
        schema["properties"]["status"] = {
            "type": "object",
            "properties": status_properties,
        }

    return {
        "apiVersion": "apiextensions.crossplane.io/v2",
        "kind": "CompositeResourceDefinition",
        "metadata": {
            "name": f"{plural}.{settings.group}",
        },
        "spec": {
            "group": settings.group,
            "scope": settings.scope,
            "names": {
                "kind": composite_kind,
                "plural": plural,
            },
            "defaultCompositionRef": {
                "name": f"{plural}.{settings.group}",
            },
            "versions": [
                {
                    "name": settings.version,
                    "served": True,
                    "referenceable": True,
                    "schema": {
                        "openAPIV3Schema": schema,
                    },
                }
            ],
        },
    }


def _to_camel(snake: str) -> str:
    """'kms_key_id' → 'kmsKeyId'."""
    parts = snake.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])
