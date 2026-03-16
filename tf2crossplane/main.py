import shutil
from pathlib import Path

import click
import yaml

from tf2crossplane.composition import generate_composition
from tf2crossplane.logger import LOGGER
from tf2crossplane.parser import (
    clone_module,
    module_name_from_url,
    module_name_to_kind,
    parse_outputs,
    parse_variables,
)
from tf2crossplane.settings import Settings
from tf2crossplane.xrd import generate_xrd


@click.command()
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
    "--workspace-api-version",
    default="opentofu.m.upbound.io/v1beta1",
    show_default=True,
    help="apiVersion of the Workspace resource in the generated Composition (e.g. opentofu.m.upbound.io/v1beta1)",
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
    help="Add a function-auto-ready step to the pipeline to propagate composed resource readiness to the composite",
)
def main(
    module_url: str,
    output_dir: str,
    group: str,
    provider_config: str,
    version: str,
    kind: str,
    provider_config_kind: str,
    composition_update_policy: str,
    workspace_api_version: str,
    function_go_templating: str,
    function_auto_ready: str,
    scope: str,
    auto_ready: bool,
) -> None:
    """Generate Crossplane XRD + Composition from a Terraform module Git URL."""

    # Bundle all generation parameters into a single object passed down to
    # generate_xrd() and generate_composition(), instead of threading each
    # individual value through every function signature.
    settings = Settings(
        module_url=module_url,
        output_dir=output_dir,
        group=group,
        provider_config=provider_config,
        provider_config_kind=provider_config_kind,
        composition_update_policy=composition_update_policy,
        workspace_api_version=workspace_api_version,
        function_go_templating=function_go_templating,
        function_auto_ready=function_auto_ready,
        scope=scope,
        auto_ready=auto_ready,
        version=version,
        kind=kind,
    )

    # Derive the Kubernetes kind from the module name (e.g. terraform-aws-s3-bucket → S3Bucket)
    # unless the user overrides it explicitly with --kind.
    module_name = module_name_from_url(module_url)
    resolved_kind = kind or module_name_to_kind(module_name)

    # Clone into a temp directory so we can parse variables.tf / outputs.tf
    # without polluting the working directory. The tmpdir is always deleted in
    # the finally block, even if parsing raises an exception.
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

    # Generate the two Crossplane manifests from the parsed module data.
    xrd = generate_xrd(variables, outputs, resolved_kind, settings)
    composition, literal_cls, literal_repr = generate_composition(
        variables, outputs, resolved_kind, module_url, settings
    )

    # Register the PyYAML custom representer so the Go template inside the
    # Composition is serialised with | block style instead of a single escaped line.
    # This must be done before the first yaml.dump() call.
    yaml.add_representer(literal_cls, literal_repr)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    xrd_path = output_path / "xrd.yaml"
    comp_path = output_path / "composition.yaml"

    header = f"# Generated by tf2crossplane from {module_url}\n# Do not edit manually — re-run tf2crossplane to regenerate.\n"

    # sort_keys=False preserves the insertion order of the dicts (apiVersion first,
    # then kind, metadata, spec…), which matches the conventional Kubernetes YAML layout.
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
