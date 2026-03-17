import pytest

from tf2crossplane.settings import ResourceDef, StackSettings
from tf2crossplane.stack.xrd import _plural, _to_camel, generate_stack_xrd


@pytest.mark.parametrize(
    "kind,expected",
    [
        ("StackVM", "xstackvms"),
        ("StackS3", "xstacks3s"),
        ("MyStack", "xmystacks"),
    ],
)
def test_plural(kind, expected):
    assert _plural(kind) == expected


@pytest.mark.parametrize(
    "snake,expected",
    [
        ("key_id", "keyId"),
        ("kms_key_id", "kmsKeyId"),
        ("security_group_id", "securityGroupId"),
        ("key", "key"),
    ],
)
def test_to_camel(snake, expected):
    assert _to_camel(snake) == expected


def test_xrd_structure(stack_settings, infra_xrds):
    """The generated XRD has the correct apiVersion, kind, plural, group and composite name."""
    xrd = generate_stack_xrd(stack_settings, infra_xrds)

    assert xrd["apiVersion"] == "apiextensions.crossplane.io/v2"
    assert xrd["kind"] == "CompositeResourceDefinition"
    assert xrd["metadata"]["name"] == "xstackvms.homelab.crossplane.io"

    spec = xrd["spec"]
    assert spec["group"] == "homelab.crossplane.io"
    assert spec["scope"] == "Namespaced"
    assert spec["names"]["kind"] == "XStackVM"
    assert spec["names"]["plural"] == "xstackvms"
    assert "claimNames" not in spec
    assert spec["defaultCompositionRef"]["name"] == "xstackvms.homelab.crossplane.io"


def test_xrd_providerconfig_always_present(stack_settings, infra_xrds):
    """providerConfig is always present and required in the Stack XRD spec."""
    xrd = generate_stack_xrd(stack_settings, infra_xrds)
    props = xrd["spec"]["versions"][0]["schema"]["openAPIV3Schema"]["properties"][
        "spec"
    ]["properties"]
    required = xrd["spec"]["versions"][0]["schema"]["openAPIV3Schema"]["properties"][
        "spec"
    ]["required"]

    assert "providerConfig" in props
    assert "providerConfig" in required


def test_xrd_optional_resource_has_existingid_and_import(stack_settings, infra_xrds):
    """Optional resources expose existingId and import fields in the XRD."""
    xrd = generate_stack_xrd(stack_settings, infra_xrds)
    props = xrd["spec"]["versions"][0]["schema"]["openAPIV3Schema"]["properties"][
        "spec"
    ]["properties"]

    kms_props = props["kms"]["properties"]
    assert "existingId" in kms_props
    assert "import" in kms_props


def test_xrd_required_resource_no_existingid(stack_settings, infra_xrds):
    """Non-optional resources do not have existingId or import fields."""
    xrd = generate_stack_xrd(stack_settings, infra_xrds)
    props = xrd["spec"]["versions"][0]["schema"]["openAPIV3Schema"]["properties"][
        "spec"
    ]["properties"]

    ec2_props = props["ec2"]["properties"]
    assert "existingId" not in ec2_props
    assert "import" not in ec2_props


def test_xrd_expose_filters_fields(stack_settings, infra_xrds):
    """Only the fields listed in expose appear in the Stack XRD for that resource."""
    xrd = generate_stack_xrd(stack_settings, infra_xrds)
    props = xrd["spec"]["versions"][0]["schema"]["openAPIV3Schema"]["properties"][
        "spec"
    ]["properties"]

    kms_props = props["kms"]["properties"]
    # expose = ["description", "deletion_window_in_days"] — providerConfig excluded
    assert "description" in kms_props
    assert "deletion_window_in_days" in kms_props
    assert "providerConfig" not in kms_props


def test_xrd_status_outputs_from_wires(stack_settings, infra_xrds):
    """Wire sources generate status output fields on the XRD (camelCase)."""
    xrd = generate_stack_xrd(stack_settings, infra_xrds)
    schema = xrd["spec"]["versions"][0]["schema"]["openAPIV3Schema"]["properties"]

    assert "status" in schema
    assert "kmsKeyId" in schema["status"]["properties"]


def test_xrd_no_wires_no_status(infra_xrds):
    """When there are no wires the XRD has no status block."""
    settings = StackSettings(
        name="SimpleStack",
        group="example.crossplane.io",
        resources=[ResourceDef(name="ec2", xrd="xec2instances")],
        wires=[],
    )
    xrd = generate_stack_xrd(settings, infra_xrds)
    schema = xrd["spec"]["versions"][0]["schema"]["openAPIV3Schema"]["properties"]
    assert "status" not in schema
