"""
Parse a Terraform module and convert its types to Crossplane-compatible formats.

This module is the entry point for all data extraction from a Terraform module:

  1. clone_module()        — shallow-clone the Git repo into a temp directory
  2. parse_variables()     — extract variable blocks → {name: {type, description, default}}
  3. parse_outputs()       — extract output blocks  → {name: {description}}
  4. tf_type_to_openapi()  — convert a Terraform type string to an OpenAPI v3 schema fragment
                             (used by xrd.py to build the XRD spec.versions[].schema)
  5. tf_type_to_go_expr()  — convert a Terraform type string to the Go template expression
                             that reads the corresponding field from the composite resource spec
                             (used by composition.py to build the Workspace varmap)

The two type-conversion functions share a common normalisation step (_unwrap_optional)
that strips Terraform 1.3+ optional() wrappers before dispatching on the inner type.
"""

import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import hcl2


def clone_module(url: str) -> Path:
    """
    Shallow-clone a Terraform module from a Git URL into a temp directory.

    Supports the Terraform git:: prefix, ?ref= query parameter, and the //subdir
    syntax for pointing at a subdirectory within a repo:
      git::https://github.com/org/module.git?ref=v1.2.3
      git::https://github.com/org/mono-repo.git//modules/my-module?ref=v1.2.3

    --depth=1 avoids downloading the full commit history — we only need the
    current state of the files to parse variables.tf and outputs.tf.

    Returns the path to the cloned directory (or subdirectory); the caller is
    responsible for deleting the tmpdir root (typically via shutil.rmtree in a
    try/finally block).
    """
    # Strip the git:: prefix that Terraform uses but git clone does not understand
    clean_url = url.replace("git::", "")
    ref = None
    if "?ref=" in clean_url:
        clean_url, ref = clean_url.rsplit("?ref=", 1)

    # Support Terraform's //subdir syntax: everything after the first // that is
    # NOT the scheme separator (i.e. not the :// in https://) is a subdir path.
    # Strategy: skip past the scheme (e.g. "https://"), then look for a second //.
    subdir = None
    scheme_end = clean_url.find("//") + 2  # points just after "://"
    rest = clean_url[scheme_end:]
    if "//" in rest:
        before, subdir = rest.split("//", 1)
        repo_url = clean_url[:scheme_end] + before
    else:
        repo_url = clean_url

    tmpdir = tempfile.mkdtemp(prefix="tfgen-")
    cmd = ["git", "clone", "--depth=1"]
    if ref:
        # --branch accepts both branch names and tags (e.g. v4.6.0)
        cmd += ["--branch", ref]
    cmd += [repo_url, tmpdir]
    subprocess.run(cmd, check=True, capture_output=True)

    result = Path(tmpdir)
    if subdir:
        result = result / subdir
    return result


def parse_variables(module_dir: Path) -> dict[str, Any]:
    """
    Parse all variable blocks from the *.tf files in the module root.

    Returns a dict keyed by variable name:
      {
        "bucket":       {"type": "string", "description": "...", "default": None},
        "force_destroy": {"type": "bool",   "description": "...", "default": False},
        ...
      }

    Files that fail to parse (e.g. syntax errors, non-HCL2 content) are silently
    skipped — real modules always have at least one valid variables.tf.
    Sorted glob ensures deterministic ordering across file systems.
    """
    variables: dict[str, Any] = {}
    for tf_file in sorted(module_dir.glob("*.tf")):
        with open(tf_file) as f:
            try:
                data = hcl2.load(f)
            except Exception:
                continue
        # python-hcl2 returns each variable block as a single-key dict:
        # [{"bucket": {"type": "string", ...}}, {"force_destroy": {...}}, ...]
        for var_block in data.get("variable", []):
            for var_name, var_def in var_block.items():
                variables[var_name] = var_def
    return variables


def parse_outputs(module_dir: Path) -> dict[str, Any]:
    """
    Parse all output blocks from the *.tf files in the module root.

    Returns a dict keyed by output name:
      {
        "s3_bucket_id":  {"description": "Bucket ID"},
        "s3_bucket_arn": {"description": "Bucket ARN"},
        ...
      }

    Outputs are currently used only to document the XRD status.outputs field;
    their values are not wired into the Composition template.
    """
    outputs: dict[str, Any] = {}
    for tf_file in sorted(module_dir.glob("*.tf")):
        with open(tf_file) as f:
            try:
                data = hcl2.load(f)
            except Exception:
                continue
        for out_block in data.get("output", []):
            for out_name, out_def in out_block.items():
                outputs[out_name] = out_def
    return outputs


def _unwrap_optional(type_str: str) -> str:
    """
    Strip the optional() wrapper introduced in Terraform 1.3 and return the inner type.

    Handles both forms:
      optional(string)         → string
      optional(string, null)   → string   (drops the default value)
      optional(object({...}))  → object({...})

    The default value is dropped by finding the first comma that sits at
    depth 0 (i.e. not nested inside any parentheses or braces). A simple
    split(",") would break on types like optional(object({a = string}), null).
    """
    match = re.match(r"^optional\((.+)\)$", type_str, re.DOTALL)
    if not match:
        return type_str
    inner = match.group(1)
    # Walk character by character tracking nesting depth to find the
    # top-level comma that separates the type from its default value.
    depth = 0
    for pos, char in enumerate(inner):
        if char in "({":
            depth += 1
        elif char in ")}":
            depth -= 1
        elif char == "," and depth == 0:
            return inner[:pos].strip()
    return inner.strip()


def tf_type_to_openapi(tf_type: Any) -> dict[str, Any]:
    """
    Convert a Terraform type string to an OpenAPI v3 schema fragment.

    Used by xrd.py to populate spec.versions[].schema.openAPIV3Schema.properties.spec.

    OpenAPI v3 is the schema format mandated by Kubernetes for CRD validation
    (spec.versions[].schema.openAPIV3Schema). Crossplane XRDs follow the same
    convention — that is why Terraform types must be translated to OpenAPI
    fragments rather than kept in their native HCL form.

    Mapping:
      string              → {type: string}
      number              → {type: number}
      bool                → {type: boolean}
      list(X) / set(X)    → {type: array, items: <recurse on X>}
      map(X)              → {type: object, additionalProperties: <recurse on X>}
      object({...})       → {type: object, x-kubernetes-preserve-unknown-fields: true}
      optional(X)         → <unwrap and recurse on X>
      any / unknown       → {type: object, x-kubernetes-preserve-unknown-fields: true}

    object({...}) fields are not recursively expanded: the whole object is left
    open with x-kubernetes-preserve-unknown-fields so Kubernetes accepts any
    shape. This is intentional — deeply nested object schemas are verbose,
    rarely validated at the CRD level, and function-go-templating passes them
    as JSON strings anyway.
    """
    if tf_type is None:
        return {"type": "string"}

    type_str = str(tf_type).strip()
    # python-hcl2 sometimes wraps types in ${...} (legacy interpolation syntax)
    if type_str.startswith("${") and type_str.endswith("}"):
        type_str = type_str[2:-1]

    # optional(type) / optional(type, default) — strip the wrapper before dispatching
    type_str = _unwrap_optional(type_str)

    if type_str == "string":
        return {"type": "string"}
    if type_str == "number":
        return {"type": "number"}
    if type_str == "bool":
        return {"type": "boolean"}

    # list(X) and set(X) both map to an array; set semantics are not enforced at the CRD level
    match = re.match(r"^(?:list|set)\((.+)\)$", type_str)
    if match:
        return {"type": "array", "items": tf_type_to_openapi(match.group(1))}

    # map(X) → object with uniform value type
    match = re.match(r"^map\((.+)\)$", type_str)
    if match:
        return {
            "type": "object",
            "additionalProperties": tf_type_to_openapi(match.group(1)),
        }

    # object({...}) — leave open rather than expanding fields recursively
    if type_str.startswith("object("):
        return {"type": "object", "x-kubernetes-preserve-unknown-fields": True}

    # any / unknown / unrecognised — treat as open object
    return {"type": "object", "x-kubernetes-preserve-unknown-fields": True}


def tf_type_to_go_expr(var_name: str, tf_type: Any) -> str:
    """
    Return the Go template expression that reads a variable from the composite resource spec.

    The expression is embedded verbatim in the Workspace varmap inside the Composition template.
    The pipe filter depends on the Terraform type:

      string              → | quote    wraps the value in HCL double-quotes: bucket = "my-bucket"
      number / bool       → direct     no quoting needed:                    count = 2 / enabled = true
      list / map / object → | toJson   serialises as a JSON string that      tags = {"env":"prod"}
                                       OpenTofu deserialises on the other side

    The index function is used instead of dot notation (.spec.bucket) because
    variable names can contain characters that are invalid in Go template identifiers
    (e.g. hyphens).
    """
    type_str = str(tf_type).strip() if tf_type is not None else ""
    if type_str.startswith("${") and type_str.endswith("}"):
        type_str = type_str[2:-1]

    type_str = _unwrap_optional(type_str)

    if type_str in ("string", ""):
        return f'{{{{ index .observed.composite.resource.spec "{var_name}" | quote }}}}'
    if type_str in ("number", "bool"):
        return f'{{{{ index .observed.composite.resource.spec "{var_name}" }}}}'
    # list, set, map, object → JSON
    return f'{{{{ index .observed.composite.resource.spec "{var_name}" | toJson }}}}'


def module_name_from_url(url: str) -> str:
    """
    Extract the module name from a Git URL.

    Takes the last path segment and strips the .git suffix and any ?ref= query:
      git::https://github.com/org/terraform-aws-s3-bucket.git?ref=v4.6.0
        → terraform-aws-s3-bucket
    """
    clean = url.replace("git::", "").split("?")[0].rstrip("/")
    name = clean.split("/")[-1]
    return name.removesuffix(".git")


def module_name_to_kind(module_name: str) -> str:
    """
    Convert a Terraform module name to a CamelCase Kubernetes kind.

    Strips well-known provider prefixes (terraform-aws-, terraform-google-…),
    then joins the remaining parts in CamelCase. Parts with 3 characters or
    fewer are fully uppercased to preserve well-known acronyms:

      terraform-aws-s3-bucket   → S3Bucket    (s3 → S3, bucket → Bucket)
      terraform-aws-kms         → KMS         (kms → KMS)
      terraform-aws-ec2-instance → EC2Instance (ec2 → EC2, instance → Instance)
      terraform-aws-iam-role    → IAMRole     (iam → IAM, role → Role)
    """
    for prefix in (
        "terraform-aws-",
        "terraform-google-",
        "terraform-azurerm-",
        "terraform-",
    ):
        if module_name.startswith(prefix):
            module_name = module_name[len(prefix) :]
            break
    parts = module_name.split("-")
    return "".join(p.upper() if len(p) <= 3 else p.capitalize() for p in parts)
