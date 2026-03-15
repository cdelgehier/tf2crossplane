from tf2crossplane.composition import generate_composition
from tf2crossplane.settings import Settings


def _settings():
    return Settings(
        module_url="git::https://github.com/terraform-aws-modules/terraform-aws-s3-bucket.git?ref=v4.6.0",
        output_dir=".",
        group="example.crossplane.io",
        provider_config="my-provider-config",
    )


def test_composition_structure(s3_variables, s3_outputs):
    """The generated Composition has the correct kind, name, compositeTypeRef, and pipeline mode."""
    composition, _, _ = generate_composition(
        s3_variables, s3_outputs, "S3Bucket", _settings().module_url, _settings()
    )

    assert composition["kind"] == "Composition"
    assert composition["metadata"]["name"] == "xs3buckets.example.crossplane.io"

    spec = composition["spec"]
    assert spec["compositeTypeRef"]["kind"] == "XS3Bucket"
    assert spec["mode"] == "Pipeline"

    step = spec["pipeline"][0]
    assert step["functionRef"]["name"] == "function-go-templating"
    assert step["input"]["kind"] == "GoTemplate"


def test_composition_template_contains_variables(s3_variables, s3_outputs):
    """All module variables appear in the Go template with the correct pipe filter for their type."""
    composition, _, _ = generate_composition(
        s3_variables, s3_outputs, "S3Bucket", _settings().module_url, _settings()
    )
    template = composition["spec"]["pipeline"][0]["input"]["inline"]["template"]

    assert "bucket" in template
    assert "force_destroy" in template
    assert "tags" in template
    # strings → quote, booleans → direct, maps → toJson
    assert "| quote" in template
    assert "| toJson" in template


def test_composition_uses_provider_config_from_claim(s3_variables, s3_outputs):
    """The Go template reads providerConfig from the claim spec, not from a hard-coded value."""
    composition, _, _ = generate_composition(
        s3_variables, s3_outputs, "S3Bucket", _settings().module_url, _settings()
    )
    template = composition["spec"]["pipeline"][0]["input"]["inline"]["template"]

    assert ".observed.composite.resource.spec.providerConfig" in template


def test_composition_no_meta_account_meta_region(s3_variables, s3_outputs):
    """meta_account and meta_region (CMA-specific routing fields) must not appear in the template."""
    composition, _, _ = generate_composition(
        s3_variables, s3_outputs, "S3Bucket", _settings().module_url, _settings()
    )
    template = composition["spec"]["pipeline"][0]["input"]["inline"]["template"]

    assert "meta_account" not in template
    assert "meta_region" not in template


def test_composition_alb_any_type_uses_tojson(alb_variables, alb_outputs):
    """${any}-typed variables (listeners, target_groups) must use | toJson in the Go template."""
    url = "git::https://github.com/terraform-aws-modules/terraform-aws-alb.git?ref=v9.13.0"
    settings = Settings(
        module_url=url,
        output_dir=".",
        group="platform.example.io",
        provider_config="aws-prod",
    )
    composition, _, _ = generate_composition(
        alb_variables, alb_outputs, "ApplicationLoadBalancer", url, settings
    )
    template = composition["spec"]["pipeline"][0]["input"]["inline"]["template"]

    assert '"listeners" | toJson' in template
    assert '"target_groups" | toJson' in template
    # plain string → quote
    assert '"name" | quote' in template
    # bool → direct (no pipe)
    assert '"internal" }}' in template
