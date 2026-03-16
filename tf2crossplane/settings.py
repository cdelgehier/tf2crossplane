from pydantic import BaseModel, field_validator


class Settings(BaseModel):
    """
    Generation parameters passed through the call chain (main → generate_xrd / generate_composition).

    Using pydantic BaseModel instead of a plain dataclass gives us field
    validation for free — e.g. group must not be empty, version must start
    with 'v'. Errors are raised at construction time with a clear message
    rather than silently producing invalid YAML later.
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
    workspace_api_version: str = "opentofu.m.upbound.io/v1beta1"
    workspace_source: str = "Remote"
    version: str = "v1alpha1"
    kind: str = ""  # override auto-detected kind; derived from module name if empty

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
