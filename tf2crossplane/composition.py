"""
Generate a Crossplane Composition manifest from parsed Terraform module data.

A Composition is the implementation side of a Crossplane XRD: it describes
*how* to fulfil a claim. Here, the strategy is always the same:

  Claim (spec fields)
    → function-go-templating (pipeline step)
      → Workspace (provider-opentofu)
        → Terraform module (remote Git source)

The generated Composition contains a single pipeline step that uses
function-go-templating to render a Workspace resource inline. The Go template
reads every field from the composite resource spec (.observed.composite.resource.spec)
and passes them as Terraform variables via the Workspace varmap.

Output files (written by main.py):
  <output_dir>/composition.yaml   ← this module
  <output_dir>/xrd.yaml           ← xrd.py
"""

from typing import Any

from tf2crossplane.parser import tf_type_to_go_expr
from tf2crossplane.settings import Settings


class _Literal(str):
    """
    Subclass of str used as a marker for PyYAML literal block style (|).

    Without this, PyYAML serialises the Go template as a single line with
    escaped newlines:

        template: "apiVersion: opentofu.m.upbound.io/v1beta1\\nkind: Workspace\\n..."

    That is both unreadable and invalid — function-go-templating expects a
    real multi-line YAML block. Wrapping the template string in _Literal tells
    the custom representer below to emit it with the | block scalar style:

        template: |
          apiVersion: opentofu.m.upbound.io/v1beta1
          kind: Workspace
          ...

    PyYAML has no global option to force block style per content type
    (unlike ruamel.yaml), so the _Literal marker + representer pair is the
    standard workaround.
    """


def _literal_representer(dumper, data):
    """
    PyYAML representer that forces block scalar style (|) for _Literal strings.

    Must be registered with yaml.add_representer(_Literal, _literal_representer)
    before calling yaml.dump(), otherwise _Literal instances fall back to the
    default str representer and the block style is lost.
    """
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")


def _build_template(variables: dict[str, Any], module_url: str) -> str:
    """
    Build the Go template string that function-go-templating will render at sync time.

    The output is a YAML string representing a provider-opentofu Workspace resource.
    Each Terraform variable is mapped to its value from the composite resource spec
    using the appropriate Go template pipe filter:
      - string  → | quote   (wraps the value in double quotes for HCL)
      - number  → direct    (HCL numbers need no quoting)
      - bool    → direct    (HCL booleans need no quoting)
      - list / map / object → | toJson  (HCL complex types are passed as JSON strings)

    The providerConfig field drives which ProviderConfig the Workspace will use,
    allowing each claim to target a different AWS account / region without changing
    the Composition itself.
    """
    varmap_lines = []
    for var_name, var_def in variables.items():
        expr = tf_type_to_go_expr(var_name, var_def.get("type"))
        varmap_lines.append(f"      {var_name}: {expr}")

    varmap_block = "\n".join(varmap_lines)

    return f"""\
apiVersion: opentofu.m.upbound.io/v1beta1
kind: Workspace
metadata:
  name: {{{{ .observed.composite.resource.metadata.name }}}}
  annotations:
    gotemplating.fn.crossplane.io/composition-resource-name: workspace
spec:
  providerConfigRef:
    name: {{{{ .observed.composite.resource.spec.providerConfig }}}}
  forProvider:
    source: Remote
    module: {module_url}
    varmap:
{varmap_block}
"""


def generate_composition(
    variables: dict[str, Any],
    outputs: dict[str, Any],
    kind: str,
    module_url: str,
    settings: Settings,
) -> tuple[dict, type, Any]:
    """
    Generate a Composition manifest dict from parsed Terraform module data.

    The Composition references the composite type produced by generate_xrd() and
    wires every claim field through to the Terraform module via a Workspace resource.

    Args:
        variables:  Output of parse_variables() — {var_name: {type, description, default}}.
        outputs:    Output of parse_outputs()   — {out_name: {description}}.
        kind:       Kubernetes kind for the claim (e.g. "S3Bucket").
        module_url: Git URL of the Terraform module (passed verbatim to Workspace.forProvider.module).
        settings:   Global generation settings (group, version, providerConfig…).

    Returns:
        A 3-tuple (manifest_dict, _Literal, _literal_representer).
        The caller (main.py) must register the representer with yaml.add_representer()
        before calling yaml.dump(), otherwise the Go template block will be mangled.
    """
    composite_kind = "X" + kind
    plural = kind.lower() + "s"
    composite_plural = "x" + plural

    # _Literal marks the template string so PyYAML renders it with | block style
    template = _Literal(_build_template(variables, module_url))

    composition = {
        "apiVersion": "apiextensions.crossplane.io/v1",
        "kind": "Composition",
        "metadata": {
            "name": f"{composite_plural}.{settings.group}",
        },
        "spec": {
            "compositeTypeRef": {
                "apiVersion": f"{settings.group}/{settings.version}",
                "kind": composite_kind,
            },
            "mode": "Pipeline",
            "pipeline": [
                {
                    "step": "render",
                    "functionRef": {"name": "function-go-templating"},
                    "input": {
                        "apiVersion": "gotemplating.fn.crossplane.io/v1beta1",
                        "kind": "GoTemplate",
                        "source": "Inline",
                        "inline": {"template": template},
                    },
                }
            ],
        },
    }
    return composition, _Literal, _literal_representer
