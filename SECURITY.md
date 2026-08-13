# Security and demonstration-data policy

ClinicPass is a hackathon prototype, not a production medical system. Use synthetic data only.

- Do not commit API keys, credentials, exports, uploads, logs, or real patient information.
- The seeded credentials are for an isolated local demo only.
- Document content is stored in a Docker volume and can be cleared with `make clean-data`.
- AGNES requests are server-side. Keys are never sent to the browser.
- Readiness checks are administrative checks, not coverage guarantees or clinical decisions.

Report security issues privately to the project owner rather than opening a public issue.

