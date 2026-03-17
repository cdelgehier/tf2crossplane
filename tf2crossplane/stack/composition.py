"""Generate the Composition for a Stack (Composition of Compositions)."""

from tf2crossplane.settings import ResourceDef, StackSettings, WireDef
from tf2crossplane.stack.reader import xrd_group, xrd_kind
from tf2crossplane.stack.xrd import _composite_kind, _plural, _to_camel


def _resource_block(
    resource: ResourceDef,
    infra_xrd: dict,
    wires_to: list[WireDef],
    group: str,
    version: str,
) -> str:
    """
    Render the go-template block for one resource.

    Handles three modes for optional resources:
    - existingId: skip creation, forward the ID to the XR status
    - import: create XR with spec.import set
    - (default): create XR normally

    wires_to: wires whose target starts with this resource name (inbound wires).
    """
    res_group = xrd_group(infra_xrd) or group
    res_kind = xrd_kind(infra_xrd)
    res_name = resource.name

    # Build inbound wire assignments (fields this resource receives from the XR status).
    # Multiple wires targeting the same field are rendered as a YAML list.
    by_target: dict[str, list[tuple[str, str]]] = {}
    for wire in wires_to:
        target_field = (
            wire.target.split(".", 1)[1] if "." in wire.target else wire.target
        )
        source_parts = wire.source.split(".")
        status_key = (
            _to_camel(f"{source_parts[0]}_{source_parts[2]}")
            if len(source_parts) >= 3
            else wire.source
        )
        fallback = wire.fallback or f"spec.{source_parts[0]}.existingId"
        by_target.setdefault(target_field, []).append((status_key, fallback))

    inbound_lines = []
    for target_field, entries in by_target.items():
        if len(entries) == 1:
            status_key, fallback = entries[0]
            inbound_lines.append(
                f"  {target_field}: {{{{ (.observed.composite.resource.status.{status_key} | default .observed.composite.resource.{fallback}) }}}}"
            )
        else:
            inbound_lines.append(f"  {target_field}:")
            for status_key, fallback in entries:
                inbound_lines.append(
                    f"  - {{{{ (.observed.composite.resource.status.{status_key} | default .observed.composite.resource.{fallback}) }}}}"
                )

    inbound = ("\n" + "\n".join(inbound_lines)) if inbound_lines else ""

    if resource.optional:
        block = f"""\
{{{{- if and (not .observed.composite.resource.spec.{res_name}.existingId) (not .observed.composite.resource.spec.{res_name}.import) }}}}
---
apiVersion: {res_group}/{version}
kind: {res_kind}
metadata:
  name: {{{{ .observed.composite.resource.metadata.name }}}}-{res_name}
  namespace: {{{{ .observed.composite.resource.metadata.namespace }}}}
  annotations:
    gotemplating.fn.crossplane.io/composition-resource-name: {res_name}
spec:
  providerConfig: {{{{ .observed.composite.resource.spec.providerConfig }}}}{inbound}
{{{{- else if .observed.composite.resource.spec.{res_name}.import }}}}
---
apiVersion: {res_group}/{version}
kind: {res_kind}
metadata:
  name: {{{{ .observed.composite.resource.metadata.name }}}}-{res_name}
  namespace: {{{{ .observed.composite.resource.metadata.namespace }}}}
  annotations:
    gotemplating.fn.crossplane.io/composition-resource-name: {res_name}
spec:
  providerConfig: {{{{ .observed.composite.resource.spec.providerConfig }}}}
  import: {{{{ .observed.composite.resource.spec.{res_name}.import }}}}
{{{{- end }}}}"""
    else:
        block = f"""\
---
apiVersion: {res_group}/{version}
kind: {res_kind}
metadata:
  name: {{{{ .observed.composite.resource.metadata.name }}}}-{res_name}
  namespace: {{{{ .observed.composite.resource.metadata.namespace }}}}
  annotations:
    gotemplating.fn.crossplane.io/composition-resource-name: {res_name}
spec:
  providerConfig: {{{{ .observed.composite.resource.spec.providerConfig }}}}{inbound}"""

    return block


def generate_stack_composition(
    settings: StackSettings,
    infra_xrds: dict[str, dict],
) -> dict:
    """
    Build the Composition manifest for a Stack.

    Parameters
    ----------
    settings:
        StackSettings with name, group, version, resources, wires.
    infra_xrds:
        Mapping of resource logical name → loaded XRD dict.
    """
    plural = _plural(settings.name)
    composite_kind = _composite_kind(settings.name)

    # Build the go-template: one block per resource + ToCompositeFieldPath patches
    template_parts = []

    for resource in settings.resources:
        infra_xrd = infra_xrds.get(resource.name, {})

        # Wires that feed INTO this resource (target starts with resource.name)
        wires_to = [
            w for w in settings.wires if w.target.split(".")[0] == resource.name
        ]

        block = _resource_block(
            resource,
            infra_xrd,
            wires_to,
            settings.group,
            settings.version,
        )
        template_parts.append(block)

    # ToCompositeFieldPath patches: each wire source needs a patch step to bubble
    # the output up to the XR status so downstream resources can read it.
    patches = []
    for wire in settings.wires:
        source_parts = wire.source.split(".")
        if len(source_parts) < 3:
            continue
        res_name, _, field = source_parts[0], source_parts[1], source_parts[2]
        status_key = _to_camel(f"{res_name}_{field}")
        patches.append(
            {
                "type": "ToCompositeFieldPath",
                "fromFieldPath": f"status.atProvider.outputs.{field}",
                "toFieldPath": f"status.{status_key}",
                "transforms": [],
                # patch applies to the composed resource named res_name
                "policy": {"fromFieldPath": "Optional"},
            }
        )

    full_template = "\n".join(template_parts)

    pipeline: list = [
        {
            "step": "render",
            "functionRef": {"name": settings.function_go_templating},
            "input": {
                "apiVersion": "gotemplating.fn.crossplane.io/v1beta1",
                "kind": "GoTemplate",
                "source": "Inline",
                "inline": {"template": full_template},
            },
        }
    ]

    if patches:
        pipeline.append(
            {
                "step": "patch-outputs",
                "functionRef": {"name": "function-patch-and-transform"},
                "input": {
                    "apiVersion": "pt.fn.crossplane.io/v1beta1",
                    "kind": "Resources",
                    "resources": [
                        {
                            "name": wire.source.split(".")[0],
                            "patches": [
                                {
                                    "type": "ToCompositeFieldPath",
                                    "fromFieldPath": f"status.atProvider.outputs.{wire.source.split('.')[2]}",
                                    "toFieldPath": f"status.{_to_camel(wire.source.split('.')[0] + '_' + wire.source.split('.')[2])}",
                                    "policy": {"fromFieldPath": "Optional"},
                                }
                            ],
                        }
                        for wire in settings.wires
                        if len(wire.source.split(".")) >= 3
                    ],
                },
            }
        )

    pipeline.append(
        {
            "step": "auto-ready",
            "functionRef": {"name": settings.function_auto_ready},
        }
    )

    return {
        "apiVersion": "apiextensions.crossplane.io/v1",
        "kind": "Composition",
        "metadata": {
            "name": f"{plural}.{settings.group}",
        },
        "spec": {
            "compositeTypeRef": {
                "apiVersion": f"{settings.group}/{settings.version}",
                "kind": composite_kind,
            },
            "mode": "Pipeline",
            "pipeline": pipeline,
        },
    }
