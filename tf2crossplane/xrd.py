from typing import Any

from tf2crossplane.parser import tf_type_to_openapi
from tf2crossplane.settings import Settings


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

    properties: dict[str, Any] = {
        "providerConfig": {
            "type": "string",
            "description": "ProviderConfig to use (e.g. my-provider-config, my-other-provider-config)",
        }
    }
    required = ["providerConfig"]

    for var_name, var_def in variables.items():
        schema = tf_type_to_openapi(var_def.get("type"))
        if desc := var_def.get("description", ""):
            schema["description"] = desc
        if (default := var_def.get("default")) is not None:
            schema["default"] = default
        else:
            required.append(var_name)
        properties[var_name] = schema

    return {
        "apiVersion": "apiextensions.crossplane.io/v2",
        "kind": "CompositeResourceDefinition",
        "metadata": {
            "name": f"{composite_plural}.{settings.group}",
        },
        "spec": {
            "scope": "Namespaced",
            "group": settings.group,
            "names": {
                "kind": composite_kind,
                "plural": composite_plural,
            },
            "defaultCompositionUpdatePolicy": "Manual",
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
                                        "outputs": {
                                            "type": "object",
                                            "x-kubernetes-preserve-unknown-fields": True,
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
