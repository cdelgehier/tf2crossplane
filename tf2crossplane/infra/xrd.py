from typing import Any

from tf2crossplane.infra.parser import tf_type_to_openapi
from tf2crossplane.settings import Settings


def _parse_extra_var(raw: str) -> tuple[str, dict[str, Any]]:
    """
    Parse an --extra-var string into a (name, var_def) pair compatible with generate_xrd.

    Format: name:type:description  (required field, no default)
            name:type:description:default  (optional field with default)

    Examples:
      "target_region:string:AWS region"               → required
      "environment:string:Target environment:prod"    → optional, default "prod"
    """
    parts = raw.split(":", 3)
    if len(parts) < 2:
        raise ValueError(
            f"--extra-var must be 'name:type', 'name:type:description', or "
            f"'name:type:description:default', got: {raw!r}"
        )
    name = parts[0].strip()
    type_ = parts[1].strip()
    desc = parts[2].strip() if len(parts) > 2 else ""
    var_def: dict[str, Any] = {"type": type_, "description": desc}
    if len(parts) > 3:
        var_def["default"] = parts[3]
    return name, var_def


_COMPLEX_OUTPUT_HINTS = ("map", "object", "list", "set")


def _output_schema(out_def: dict[str, Any]) -> dict[str, Any]:
    """
    Return an OpenAPI schema fragment for a Terraform output.

    Terraform outputs have no type declaration, so we fall back to string.
    When the description hints at a complex type (map, object, list, set) we
    use x-kubernetes-preserve-unknown-fields instead to avoid validation
    errors when OpenTofu returns a non-string value at runtime.
    """
    raw_desc = out_def.get("description", "")
    description = raw_desc[0] if isinstance(raw_desc, list) else raw_desc
    desc_lower = description.lower()
    if any(hint in desc_lower for hint in _COMPLEX_OUTPUT_HINTS):
        return {
            "x-kubernetes-preserve-unknown-fields": True,
            "description": description,
        }
    return {"type": "string", "description": description}


def generate_xrd(
    variables: dict[str, Any],
    outputs: dict[str, Any],
    kind: str,
    settings: Settings,
) -> dict:
    """Generate a CompositeResourceDefinition manifest.

    A XRD is the Crossplane equivalent of a Kubernetes CRD: it declares the
    API (group, kind, versions) and the validation schema for a composite
    resource. Kubernetes requires CRD schemas to be expressed in OpenAPI v3
    (spec.versions[].schema.openAPIV3Schema), which is why every Terraform
    type is first converted to an OpenAPI fragment via tf_type_to_openapi()
    before being embedded here.
    """
    composite_kind = "X" + kind
    plural = kind.lower() + "s"
    composite_plural = "x" + plural

    # When provider_config_format is set the ProviderConfig name is computed
    # dynamically from other spec fields; exposing a redundant providerConfig
    # field in the XRD would be misleading ("which one wins?").
    if settings.provider_config_format:
        properties: dict[str, Any] = {}
        required: list[str] = []
    else:
        properties = {
            "providerConfig": {
                "type": "string",
                "description": "ProviderConfig to use (e.g. my-provider-config, my-other-provider-config)",
            }
        }
        required = ["providerConfig"]

    all_vars = dict(variables)
    for raw in settings.extra_vars:
        name, var_def = _parse_extra_var(raw)
        all_vars[name] = var_def

    for var_name, var_def in all_vars.items():
        default = var_def.get("default")
        schema = tf_type_to_openapi(var_def.get("type"), default)
        if desc := var_def.get("description", ""):
            schema["description"] = desc
        # Never embed default in the schema — Kubernetes rejects a default: []
        # on type: object (and vice-versa). The default value is only used above
        # to infer the correct OpenAPI type for ambiguous Terraform types (any).
        if "default" not in var_def:
            required.append(var_name)
        properties[var_name] = schema

    return {
        "apiVersion": "apiextensions.crossplane.io/v2",
        "kind": "CompositeResourceDefinition",
        "metadata": {
            "name": f"{composite_plural}.{settings.group}",
        },
        "spec": {
            "scope": settings.scope,
            "group": settings.group,
            "names": {
                "kind": composite_kind,
                "plural": composite_plural,
            },
            "defaultCompositionRef": {
                "name": f"{composite_plural}.{settings.group}",
            },
            "defaultCompositionUpdatePolicy": settings.composition_update_policy,
            "versions": [
                {
                    "name": settings.version,
                    "served": True,
                    "referenceable": True,
                    "schema": {
                        "openAPIV3Schema": {
                            "type": "object",
                            "properties": {
                                "spec": {
                                    "type": "object",
                                    "properties": properties,
                                    "required": required,
                                },
                                "status": {
                                    "type": "object",
                                    "properties": {
                                        "atProvider": {
                                            "type": "object",
                                            "properties": {
                                                "outputs": {
                                                    "type": "object",
                                                    "x-kubernetes-preserve-unknown-fields": True,
                                                    "properties": {
                                                        out_name: _output_schema(
                                                            out_def
                                                        )
                                                        for out_name, out_def in outputs.items()
                                                    },
                                                }
                                            },
                                        }
                                    },
                                },
                            },
                        }
                    },
                }
            ],
        },
    }
