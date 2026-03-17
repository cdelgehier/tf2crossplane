import shutil
from pathlib import Path

import click
import yaml

from tf2crossplane.infra.composition import generate_composition
from tf2crossplane.infra.parser import (
    clone_module,
    module_name_from_url,
    module_name_to_kind,
    parse_outputs,
    parse_variables,
)
from tf2crossplane.infra.xrd import generate_xrd
from tf2crossplane.logger import LOGGER
from tf2crossplane.settings import Settings


@click.group()
def cli() -> None:
    """Generate Crossplane artifacts from Terraform modules or XRD definitions."""


@cli.command("infra")
@click.option(
    "--module-url",
    required=True,
    help="Git URL of Terraform module (e.g. git::https://...?ref=v1.0.0)",
)
@click.option(
    "--output-dir",
    default=".",
    show_default=True,
    help="Output directory for generated YAML files",
)
@click.option(
    "--group",
    default="example.crossplane.io",
    show_default=True,
    help="Crossplane API group",
)
@click.option(
    "--provider-config",
    default="my-provider-config",
    show_default=True,
    help="Default ProviderConfig name",
)
@click.option("--version", default="v1alpha1", show_default=True, help="API version")
@click.option(
    "--kind", default="", help="Override auto-detected kind (CamelCase, e.g. S3Bucket)"
)
@click.option(
    "--provider-config-kind",
    default="ProviderConfig",
    show_default=True,
    help="Kind for providerConfigRef (ProviderConfig or ClusterProviderConfig)",
)
@click.option(
    "--composition-update-policy",
    default="Automatic",
    show_default=True,
    help="defaultCompositionUpdatePolicy in the XRD (Automatic or Manual)",
)
@click.option(
    "--workspace-source",
    default="Remote",
    show_default=True,
    type=click.Choice(["Remote", "Inline", "Module"], case_sensitive=True),
    help="source field of the Workspace forProvider (Remote, Inline, or Module)",
)
@click.option(
    "--workspace-api-version",
    default="opentofu.m.upbound.io/v1beta1",
    show_default=True,
    help="apiVersion of the Workspace resource in the generated Composition",
)
@click.option(
    "--function-go-templating",
    default="function-go-templating",
    show_default=True,
    help="Name of the function-go-templating Function installed on the cluster",
)
@click.option(
    "--function-auto-ready",
    default="function-auto-ready",
    show_default=True,
    help="Name of the function-auto-ready Function installed on the cluster",
)
@click.option(
    "--function-patch-and-transform",
    default="function-patch-and-transform",
    show_default=True,
    help="Name of the function-patch-and-transform Function installed on the cluster",
)
@click.option(
    "--scope",
    default="Namespaced",
    show_default=True,
    type=click.Choice(["Namespaced", "Cluster"], case_sensitive=True),
    help="Scope of the XRD (Namespaced or Cluster)",
)
@click.option(
    "--auto-ready/--no-auto-ready",
    default=True,
    show_default=True,
    help="Add a function-auto-ready step to the pipeline",
)
@click.option(
    "--extra-var",
    "extra_vars",
    multiple=True,
    help=(
        "Add a field to the XRD spec not in the Terraform module. "
        "Format: name:type:description or name:type:description:default. "
        "Example: --extra-var 'target_region:string:AWS region'"
    ),
)
@click.option(
    "--secret-name-format",
    default="",
    help=(
        "Format string for writeConnectionSecretToRef.name. "
        "Supported placeholders: {module}, {namespace}, {name}, {<spec_field>}."
    ),
)
@click.option(
    "--provider-config-format",
    default="",
    help=(
        "Format string for providerConfigRef.name. When set, the name is computed "
        "dynamically instead of reading spec.providerConfig from the claim. "
        "Supported placeholders: {module}, {namespace}, {name}, {<spec_field>}."
    ),
)
def infra(
    module_url: str,
    output_dir: str,
    group: str,
    provider_config: str,
    version: str,
    kind: str,
    provider_config_kind: str,
    composition_update_policy: str,
    workspace_source: str,
    workspace_api_version: str,
    function_go_templating: str,
    function_auto_ready: str,
    function_patch_and_transform: str,
    scope: str,
    auto_ready: bool,
    extra_vars: tuple[str, ...],
    secret_name_format: str,
    provider_config_format: str,
) -> None:
    """Generate XRD + Composition from a Terraform module Git URL."""
    settings = Settings(
        module_url=module_url,
        output_dir=output_dir,
        group=group,
        provider_config=provider_config,
        provider_config_kind=provider_config_kind,
        composition_update_policy=composition_update_policy,
        workspace_source=workspace_source,
        workspace_api_version=workspace_api_version,
        function_go_templating=function_go_templating,
        function_auto_ready=function_auto_ready,
        function_patch_and_transform=function_patch_and_transform,
        scope=scope,
        auto_ready=auto_ready,
        version=version,
        kind=kind,
        extra_vars=list(extra_vars),
        secret_name_format=secret_name_format,
        provider_config_format=provider_config_format,
    )

    module_name = module_name_from_url(module_url)
    resolved_kind = kind or module_name_to_kind(module_name)

    LOGGER.info("Cloning %s ...", module_url)
    tmpdir_root, module_path = clone_module(module_url)
    try:
        variables = parse_variables(module_path)
        outputs = parse_outputs(module_path)
    finally:
        shutil.rmtree(tmpdir_root)

    LOGGER.info(
        "Found %d variables, %d outputs → kind: %s",
        len(variables),
        len(outputs),
        resolved_kind,
    )

    xrd = generate_xrd(variables, outputs, resolved_kind, settings)
    composition, literal_cls, literal_repr = generate_composition(
        variables, outputs, resolved_kind, module_url, settings
    )

    yaml.add_representer(literal_cls, literal_repr)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    xrd_path = output_path / "xrd.yaml"
    comp_path = output_path / "composition.yaml"

    header = f"# Generated by tf2crossplane infra from {module_url}\n# Do not edit manually — re-run tf2crossplane infra to regenerate.\n"

    with open(xrd_path, "w") as f:
        f.write(header)
        yaml.dump(xrd, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    with open(comp_path, "w") as f:
        f.write(header)
        yaml.dump(
            composition,
            f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )

    LOGGER.info("Written: %s", xrd_path)
    LOGGER.info("Written: %s", comp_path)


@cli.command("stack")
@click.option(
    "--file",
    "-f",
    "stack_file",
    type=click.Path(exists=True, path_type=Path),
    help="Path to a *.stack.yaml definition file",
)
@click.option("--name", default="", help="Stack kind name (CamelCase, e.g. StackVM)")
@click.option(
    "--xrd-dir",
    default=".",
    show_default=True,
    help="Directory containing the Infra XRD YAML files to read",
)
@click.option(
    "--output-dir",
    default=".",
    show_default=True,
    help="Output directory for generated YAML files",
)
@click.option(
    "--group",
    default="example.crossplane.io",
    show_default=True,
    help="Crossplane API group",
)
@click.option("--version", default="v1alpha1", show_default=True, help="API version")
@click.option(
    "--resource",
    "resources",
    multiple=True,
    help=(
        "Infra resource to include. Format: name:xrd-plural (e.g. kms:xkmskeys). "
        "Can be repeated."
    ),
)
@click.option(
    "--wire",
    "wires",
    multiple=True,
    help=(
        "Output wiring between resources. "
        "Format: 'source.outputs.field -> target.field' "
        "(e.g. 'kms.outputs.key_id -> ec2.kms_key_id'). "
        "Can be repeated."
    ),
)
@click.option(
    "--function-go-templating",
    default="function-go-templating",
    show_default=True,
    help="Name of the function-go-templating Function installed on the cluster",
)
@click.option(
    "--function-auto-ready",
    default="function-auto-ready",
    show_default=True,
    help="Name of the function-auto-ready Function installed on the cluster",
)
def stack(
    stack_file: Path | None,
    name: str,
    xrd_dir: str,
    output_dir: str,
    group: str,
    version: str,
    resources: tuple[str, ...],
    wires: tuple[str, ...],
    function_go_templating: str,
    function_auto_ready: str,
) -> None:
    """Generate XRD + Composition for a Stack (Composition of Compositions).

    Input can be a *.stack.yaml file (--file) or CLI flags (--name, --resource, --wire).
    Each resource in the Stack references an existing Infra XRD read from --xrd-dir.
    """
    from tf2crossplane.stack.command import run_stack

    run_stack(
        stack_file=stack_file,
        name=name,
        xrd_dir=Path(xrd_dir),
        output_dir=Path(output_dir),
        group=group,
        version=version,
        resources=list(resources),
        wires=list(wires),
        function_go_templating=function_go_templating,
        function_auto_ready=function_auto_ready,
    )
