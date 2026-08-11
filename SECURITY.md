# SECURITY.md

## Reporting a vulnerability

Please **do not** open a public issue for security problems.

Report suspected vulnerabilities privately by emailing the maintainers or opening a GitHub Security Advisory (if enabled on this repository). Include:

- A description of the issue.
- Steps to reproduce.
- The affected version/filename.
- Any suggested fix, if known.

## Security principles

This project follows a strict security boundary:

```text
PRIVATE / WRITE  ->  ADMIN / IMPORT  ->  VALIDATION  ->  PUBLIC / READ
```

Public users must never receive administrative credentials.

### Secrets

Never commit any of the following to the repository:

- API tokens
- GitHub tokens
- Google service-account credentials
- Passwords
- Private keys
- OAuth secrets

Sensitive credentials belong in GitHub Actions Secrets or another secure server-side mechanism. If a feature requires a secret in browser JavaScript, the architecture must be reconsidered.

### Federated feed headers

`tools/federate.py` REST/JSON-URL feeds may send custom HTTP headers. Values
are expanded from the environment at run time (`"Authorization": "Bearer
${FEED_API_TOKEN}"`); a literal token must never be placed in a committed
config file. `feeds.example.json` documents the placeholders only.

### Deployment boundary

The admin/editing application (`admin/`, `tools/serve.py`) is a local,
developer-only tool. It binds to `127.0.0.1`, holds no credentials, and lives
**outside** `public/` so it can never be uploaded to GitHub Pages. The deploy
artifact is exactly `public/`, which contains no backend code, admin pages,
secrets, or third-party scripts.

### Automated audit

`tools/security_audit.py` runs in CI (and `tests/test_security.py`) and fails
the build on: committed secret patterns, plain-http external URLs, remote
`<script>` tags, unsafe rendering sinks (`eval`, `document.write`,
`innerHTML`) in the public site, unescaped admin id attributes, and a broken
deploy boundary.

### Public site

The public application must not include backend code, admin credentials, secrets, or third-party scripts that transmit data to third parties.

### Input handling

Event data may originate from external sources. All external data is validated, and any rendering into the public site must escape / sanitize content. Never write `innerHTML` with untrusted data.

## Reporting check

Confirm the following before reporting a security concern:

- Is the issue exploitable on the deployed public site?
- Does the issue expose secret material?
- Does the issue allow injection or data corruption?

## Scope

This project is intentionally minimal. Do not report the absence of "enterprise" features (auth servers, RBAC, databases) as vulnerabilities; those are deliberate design decisions documented in `ARCHITECTURE.md`.

## Disclosure

We will acknowledge receipt of valid reports and coordinate a fix. Please allow reasonable time before public disclosure.