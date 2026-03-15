from tf2crossplane.settings import Settings
from tf2crossplane.xrd import generate_xrd


def test_xrd_structure(s3_variables, s3_outputs):
    """The generated XRD has the correct kind, plural name, group, composite kind, and claim kind."""
    settings = Settings(
        module_url="git::https://example.com/module.git",
        output_dir=".",
        group="example.crossplane.io",
        provider_config="my-provider-config",
    )
    xrd = generate_xrd(s3_variables, s3_outputs, "S3Bucket", settings)

    assert xrd["kind"] == "CompositeResourceDefinition"
    assert xrd["metadata"]["name"] == "xs3buckets.example.crossplane.io"

    spec = xrd["spec"]
    assert spec["group"] == "example.crossplane.io"
    assert spec["names"]["kind"] == "XS3Bucket"
    assert "claimNames" not in spec

    version = spec["versions"][0]
    properties = version["schema"]["openAPIV3Schema"]["properties"]["spec"][
        "properties"
    ]
    required = version["schema"]["openAPIV3Schema"]["properties"]["spec"]["required"]

    # providerConfig always present and required
    assert "providerConfig" in properties
    assert "providerConfig" in required

    # variable without default → required
    assert "bucket" in required

    # variable with default → not required
    assert "force_destroy" not in required
    assert "tags" not in required

    # correct types
    assert properties["force_destroy"]["type"] == "boolean"
    assert properties["tags"]["type"] == "object"
    assert properties["allowed_cidrs"]["type"] == "array"


def test_xrd_no_meta_account_meta_region(s3_variables, s3_outputs):
    """meta_account and meta_region (CMA-specific routing fields) must not appear in the XRD schema."""
    settings = Settings(
        module_url="git::https://example.com/module.git",
        output_dir=".",
        group="example.crossplane.io",
        provider_config="my-provider-config",
    )
    xrd = generate_xrd(s3_variables, s3_outputs, "S3Bucket", settings)
    properties = xrd["spec"]["versions"][0]["schema"]["openAPIV3Schema"]["properties"][
        "spec"
    ]["properties"]

    assert "meta_account" not in properties
    assert "meta_region" not in properties


def _settings():
    return Settings(
        module_url="git::https://example.com/module.git",
        output_dir=".",
        group="example.crossplane.io",
        provider_config="my-provider-config",
    )


def test_xrd_ec2_required_fields(ec2_variables, ec2_outputs):
    """Variables without a default are required; variables with a default are optional in the XRD schema."""
    xrd = generate_xrd(ec2_variables, ec2_outputs, "Ec2Instance", _settings())
    spec = xrd["spec"]["versions"][0]["schema"]["openAPIV3Schema"]["properties"]["spec"]
    required = spec["required"]

    assert "name" in required
    assert "ami" in required
    # variables with defaults are not required
    assert "instance_type" not in required
    assert "instance_count" not in required
    assert "monitoring" not in required


def test_xrd_ec2_types(ec2_variables, ec2_outputs):
    """Terraform types are mapped to the correct OpenAPI types in the XRD schema."""
    xrd = generate_xrd(ec2_variables, ec2_outputs, "Ec2Instance", _settings())
    props = xrd["spec"]["versions"][0]["schema"]["openAPIV3Schema"]["properties"][
        "spec"
    ]["properties"]

    assert props["instance_count"]["type"] == "number"
    assert props["monitoring"]["type"] == "boolean"
    assert props["vpc_security_group_ids"]["type"] == "array"
    assert props["tags"]["type"] == "object"


def test_xrd_asg_optional_types(asg_variables, asg_outputs):
    """optional(type) and optional(type, default) are unwrapped to their inner type in the XRD schema."""
    xrd = generate_xrd(asg_variables, asg_outputs, "Asg", _settings())
    props = xrd["spec"]["versions"][0]["schema"]["openAPIV3Schema"]["properties"][
        "spec"
    ]["properties"]

    # optional(number, null) → number
    assert props["desired_capacity"]["type"] == "number"
    # nested object → preserve-unknown-fields
    assert props["mixed_instances_policy"]["type"] == "object"
    assert (
        props["mixed_instances_policy"].get("x-kubernetes-preserve-unknown-fields")
        is True
    )


def test_xrd_alb_required_fields(alb_variables, alb_outputs):
    """name, vpc_id and subnets have no default and must be required; load_balancer_type has a default and must not."""
    xrd = generate_xrd(
        alb_variables, alb_outputs, "ApplicationLoadBalancer", _settings()
    )
    spec = xrd["spec"]["versions"][0]["schema"]["openAPIV3Schema"]["properties"]["spec"]
    required = spec["required"]

    assert "name" in required
    assert "vpc_id" in required
    assert "subnets" in required
    assert "load_balancer_type" not in required
    assert "internal" not in required


def test_xrd_alb_types(alb_variables, alb_outputs):
    """list(string), map(string), and ${any} are mapped to the correct OpenAPI schemas."""
    xrd = generate_xrd(
        alb_variables, alb_outputs, "ApplicationLoadBalancer", _settings()
    )
    props = xrd["spec"]["versions"][0]["schema"]["openAPIV3Schema"]["properties"][
        "spec"
    ]["properties"]

    assert props["subnets"]["type"] == "array"
    assert props["subnets"]["items"] == {"type": "string"}
    assert props["security_groups"]["type"] == "array"
    assert props["access_logs"]["type"] == "object"
    assert "additionalProperties" in props["access_logs"]
    # ${any} → open object
    assert props["listeners"]["type"] == "object"
    assert props["listeners"].get("x-kubernetes-preserve-unknown-fields") is True
    assert props["target_groups"]["type"] == "object"
    assert props["target_groups"].get("x-kubernetes-preserve-unknown-fields") is True
