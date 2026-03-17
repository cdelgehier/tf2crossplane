import pytest

from tf2crossplane.settings import ResourceDef, StackSettings, WireDef

# ── Minimal Infra XRD dicts (as would be loaded from xrd.yaml files) ─────────


@pytest.fixture
def kms_xrd() -> dict:
    return {
        "apiVersion": "apiextensions.crossplane.io/v1",
        "kind": "CompositeResourceDefinition",
        "spec": {
            "group": "homelab.crossplane.io",
            "names": {"kind": "XKMSKey", "plural": "xkmskeys"},
            "versions": [
                {
                    "name": "v1alpha1",
                    "served": True,
                    "referenceable": True,
                    "schema": {
                        "openAPIV3Schema": {
                            "type": "object",
                            "properties": {
                                "spec": {
                                    "type": "object",
                                    "properties": {
                                        "providerConfig": {"type": "string"},
                                        "description": {"type": "string"},
                                        "deletion_window_in_days": {"type": "number"},
                                    },
                                }
                            },
                        }
                    },
                }
            ],
        },
    }


@pytest.fixture
def sg_xrd() -> dict:
    return {
        "apiVersion": "apiextensions.crossplane.io/v1",
        "kind": "CompositeResourceDefinition",
        "spec": {
            "group": "homelab.crossplane.io",
            "names": {"kind": "XSecurityGroup", "plural": "xsecuritygroups"},
            "versions": [
                {
                    "name": "v1alpha1",
                    "served": True,
                    "referenceable": True,
                    "schema": {
                        "openAPIV3Schema": {
                            "type": "object",
                            "properties": {
                                "spec": {
                                    "type": "object",
                                    "properties": {
                                        "providerConfig": {"type": "string"},
                                        "ingress": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "x-kubernetes-preserve-unknown-fields": True,
                                            },
                                        },
                                        "egress": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "x-kubernetes-preserve-unknown-fields": True,
                                            },
                                        },
                                    },
                                }
                            },
                        }
                    },
                }
            ],
        },
    }


@pytest.fixture
def ec2_xrd() -> dict:
    return {
        "apiVersion": "apiextensions.crossplane.io/v1",
        "kind": "CompositeResourceDefinition",
        "spec": {
            "group": "homelab.crossplane.io",
            "names": {"kind": "XEC2Instance", "plural": "xec2instances"},
            "versions": [
                {
                    "name": "v1alpha1",
                    "served": True,
                    "referenceable": True,
                    "schema": {
                        "openAPIV3Schema": {
                            "type": "object",
                            "properties": {
                                "spec": {
                                    "type": "object",
                                    "properties": {
                                        "providerConfig": {"type": "string"},
                                        "instance_type": {"type": "string"},
                                        "ami": {"type": "string"},
                                        "kms_key_id": {"type": "string"},
                                        "vpc_security_group_ids": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                    },
                                }
                            },
                        }
                    },
                }
            ],
        },
    }


# ── StackSettings fixtures ────────────────────────────────────────────────────


@pytest.fixture
def stack_settings(tmp_path) -> StackSettings:
    """Minimal StackVM settings with KMS (optional) + EC2 (required) + 1 wire."""
    return StackSettings(
        name="StackVM",
        group="homelab.crossplane.io",
        version="v1alpha1",
        xrd_dir=tmp_path,
        output_dir=tmp_path / "out",
        resources=[
            ResourceDef(
                name="kms",
                xrd="xkmskeys",
                optional=True,
                expose=["description", "deletion_window_in_days"],
            ),
            ResourceDef(
                name="ec2",
                xrd="xec2instances",
                optional=False,
                expose=["instance_type", "ami"],
            ),
        ],
        wires=[
            WireDef(
                source="kms.outputs.key_id",
                target="ec2.kms_key_id",
                fallback="spec.kms.existingId",
            )
        ],
    )


@pytest.fixture
def sg_db_xrd() -> dict:
    return {
        "apiVersion": "apiextensions.crossplane.io/v1",
        "kind": "CompositeResourceDefinition",
        "spec": {
            "group": "homelab.crossplane.io",
            "names": {"kind": "XSecurityGroup", "plural": "xsecuritygroups"},
            "versions": [
                {
                    "name": "v1alpha1",
                    "served": True,
                    "referenceable": True,
                    "schema": {
                        "openAPIV3Schema": {
                            "type": "object",
                            "properties": {
                                "spec": {
                                    "type": "object",
                                    "properties": {
                                        "providerConfig": {"type": "string"},
                                    },
                                }
                            },
                        }
                    },
                }
            ],
        },
    }


@pytest.fixture
def infra_xrds(kms_xrd, ec2_xrd) -> dict:
    return {"kms": kms_xrd, "ec2": ec2_xrd}
