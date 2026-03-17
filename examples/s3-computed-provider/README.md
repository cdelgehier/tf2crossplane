# Example: S3 with Computed Provider

This example shows three advanced settings for `tf2crossplane infra`:
`extra_vars`, `provider_config_format`, and `secret_name_format`.

Use case: deploy an S3 bucket to any AWS account and region by setting
`target_account` and `target_region` in the XR — no `providerConfig` field needed.

## What this example demonstrates

| Feature | Where to look |
|---------|--------------|
| Add fields not in the Terraform module | `infra/xrd.yaml` → `target_account` and `target_region` properties |
| `target_account` is required, `target_region` has a default | `infra/xrd.yaml` → `required: [target_account]` |
| ProviderConfig name computed from spec fields | `infra/composition.yaml` → `providerConfigRef.name` |
| `providerConfig` absent from the XRD spec | `infra/xrd.yaml` → no `providerConfig` field under `spec.properties` |
| Connection secret with a custom name | `infra/composition.yaml` → `writeConnectionSecretToRef` block |

## Files

```
s3-computed-provider/
├── infra/
│   ├── xrd.yaml          # Generated — do not edit
│   └── composition.yaml  # Generated — do not edit
└── xr-s3-computed-provider.yaml  # Example claim
```

## Prerequisites

- Crossplane with `function-go-templating` and `function-auto-ready` installed
- **One ProviderConfig per account+region combination**, named `aws-<account_id>-<region>`.
  Example: `aws-123456789012-eu-west-1`
- The provider must support `writeConnectionSecretToRef` (provider-opentofu does).
  Without this, the secret is never written even if `secret_name_format` is set.

## Key things to read

**`infra/composition.yaml`**
- `providerConfigRef.name` is built with Go `printf` from `target_account` and
  `target_region`. The static `spec.providerConfig` field is not used.
- `writeConnectionSecretToRef` — Crossplane writes the workspace outputs
  (bucket ARN, region…) to a Secret named `<xr-name>-s3-creds`.

**`infra/xrd.yaml`**
- `target_account` and `target_region` are injected by `--extra-var`. They are
  not Terraform module variables; they only drive the ProviderConfig name.
- No `providerConfig` field in the spec — when `provider_config_format` is set,
  tf2crossplane removes it to avoid ambiguity.

## Regenerate

```bash
task example:s3-computed-provider
```
