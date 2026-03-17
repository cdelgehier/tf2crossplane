from pathlib import Path

from pydantic import BaseModel, field_validator


class Settings(BaseModel):
    """
    Generation parameters for the infra subcommand (main → generate_xrd / generate_composition).
    """

    module_url: str
    output_dir: str
    group: str
    provider_config: str
    provider_config_kind: str = "ProviderConfig"
    composition_update_policy: str = "Automatic"
    auto_ready: bool = True
    scope: str = "Namespaced"
    function_go_templating: str = "function-go-templating"
    function_auto_ready: str = "function-auto-ready"
    function_patch_and_transform: str = "function-patch-and-transform"
    workspace_api_version: str = "opentofu.m.upbound.io/v1beta1"
    workspace_source: str = "Remote"
    version: str = "v1alpha1"
    kind: str = ""  # override auto-detected kind; derived from module name if empty
    extra_vars: list[str] = []  # format: name:type:description[:default]
    secret_name_format: str = (
        ""  # Go printf format for writeConnectionSecretToRef.name; empty = omit
    )
    provider_config_format: str = ""  # Go printf format for providerConfigRef.name; empty = use spec.providerConfig

    @field_validator("group")
    @classmethod
    def group_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("group must not be empty (e.g. example.crossplane.io)")
        return v

    @field_validator("version")
    @classmethod
    def version_starts_with_v(cls, v: str) -> str:
        if not v.startswith("v"):
            raise ValueError(f"version must start with 'v', got '{v}'")
        return v


class WireDef(BaseModel):
    """A single output wiring between two resources in a Stack."""

    # e.g. "kms.outputs.key_id"
    source: str
    # e.g. "ec2.kms_key_id"
    target: str
    # fallback field path on the XR spec when the source resource is not created
    # e.g. "spec.kms.existingId"
    fallback: str = ""


class ResourceDef(BaseModel):
    """One Infra resource slot in a Stack definition."""

    # logical name used in wires and go-template (e.g. "kms")
    name: str
    # plural name of the XRD to reference (e.g. "xkmskeys")
    xrd: str
    # when True, the resource supports existingId / import modes in addition to create
    optional: bool = False
    # spec fields from the Infra XRD to expose directly on the Stack XRD
    expose: list[str] = []


class StackSettings(BaseModel):
    """
    Generation parameters for the stack subcommand.

    A Stack is a Composition of Compositions: it creates N Infra XRs, passes
    outputs between them via the composite resource status, and supports three
    modes for each optional resource: create, existingId (reference, not managed),
    or import (Crossplane adopts the existing resource).
    """

    name: str  # CamelCase Stack kind, e.g. "StackVM"
    group: str
    version: str = "v1alpha1"
    scope: str = "Namespaced"
    xrd_dir: Path = Path(".")
    output_dir: Path = Path(".")
    resources: list[ResourceDef] = []
    wires: list[WireDef] = []
    function_go_templating: str = "function-go-templating"
    function_auto_ready: str = "function-auto-ready"

    @field_validator("group")
    @classmethod
    def group_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("group must not be empty (e.g. example.crossplane.io)")
        return v

    @field_validator("version")
    @classmethod
    def version_starts_with_v(cls, v: str) -> str:
        if not v.startswith("v"):
            raise ValueError(f"version must start with 'v', got '{v}'")
        return v
