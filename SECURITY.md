# Security

Use GitHub-hosted Linux runners for untrusted page observations. Do not grant this action secrets or write permissions. Inputs are passed through environment variables and Python arguments, never evaluated as shell source. Output and fixture paths must stay inside GITHUB_WORKSPACE; symlinks and fixture/report collisions are refused. The bounded checker validates every network destination and redirect, pins connections to validated public IPs and retains TLS checks.

This is a public-resource observer, not a sandbox for executing arbitrary input or a schema/HTML security scanner. Avoid self-hosted runners with sensitive network access. Run trusted revisions of this action and review the source before use. Artifacts are governed by the caller repository's access and retention settings.

For a suspected vulnerability, use GitHub's private vulnerability reporting when available; otherwise contact the maintainer through the official contact route at https://mohammedteto.com/. Do not publish exploit details or secrets in issues.
