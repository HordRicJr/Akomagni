# Security Policy

## Supported versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a vulnerability

**Please do not open public GitHub issues for security vulnerabilities.**

Report security issues via one of:

1. [GitHub Security Advisories](https://github.com/HordRicJr/Akomagni/security/advisories/new) (preferred)
2. Email: **security@akomagni.dev**

Include:

- Description of the vulnerability
- Steps to reproduce
- Impact assessment
- Suggested fix (if any)

We aim to acknowledge reports within **72 hours** and provide a status update within **7 days**.

## Scope

In scope:

- Akomagni CLI, core, flow, memory, inference modules
- Install scripts (`install/`)
- Dependency vulnerabilities introduced by our code

Out of scope:

- Third-party models from Hugging Face (report to model authors)
- BMAD skills installed separately
- User misconfiguration of local inference

## Safe defaults

Akomagni runs **locally by default**. The inference server binds to `127.0.0.1`
unless explicitly configured otherwise. Agent tools require approval before
destructive actions (delete, push).

## Security best practices for users

- Do not expose `akomagni serve` to the public internet without authentication
- Review skills and models before running untrusted content
- Keep Python and dependencies updated
