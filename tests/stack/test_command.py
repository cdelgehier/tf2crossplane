import pytest
import yaml

from tf2crossplane.stack.command import (
    _parse_resource_flag,
    _parse_wire_flag,
    run_stack,
)

# ── _parse_resource_flag ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw,expected_name,expected_xrd",
    [
        ("kms:xkmskeys", "kms", "xkmskeys"),
        ("sg:xsecuritygroups", "sg", "xsecuritygroups"),
        ("ec2:xec2instances", "ec2", "xec2instances"),
    ],
)
def test_parse_resource_flag(raw, expected_name, expected_xrd):
    r = _parse_resource_flag(raw)
    assert r.name == expected_name
    assert r.xrd == expected_xrd


def test_parse_resource_flag_invalid():
    with pytest.raises(ValueError, match="name:xrd-plural"):
        _parse_resource_flag("bad-format")


# ── _parse_wire_flag ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw,expected_source,expected_target",
    [
        (
            "kms.outputs.key_id -> ec2.kms_key_id",
            "kms.outputs.key_id",
            "ec2.kms_key_id",
        ),
        (
            "sg.outputs.security_group_id -> ec2.vpc_security_group_ids",
            "sg.outputs.security_group_id",
            "ec2.vpc_security_group_ids",
        ),
    ],
)
def test_parse_wire_flag(raw, expected_source, expected_target):
    w = _parse_wire_flag(raw)
    assert w.source == expected_source
    assert w.target == expected_target


def test_parse_wire_flag_invalid():
    with pytest.raises(ValueError, match="->"):
        _parse_wire_flag("kms.outputs.key_id  ec2.kms_key_id")


# ── run_stack (integration) ───────────────────────────────────────────────────


def test_run_stack_from_flags_writes_files(tmp_path, kms_xrd, ec2_xrd):
    """run_stack generates xrd.yaml and composition.yaml in output_dir."""
    # Write XRD files so load_xrd can find them
    kms_dir = tmp_path / "kms"
    ec2_dir = tmp_path / "ec2"
    kms_dir.mkdir()
    ec2_dir.mkdir()
    with open(kms_dir / "xrd.yaml", "w") as f:
        yaml.dump(kms_xrd, f)
    with open(ec2_dir / "xrd.yaml", "w") as f:
        yaml.dump(ec2_xrd, f)

    out_dir = tmp_path / "out"

    run_stack(
        stack_file=None,
        name="StackVM",
        xrd_dir=tmp_path,
        output_dir=out_dir,
        group="homelab.crossplane.io",
        version="v1alpha1",
        resources=["kms:xkmskeys", "ec2:xec2instances"],
        wires=["kms.outputs.key_id -> ec2.kms_key_id"],
        function_go_templating="function-go-templating",
        function_auto_ready="function-auto-ready",
    )

    assert (out_dir / "xrd.yaml").exists()
    assert (out_dir / "composition.yaml").exists()


def test_run_stack_from_flags_valid_yaml(tmp_path, kms_xrd, ec2_xrd):
    """Generated files are valid YAML and contain the expected top-level keys."""
    kms_dir = tmp_path / "kms"
    ec2_dir = tmp_path / "ec2"
    kms_dir.mkdir()
    ec2_dir.mkdir()
    with open(kms_dir / "xrd.yaml", "w") as f:
        yaml.dump(kms_xrd, f)
    with open(ec2_dir / "xrd.yaml", "w") as f:
        yaml.dump(ec2_xrd, f)

    out_dir = tmp_path / "out"
    run_stack(
        stack_file=None,
        name="StackVM",
        xrd_dir=tmp_path,
        output_dir=out_dir,
        group="homelab.crossplane.io",
        version="v1alpha1",
        resources=["kms:xkmskeys", "ec2:xec2instances"],
        wires=["kms.outputs.key_id -> ec2.kms_key_id"],
        function_go_templating="function-go-templating",
        function_auto_ready="function-auto-ready",
    )

    xrd = yaml.safe_load((out_dir / "xrd.yaml").read_text())
    comp = yaml.safe_load((out_dir / "composition.yaml").read_text())

    assert xrd["kind"] == "CompositeResourceDefinition"
    assert xrd["metadata"]["name"] == "xstackvms.homelab.crossplane.io"
    assert comp["kind"] == "Composition"
    assert comp["spec"]["mode"] == "Pipeline"


def test_run_stack_from_file(tmp_path, kms_xrd, ec2_xrd):
    """run_stack reads settings from a *.stack.yaml file."""
    kms_dir = tmp_path / "kms"
    ec2_dir = tmp_path / "ec2"
    kms_dir.mkdir()
    ec2_dir.mkdir()
    with open(kms_dir / "xrd.yaml", "w") as f:
        yaml.dump(kms_xrd, f)
    with open(ec2_dir / "xrd.yaml", "w") as f:
        yaml.dump(ec2_xrd, f)

    out_dir = tmp_path / "out"
    stack_def = {
        "name": "StackVM",
        "group": "homelab.crossplane.io",
        "version": "v1alpha1",
        "xrd_dir": str(tmp_path),
        "output_dir": str(out_dir),
        "resources": [
            {
                "name": "kms",
                "xrd": "xkmskeys",
                "optional": True,
                "expose": ["description"],
            },
            {"name": "ec2", "xrd": "xec2instances"},
        ],
        "wires": [
            {"source": "kms.outputs.key_id", "target": "ec2.kms_key_id"},
        ],
    }
    stack_file = tmp_path / "stackvm.stack.yaml"
    with open(stack_file, "w") as f:
        yaml.dump(stack_def, f)

    run_stack(
        stack_file=stack_file,
        name="",
        xrd_dir=tmp_path,
        output_dir=out_dir,
        group="",
        version="v1alpha1",
        resources=[],
        wires=[],
        function_go_templating="function-go-templating",
        function_auto_ready="function-auto-ready",
    )

    assert (out_dir / "xrd.yaml").exists()
    assert (out_dir / "composition.yaml").exists()


def test_run_stack_from_file_relative_paths(tmp_path, kms_xrd, ec2_xrd):
    """xrd_dir and output_dir in a stack.yaml are resolved relative to the stack file."""
    xrd_dir = tmp_path / "compositions"
    xrd_dir.mkdir()
    (xrd_dir / "kms").mkdir()
    (xrd_dir / "ec2").mkdir()
    with open(xrd_dir / "kms" / "xrd.yaml", "w") as f:
        yaml.dump(kms_xrd, f)
    with open(xrd_dir / "ec2" / "xrd.yaml", "w") as f:
        yaml.dump(ec2_xrd, f)

    # stack file sits one level below tmp_path; paths are relative to it
    stack_dir = tmp_path / "stacks" / "mystack"
    stack_dir.mkdir(parents=True)
    stack_def = {
        "name": "StackVM",
        "group": "homelab.crossplane.io",
        "version": "v1alpha1",
        "xrd_dir": "../../compositions",  # relative to stack file location
        "output_dir": ".",  # relative to stack file location
        "resources": [{"name": "ec2", "xrd": "xec2instances"}],
        "wires": [],
    }
    stack_file = stack_dir / "mystack.stack.yaml"
    with open(stack_file, "w") as f:
        yaml.dump(stack_def, f)

    run_stack(
        stack_file=stack_file,
        name="",
        xrd_dir=tmp_path,
        output_dir=tmp_path,
        group="",
        version="v1alpha1",
        resources=[],
        wires=[],
        function_go_templating="function-go-templating",
        function_auto_ready="function-auto-ready",
    )

    assert (stack_dir / "xrd.yaml").exists()
    assert (stack_dir / "composition.yaml").exists()


def test_run_stack_missing_name_raises(tmp_path):
    """run_stack raises ValueError when --name is missing and no --file is provided."""
    with pytest.raises(ValueError, match="--name"):
        run_stack(
            stack_file=None,
            name="",
            xrd_dir=tmp_path,
            output_dir=tmp_path,
            group="example.crossplane.io",
            version="v1alpha1",
            resources=["ec2:xec2instances"],
            wires=[],
            function_go_templating="function-go-templating",
            function_auto_ready="function-auto-ready",
        )


def test_run_stack_missing_resources_raises(tmp_path):
    """run_stack raises ValueError when no resources are provided."""
    with pytest.raises(ValueError, match="resource"):
        run_stack(
            stack_file=None,
            name="MyStack",
            xrd_dir=tmp_path,
            output_dir=tmp_path,
            group="example.crossplane.io",
            version="v1alpha1",
            resources=[],
            wires=[],
            function_go_templating="function-go-templating",
            function_auto_ready="function-auto-ready",
        )
