# 05 — ReMap

## Current state

All-peak/full ReMap is stopped/deferred; it is not `production/full done`.

- `t_8bc6dacf` — stopped by user strategy decision; not canonical; do not auto-resume.
- No canonical `tf_binds_enhancer` edge/evidence exists.

Accepted support-only artifact:

- `t_3b8a2c4d` — CRM support/QA first10k chr1 `pilot accepted`/`staged-only`.
- Prefix: `gs://jouvencekb/kg/staging/source-native-expansion/remap-crm-tf-binds-enhancer-support-chr1-first10k-20260623-t_3b8a2c4d/`
- Semantics: `crm_aggregated_support` / support-QA only.
- Not `observed_binding`; not `tf_regulates_gene`; not canonical.

## Active next step

- `t_b599d3bb` — build accepted CRM support/QA artifact at larger/full feasible scope with detailed report.
- `t_3a7a8c9c` — validate CRM support/QA artifact.
- `t_9b96ea36` — review CRM support/QA artifact/report.

## Definition of done

ReMap CRM support is done only when a staged artifact at agreed scope exists, is validated/reviewed, and has a detailed report. All-peak observed-binding remains a separate deferred strategy.
