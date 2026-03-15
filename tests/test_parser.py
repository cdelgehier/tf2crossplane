from pathlib import Path
from unittest.mock import patch

import pytest

from tf2crossplane.parser import (
    clone_module,
    module_name_from_url,
    module_name_to_kind,
    tf_type_to_go_expr,
    tf_type_to_openapi,
)


@pytest.mark.parametrize(
    "tf_type,expected",
    [
        ("string", {"type": "string"}),
        ("number", {"type": "number"}),
        ("bool", {"type": "boolean"}),
        ("list(string)", {"type": "array", "items": {"type": "string"}}),
        ("set(string)", {"type": "array", "items": {"type": "string"}}),
        ("map(string)", {"type": "object", "additionalProperties": {"type": "string"}}),
        (
            "object({enabled = bool})",
            {"type": "object", "x-kubernetes-preserve-unknown-fields": True},
        ),
        ("any", {"type": "object", "x-kubernetes-preserve-unknown-fields": True}),
        (None, {"type": "string"}),
        ("${list(string)}", {"type": "array", "items": {"type": "string"}}),
        # optional() — scalar
        ("optional(string)", {"type": "string"}),
        ("optional(number)", {"type": "number"}),
        ("optional(bool)", {"type": "boolean"}),
        # optional() with explicit default value
        ("optional(string, null)", {"type": "string"}),
        ("optional(number, 0)", {"type": "number"}),
        # optional() wrapping a collection
        ("optional(list(string))", {"type": "array", "items": {"type": "string"}}),
        (
            "optional(map(string))",
            {"type": "object", "additionalProperties": {"type": "string"}},
        ),
        # optional() wrapping a nested object
        (
            "optional(object({a = string}))",
            {"type": "object", "x-kubernetes-preserve-unknown-fields": True},
        ),
    ],
)
def test_tf_type_to_openapi(tf_type, expected):
    """Terraform type strings are converted to the correct OpenAPI v3 schema fragment."""
    assert tf_type_to_openapi(tf_type) == expected


@pytest.mark.parametrize(
    "var_name,tf_type,expected_contains",
    [
        ("bucket", "string", "| quote"),
        # number/bool — direct expression, var name appears quoted in index call
        ("count", "number", '"count"'),
        ("enabled", "bool", '"enabled"'),
        ("tags", "map(string)", "| toJson"),
        ("cidrs", "list(string)", "| toJson"),
        ("config", "object({a = string})", "| toJson"),
        # optional() variants
        ("timeout", "optional(number)", '"timeout"'),
        ("active", "optional(bool)", '"active"'),
        ("label", "optional(string, null)", "| quote"),
        ("policy", "optional(object({a = string}))", "| toJson"),
    ],
)
def test_tf_type_to_go_expr(var_name, tf_type, expected_contains):
    """Each Terraform type produces the correct Go template pipe filter (quote / toJson / direct)."""
    expr = tf_type_to_go_expr(var_name, tf_type)
    assert expected_contains in expr


@pytest.mark.parametrize(
    "var_name,tf_type",
    [
        ("count", "number"),
        ("enabled", "bool"),
        ("timeout", "optional(number)"),
    ],
)
def test_tf_type_to_go_expr_no_pipe(var_name, tf_type):
    """number and bool use a direct expression — no | quote or | toJson."""
    expr = tf_type_to_go_expr(var_name, tf_type)
    assert "| quote" not in expr
    assert "| toJson" not in expr


@pytest.mark.parametrize(
    "url,expected",
    [
        (
            "git::https://github.com/org/terraform-aws-s3-bucket.git?ref=v4.0.0",
            "terraform-aws-s3-bucket",
        ),
        ("https://github.com/org/my-module.git", "my-module"),
        ("git::https://github.com/org/module", "module"),
        # subdir syntax: last segment of the subdir path becomes the module name
        (
            "git::https://github.com/terraform-aws-modules/terraform-aws-iam.git//modules/iam-role?ref=v6.4.0",
            "iam-role",
        ),
        (
            "git::https://github.com/org/mono-repo.git//modules/my-module",
            "my-module",
        ),
    ],
)
def test_module_name_from_url(url, expected):
    """The module name is extracted from the last path segment of the URL, without the .git suffix or ?ref= query."""
    assert module_name_from_url(url) == expected


@pytest.mark.parametrize(
    "url,expected_repo,expected_subdir,expected_ref",
    [
        # Plain URL — no subdir, no ref
        (
            "git::https://github.com/org/module.git",
            "https://github.com/org/module.git",
            None,
            None,
        ),
        # With ref only
        (
            "git::https://github.com/org/module.git?ref=v1.0.0",
            "https://github.com/org/module.git",
            None,
            "v1.0.0",
        ),
        # With subdir and ref
        (
            "git::https://github.com/org/mono.git//modules/foo?ref=v2.0.0",
            "https://github.com/org/mono.git",
            "modules/foo",
            "v2.0.0",
        ),
        # With subdir, no ref
        (
            "git::https://github.com/org/mono.git//modules/foo",
            "https://github.com/org/mono.git",
            "modules/foo",
            None,
        ),
    ],
)
def test_clone_module_git_command(url, expected_repo, expected_subdir, expected_ref):
    """clone_module passes the correct repo URL (without subdir) to git clone and returns the right path."""
    fake_tmpdir = "/tmp/tfgen-fake"

    with (
        patch("tf2crossplane.parser.tempfile.mkdtemp", return_value=fake_tmpdir),
        patch("tf2crossplane.parser.subprocess.run") as mock_run,
    ):
        result = clone_module(url)  # returns (tmpdir_root, module_path)

    expected_cmd = ["git", "clone", "--depth=1"]
    if expected_ref:
        expected_cmd += ["--branch", expected_ref]
    expected_cmd += [expected_repo, fake_tmpdir]
    mock_run.assert_called_once_with(expected_cmd, check=True, capture_output=True)

    tmpdir_root, module_path = result
    assert tmpdir_root == Path(fake_tmpdir)
    if expected_subdir:
        assert module_path == Path(fake_tmpdir) / expected_subdir
    else:
        assert module_path == Path(fake_tmpdir)


@pytest.mark.parametrize(
    "module_name,expected",
    [
        ("terraform-aws-s3-bucket", "S3Bucket"),
        # parts with len <= 3 are uppercased — KMS, EC2, IAM are well-known AWS acronyms
        ("terraform-aws-kms", "KMS"),
        ("terraform-aws-ec2-instance", "EC2Instance"),
        ("terraform-aws-iam-role", "IAMRole"),
    ],
)
def test_module_name_to_kind(module_name, expected):
    """Module names are converted to CamelCase kinds; parts with 3 chars or fewer are uppercased (S3, EC2, IAM…)."""
    assert module_name_to_kind(module_name) == expected
