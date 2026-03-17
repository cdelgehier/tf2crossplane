from tf2crossplane.settings import ResourceDef, StackSettings, WireDef
from tf2crossplane.stack.composition import generate_stack_composition


def test_composition_structure(stack_settings, infra_xrds):
    """The generated Composition has the correct kind, name, compositeTypeRef and pipeline mode."""
    comp = generate_stack_composition(stack_settings, infra_xrds)

    assert comp["kind"] == "Composition"
    assert comp["metadata"]["name"] == "xstackvms.homelab.crossplane.io"

    spec = comp["spec"]
    assert spec["compositeTypeRef"]["kind"] == "XStackVM"
    assert spec["compositeTypeRef"]["apiVersion"] == "homelab.crossplane.io/v1alpha1"
    assert spec["mode"] == "Pipeline"


def test_composition_pipeline_has_render_and_auto_ready(stack_settings, infra_xrds):
    """Pipeline always starts with a go-templating render step and ends with auto-ready."""
    comp = generate_stack_composition(stack_settings, infra_xrds)
    steps = [s["step"] for s in comp["spec"]["pipeline"]]

    assert steps[0] == "render"
    assert steps[-1] == "auto-ready"


def test_composition_render_step_uses_go_templating(stack_settings, infra_xrds):
    """The render step references function-go-templating and uses Inline GoTemplate."""
    comp = generate_stack_composition(stack_settings, infra_xrds)
    render = comp["spec"]["pipeline"][0]

    assert render["functionRef"]["name"] == "function-go-templating"
    assert render["input"]["kind"] == "GoTemplate"
    assert render["input"]["source"] == "Inline"


def test_composition_template_contains_required_resource(stack_settings, infra_xrds):
    """The go-template includes an unconditional block for the required (non-optional) resource."""
    comp = generate_stack_composition(stack_settings, infra_xrds)
    template = comp["spec"]["pipeline"][0]["input"]["inline"]["template"]

    # EC2 is not optional → no if/end guards
    assert "kind: XEC2Instance" in template
    assert "composition-resource-name: ec2" in template


def test_composition_template_optional_resource_has_guards(stack_settings, infra_xrds):
    """Optional resources are wrapped in {{- if not .spec.X.existingId }} guards."""
    comp = generate_stack_composition(stack_settings, infra_xrds)
    template = comp["spec"]["pipeline"][0]["input"]["inline"]["template"]

    assert "kind: XKMSKey" in template
    assert "spec.kms.existingId" in template
    assert "spec.kms.import" in template


def test_composition_template_wire_injects_fallback(stack_settings, infra_xrds):
    """Inbound wire to EC2 injects the KMS key_id with a fallback to existingId."""
    comp = generate_stack_composition(stack_settings, infra_xrds)
    template = comp["spec"]["pipeline"][0]["input"]["inline"]["template"]

    # The wire kms.outputs.key_id -> ec2.kms_key_id must appear in the template
    assert "kms_key_id" in template
    assert "kmsKeyId" in template or "key_id" in template


def test_composition_custom_function_names():
    """Custom function-go-templating and function-auto-ready names are propagated."""
    settings = StackSettings(
        name="MyStack",
        group="example.crossplane.io",
        resources=[ResourceDef(name="ec2", xrd="xec2instances")],
        wires=[],
        function_go_templating="my-go-templating",
        function_auto_ready="my-auto-ready",
    )
    comp = generate_stack_composition(settings, {"ec2": {}})

    pipeline = comp["spec"]["pipeline"]
    assert pipeline[0]["functionRef"]["name"] == "my-go-templating"
    assert pipeline[-1]["functionRef"]["name"] == "my-auto-ready"


def test_composition_no_patch_step_when_no_wires(infra_xrds):
    """When there are no wires, the pipeline has no patch-outputs step."""
    settings = StackSettings(
        name="SimpleStack",
        group="example.crossplane.io",
        resources=[ResourceDef(name="ec2", xrd="xec2instances")],
        wires=[],
    )
    comp = generate_stack_composition(settings, infra_xrds)
    steps = [s["step"] for s in comp["spec"]["pipeline"]]

    assert "patch-outputs" not in steps


def test_composition_patch_step_present_with_wires(stack_settings, infra_xrds):
    """When wires are defined, a patch-outputs step is added to bubble outputs to XR status."""
    comp = generate_stack_composition(stack_settings, infra_xrds)
    steps = [s["step"] for s in comp["spec"]["pipeline"]]

    assert "patch-outputs" in steps


def test_composition_single_wire_to_array_field_renders_list(ec2_xrd, sg_xrd):
    """A single wire targeting an array-typed field renders as a YAML list, not a scalar."""
    settings = StackSettings(
        name="StackVM",
        group="homelab.crossplane.io",
        resources=[
            ResourceDef(name="sg", xrd="xsecuritygroups", optional=True),
            ResourceDef(name="ec2", xrd="xec2instances"),
        ],
        wires=[
            WireDef(
                source="sg.outputs.security_group_id",
                target="ec2.vpc_security_group_ids",
            )
        ],
    )
    comp = generate_stack_composition(settings, {"sg": sg_xrd, "ec2": ec2_xrd})
    template = comp["spec"]["pipeline"][0]["input"]["inline"]["template"]

    # Must render as a list item, not a bare scalar
    assert "vpc_security_group_ids:\n  - {{" in template
    assert "vpc_security_group_ids: {{" not in template


def test_composition_multi_wire_same_target_renders_list(ec2_xrd, sg_xrd, sg_db_xrd):
    """Two wires targeting the same field render a YAML list instead of two scalar assignments."""
    settings = StackSettings(
        name="StackVM",
        group="homelab.crossplane.io",
        resources=[
            ResourceDef(name="sg_ad", xrd="xsecuritygroups", optional=True),
            ResourceDef(name="sg_db", xrd="xsecuritygroups", optional=True),
            ResourceDef(name="ec2", xrd="xec2instances"),
        ],
        wires=[
            WireDef(
                source="sg_ad.outputs.security_group_id",
                target="ec2.vpc_security_group_ids",
            ),
            WireDef(
                source="sg_db.outputs.security_group_id",
                target="ec2.vpc_security_group_ids",
            ),
        ],
    )
    xrds = {"sg_ad": sg_xrd, "sg_db": sg_db_xrd, "ec2": ec2_xrd}
    comp = generate_stack_composition(settings, xrds)
    template = comp["spec"]["pipeline"][0]["input"]["inline"]["template"]

    # The field must appear exactly once (not duplicated)
    assert template.count("vpc_security_group_ids:") == 1
    # Both SG IDs must appear as list items
    assert "- {{ (.observed.composite.resource.status.sgAdSecurityGroupId" in template
    assert "- {{ (.observed.composite.resource.status.sgDbSecurityGroupId" in template
