## v0.11.0 (2026-03-17)

### Feat

- **stack**: add static wire support for injecting literal values
- **stack**: support nested wire targets for object fields

### Fix

- **examples**: add create_security_group=false wire, fix port strings, document static wires
- **xrd**: always use x-kubernetes-preserve-unknown-fields for all outputs
- **xrd**: use x-kubernetes-preserve-unknown-fields for complex outputs
- **stack**: use RFC 1123-compliant slug for composed resource metadata.name
- **stack**: render array-typed wire targets as YAML lists
- **infra**: strip X prefix from --kind to prevent double-X kinds

## v0.5.0 (2026-03-17)

## v0.10.0 (2026-03-17)

### Feat

- **infra**: propagate workspace outputs to XR status.atProvider.outputs

## v0.5.0 (2026-03-17)

## v0.9.0 (2026-03-17)

### Feat

- **examples**: add stackiams3 and stackec2iams3 self-contained examples

### Fix

- **stack**: forward exposed spec fields from Stack XR to composed XRs

## v0.5.0 (2026-03-17)

## v0.8.1 (2026-03-17)

### Fix

- **stack**: resolve xrd_dir and output_dir relative to stack file location

## v0.5.0 (2026-03-17)

## v0.8.0 (2026-03-17)

### Feat

- **stack**: add stack subcommand for Composition of Compositions
- **composition,xrd**: add --provider-config-format to compute providerConfigRef.name dynamically

## v0.5.0 (2026-03-16)

## v0.7.0 (2026-03-16)

### Feat

- **xrd**: add --extra-var option to inject additional fields into XRD spec
- **composition**: add --secret-name-format option for writeConnectionSecretToRef

## v0.5.0 (2026-03-16)

## v0.6.0 (2026-03-16)

### Feat

- **composition**: add --workspace-source option to override Workspace forProvider.source
- **composition**: add --workspace-api-version option to override Workspace apiVersion
- **composition**: add --function-auto-ready option to override function name
- **composition**: add --function-go-templating option to override function name
- **xrd**: add --scope option for Namespaced/Cluster XRD scope

## v0.5.0 (2026-03-16)

## v0.5.1 (2026-03-16)

### Fix

- **ci**: sync uv.lock after version bump in bump-version workflow

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
