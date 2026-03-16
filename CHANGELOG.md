## v0.5.0 (2026-03-16)

### Feat

- **composition**: add --auto-ready flag and function-auto-ready pipeline step

## v0.4.0 (2026-03-16)

### Feat

- **xrd**: add --composition-update-policy flag, default Automatic
- **composition**: add --provider-config-kind flag for ProviderConfig vs ClusterProviderConfig
- **crossplane**: add XRDs and Compositions for S3, KMS, IAM (wave 7)

### Fix

- **composition**: wrap optional vars in hasKey guard to prevent <no value> errors
- **xrd**: infer array type from default value for ambiguous Terraform types
- **xrd**: remove claimNames — Claims not supported in Crossplane v2 (apiextensions.crossplane.io/v2)

## v0.3.1 (2026-03-15)

### Fix

- **parser**: return (tmpdir_root, module_path) tuple to fix rmtree on subdir clones

## v0.3.0 (2026-03-15)

### Feat

- **parser**: support Terraform //subdir syntax in module URLs

## v0.2.1 (2026-03-15)

### Fix

- **release**: exclude dist/.gitignore from release assets

## v0.2.0 (2026-03-15)

### Feat

- initial implementation of tf2crossplane
