# Provider credentials

Keep credentials in an ignored `.env` file or the process environment. The [example file](../.env.example) contains names only. Copy it to `.env` and fill it locally; never paste a key into source code, a run manifest, a command argument, a result file or Git.

The OpenRouter and Jev runners accept `--env-file /path/to/.env`. They read the selected provider key, with an existing environment variable taking precedence. This checkout's admitted hosted runs use the shared codebuild `.env`; the key itself is not part of their saved configuration. Changing the credential source does not authorize a new route or additional spending.

Claude and Codex runs use their supported subscription authentication. Do not copy subscription tokens into this template. The static public website does not load credentials or make inference requests.

Before publishing, check tracked files and Git history for secrets. Keep scanner output redacted. A clean automated scan cannot prove that every possible secret is absent; also inspect how adapters load credentials and how raw provider responses are exported. If a real secret was committed, removing it from the current file is insufficient: revoke or rotate it and assess history cleanup separately.

The repository ignores `.env` and `.env.*`, except the empty `.env.example` template. See [public evidence privacy](PUBLIC_EVIDENCE_PRIVACY.md) for the separate handling of provider account metadata.
