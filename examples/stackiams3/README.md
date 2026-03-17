# Example: StackIAMS3

This example shows how to build a **Stack** — a Composition that assembles two
infra resources (IAM role + S3 bucket) into a single Kubernetes object.

## What this example demonstrates

| Feature | Where to look |
|---------|--------------|
| Expose a subset of infra fields on the Stack XRD | `stack/stackiams3.stack.yaml` → `expose:` lists |
| Optional resource (IAM role can be skipped) | `stack/stackiams3.stack.yaml` → `optional: true` on `iam` |
| Reference an existing resource (no create) | `xr-stackiams3.yaml` → `spec.iam.existingId` |
| Generated XRD with sub-objects | `stack/xrd.yaml` → `spec.properties.iam` and `spec.properties.s3` |
| Generated Composition with optional block | `stack/composition.yaml` → `{{- if and (not ...existingId) ...}}` guard |

## Files

```
stackiams3/
├── infra/
│   ├── iam/            # XIamRole XRD + Composition (terraform-aws-iam v6.4.0)
│   └── s3/             # XS3Bucket XRD + Composition (terraform-aws-s3-bucket v4.6.0)
├── stack/
│   ├── stackiams3.stack.yaml   # Stack definition — edit this
│   ├── xrd.yaml                # Generated — do not edit
│   └── composition.yaml        # Generated — do not edit
└── xr-stackiams3.yaml          # Example claim
```

## Prerequisites

- Crossplane with `function-go-templating` and `function-auto-ready` installed
- Infra XRDs deployed (`infra/iam/` and `infra/s3/`)
- A ProviderConfig named `aws-personal-eu-west-1`

## Key lines to read

**`stack/stackiams3.stack.yaml`**
- `optional: true` on `iam` → the IAM role is not required; use `existingId` to
  reference an existing one instead of creating a new one.
- `expose:` lists → only these fields from the infra XRD are visible on the Stack XR.
  All other infra fields keep their defaults.

**`stack/composition.yaml`**
- The `{{- if and (not ...existingId) (not ...import) }}` block → three modes for
  the optional IAM resource: create, reference (existingId), or adopt (import).

## Regenerate

```bash
task example:stackiams3
```
