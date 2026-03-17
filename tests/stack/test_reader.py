import pytest
import yaml

from tf2crossplane.stack.reader import (
    load_xrd,
    xrd_group,
    xrd_kind,
    xrd_spec_properties,
)


def _write_xrd(path, xrd: dict) -> None:
    with open(path, "w") as f:
        yaml.dump(xrd, f)


def test_load_xrd_found(tmp_path, kms_xrd):
    """load_xrd finds an XRD by its spec.names.plural."""
    xrd_dir = tmp_path / "kms"
    xrd_dir.mkdir()
    _write_xrd(xrd_dir / "xrd.yaml", kms_xrd)

    result = load_xrd(tmp_path, "xkmskeys")
    assert result["spec"]["names"]["plural"] == "xkmskeys"


def test_load_xrd_nested(tmp_path, kms_xrd, ec2_xrd):
    """load_xrd searches recursively and returns the matching XRD."""
    (tmp_path / "kms").mkdir()
    (tmp_path / "ec2").mkdir()
    _write_xrd(tmp_path / "kms" / "xrd.yaml", kms_xrd)
    _write_xrd(tmp_path / "ec2" / "xrd.yaml", ec2_xrd)

    assert load_xrd(tmp_path, "xkmskeys")["spec"]["names"]["kind"] == "XKMSKey"
    assert (
        load_xrd(tmp_path, "xec2instances")["spec"]["names"]["kind"] == "XEC2Instance"
    )


def test_load_xrd_not_found(tmp_path):
    """load_xrd raises FileNotFoundError when no XRD matches the plural name."""
    with pytest.raises(FileNotFoundError, match="xunknown"):
        load_xrd(tmp_path, "xunknown")


def test_xrd_spec_properties(kms_xrd):
    """xrd_spec_properties extracts the spec.properties dict from the first version schema."""
    props = xrd_spec_properties(kms_xrd)
    assert "description" in props
    assert "deletion_window_in_days" in props
    assert "providerConfig" in props


def test_xrd_spec_properties_missing(tmp_path):
    """xrd_spec_properties returns an empty dict when the schema is absent."""
    assert xrd_spec_properties({}) == {}


def test_xrd_kind(kms_xrd):
    assert xrd_kind(kms_xrd) == "XKMSKey"


def test_xrd_group(kms_xrd):
    assert xrd_group(kms_xrd) == "homelab.crossplane.io"
