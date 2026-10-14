# Changelog

## 2026-10-14

- chore: migrated the `terraform/charm` Terraform module to the CC008 Charm
  Terraform Standard. The module now takes `model_uuid` instead of `model`,
  outputs the full `application` object and a `provides` map instead of
  `app_name`/`provides` (string), and requires the `juju/juju` provider
  `>= 1.0, < 3.0`. The `units` default changed from `3` to `1` and
  `constraints`/`base` now default to `null` to comply with the standard;
  pass explicit values to keep the previous behaviour. Added the
  `terraform_modules_compliance.yaml`, `terraform_modules_release.yaml` and
  `generate_terraform_docs.yaml` CI workflows and updated
  `test_terraform_modules.yaml` accordingly.

## 2025-12-17

- Moved charm-architecture.md from Explanation to Reference category.

### 2025-09-08

- feat: add terraform module

### 2025-09-05

- fix: issue with agent ready file not created on setup failure, leading to blockage of further
    operations.
- docs: Fixed Vale and link check failures.
- chore: Added updated documentation check workflow.

### 2025-09-05
- fix: issue with agent ready file not created on setup failure, leading to blockage of further
    operations.

### 2025-03-11

- docs: added changelog
- chore: removed src-docs