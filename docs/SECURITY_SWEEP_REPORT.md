# Security sweep report

## Scope

Workspace scanned for likely plaintext secrets using patterns such as `sk-...`.

## Findings (historical)

During an internal sweep, plaintext-style key material was reported in **local editor or note files outside this package** (e.g. IDE history exports, personal markdown). Those paths are **not** part of the published `ConcordCoder` source tree on GitHub.

## Remediation status

- Repository documentation and examples use **environment variables** only for API keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, optional `OPENAI_BASE_URL`).
- Do not commit keys, tokens, or long-lived credentials in markdown, logs, or scripts.

## Required practices

1. **Rotate** any key that was ever pasted into a file, chat, or screenshot.
2. Use `.env` (git-ignored) or your OS/CI secret store; never commit `.env` with real values.
3. Prefer `concord doctor` to verify client configuration without printing secrets.

## Verification (local)

From a clean checkout of this repository:

```bash
rg "sk-[A-Za-z0-9]{20,}" --glob '!**/node_modules/**' .
```

Expected: no live provider API keys in tracked source (sample strings in third-party vendored code may still match patterns—review hits manually).
