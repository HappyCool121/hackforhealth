# ClinicPass V2 rollback context

This public submission repository is not the Render deployment source and cannot trigger a rollback. The live application, its Blueprint, deployment branches, credentials, database backups, and rollback checkpoints are maintained separately in `clinicpass-demo`.

Migration `0005_clinicpass_v2` is additive. In an authorised deployment workspace, the safe application-first strategy is to stop writes, take a verified database backup, deploy the approved pre-V2 checkpoint with `CLINICPASS_V2_ENABLED=false`, and leave the added V2 tables dormant.

A schema downgrade to `0004_durable_document_content` should be a separate, explicitly approved operation performed only after backup verification and confirmation that V2-only synthetic data is no longer required. No deployment or database command should be run from `HappyCool121/hackforhealth`.

For reviewers, the important boundary is simple: source changes and CI activity in this repository do not affect the live Render application.
