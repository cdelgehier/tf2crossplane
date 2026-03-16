from tf2crossplane.composition import _format_to_go_printf, generate_composition
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


def test_secret_name_format_absent_by_default(s3_variables, s3_outputs):
    """Without --secret-name-format, writeConnectionSecretToRef must not appear in the template."""
    composition, _, _ = generate_composition(
        s3_variables, s3_outputs, "S3Bucket", _settings().module_url, _settings()
    )
    template = composition["spec"]["pipeline"][0]["input"]["inline"]["template"]

    assert "writeConnectionSecretToRef" not in template


def test_secret_name_format_generates_printf(s3_variables, s3_outputs):
    """--secret-name-format generates a writeConnectionSecretToRef block with a Go printf expression."""
    settings = Settings(
        module_url="git::https://github.com/terraform-aws-modules/terraform-aws-s3-bucket.git?ref=v4.6.0",
        output_dir=".",
        group="example.crossplane.io",
        provider_config="my-provider-config",
        secret_name_format="tf-outputs-{module}-{namespace}-{name}",
    )
    composition, _, _ = generate_composition(
        s3_variables, s3_outputs, "S3Bucket", settings.module_url, settings
    )
    template = composition["spec"]["pipeline"][0]["input"]["inline"]["template"]

    assert "writeConnectionSecretToRef" in template
    assert 'printf "tf-outputs-terraform-aws-s3-bucket-%s-%s"' in template
    assert ".observed.composite.resource.metadata.namespace" in template
    assert ".observed.composite.resource.metadata.name" in template


def test_secret_name_format_spec_field(s3_variables, s3_outputs):
    """Unknown placeholders in --secret-name-format map to spec fields."""
    settings = Settings(
        module_url="git::https://github.com/terraform-aws-modules/terraform-aws-s3-bucket.git?ref=v4.6.0",
        output_dir=".",
        group="example.crossplane.io",
        provider_config="my-provider-config",
        secret_name_format="secret-{name}-{region}",
    )
    composition, _, _ = generate_composition(
        s3_variables, s3_outputs, "S3Bucket", settings.module_url, settings
    )
    template = composition["spec"]["pipeline"][0]["input"]["inline"]["template"]

    assert ".observed.composite.resource.spec.region" in template


def test_format_to_go_printf_no_placeholders():
    assert _format_to_go_printf("my-static-secret", "mod") == '"my-static-secret"'


def test_format_to_go_printf_module_inline():
    result = _format_to_go_printf("prefix-{module}-suffix", "terraform-aws-s3-bucket")
    assert result == '"prefix-terraform-aws-s3-bucket-suffix"'


def test_format_to_go_printf_metadata():
    result = _format_to_go_printf("{namespace}-{name}", "mod")
    assert 'printf "%s-%s"' in result
    assert ".observed.composite.resource.metadata.namespace" in result
    assert ".observed.composite.resource.metadata.name" in result


def test_format_to_go_printf_spec_field():
    result = _format_to_go_printf("out-{region}", "mod")
    assert ".observed.composite.resource.spec.region" in result


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
