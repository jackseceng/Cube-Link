# Cube-Link — Project Steering

## Overview

Cube-Link is a Python/Flask URL shortening web app. URLs are encrypted at rest using PBKDF2+Fernet, stored in a Turso (libSQL) database, and served via Gunicorn inside a minimal scratch-based Docker image. The live instance runs at [cubel.ink](https://cubel.ink).

## Stack

- **Runtime**: Python 3.15 (built from source in Docker)
- **Web framework**: Flask 3.x, served via Gunicorn
- **Database**: Turso (libSQL) via `pyturso` — remote-synced local replica at `/tmp/urls.db`
- **Encryption**: `cryptography` library — PBKDF2HMAC (SHA-256, 120,000 iterations) + Fernet
- **Captcha**: Cloudflare Turnstile
- **Static assets / CDN**: Cloudflare R2
- **Container**: Multi-stage Docker build (Alpine build → scratch runtime), non-root user `1001:1001`

## Key Files

| File | Purpose |
| ---- | ------- |
| `app/app.py` | Flask application, routes, CSP/security headers |
| `app/url_mgmt.py` | URL validation, encryption/decryption, Turnstile verification |
| `app/turso_mgmt.py` | All database operations (get, insert, increment, stats) |
| `app/gunicorn_cfg.py` | Gunicorn standalone launcher (`0.0.0.0:8080`, workers = CPU×2+1) |
| `app/healthcheck/healthcheck.py` | Docker HEALTHCHECK — GET `http://localhost:8080`, exit 0/1 |
| `app/templates/` | Jinja2 HTML templates (index, link, redirect, stats, 404, 500) |
| `app/static/` | JS and image assets (served via R2 CDN in production) |
| `requirements.txt` | Pinned Python dependencies |
| `Dockerfile` | Two-stage build: Alpine → scratch |
| `docker-compose.yaml` | Local dev compose (port 80→8080, tmpfs at /tmp) |

## Environment Variables

Stored in `app/.env` (never commit real secrets). Required at runtime:

| Variable | Description |
| -------- | ----------- |
| `ENDPOINT` | Turso database URL (`libsql://...`) |
| `TOKEN` | Turso auth JWT |
| `CF_SECRET` | Cloudflare Turnstile secret key |
| `TLD` | App domain (e.g. `localhost` or `cubel.ink`) |
| `CDN` | Cloudflare R2 public bucket URL |

## Database Schema

```sql
CREATE TABLE urls (
  HASHSUM  NUMERIC PRIMARY KEY NOT NULL,
  URL      BLOB    NOT NULL,
  SALT     BLOB    NOT NULL,
  CLICKS   INTEGER NOT NULL DEFAULT 0,
  LASTCLICK TEXT   NOT NULL DEFAULT 'YYYY-MM-DDTHH:MM:SS.ffffff'
);
```

- `HASHSUM` is SHA-256 of the short path (the key used for all lookups)
- `URL` is Fernet-encrypted ciphertext; `SALT` is the 16-byte random salt used to derive the key

## Local Development

### Build and run

```bash
docker compose up -d --build
```

App available at <http://localhost>. Rebuild after any code change.

### Shut down

```bash
docker compose down
```

### Upload static assets to R2 (dev bucket)

```bash
docker run --rm -ti -v ~/.aws:/root/.aws -v ./app/static:/data \
  amazon/aws-cli s3 sync /data s3://<bucket> \
  --endpoint-url https://<r2-endpoint>.eu.r2.cloudflarestorage.com
```

## SRI Hashes

Any change to a file in `app/static/` requires regenerating its SRI hash and updating the `integrity` attribute in all referencing HTML templates.

Generate hash for a single file:

```bash
openssl dgst -sha384 -binary app/static/<filename> | openssl base64 -A
```

Regenerate all at once:

```bash
for f in app/static/*; do
  echo "$(basename $f): sha384-$(openssl dgst -sha384 -binary $f | openssl base64 -A)"
done
```

Prefix output with `sha384-` and update the matching `integrity` attribute in `app/templates/`.

After updating templates, rebuild the container. In production, also purge the Cloudflare cache for changed files.

## Security Conventions

- All user input is sanitised with `bleach.clean()` before use
- URLs must start with `https://` and contain no whitespace
- Custom short extensions are alphanumeric only, 1–30 chars
- URL reputation is checked against two external blocklists on every submission
- Security headers follow the OWASP cheat sheet (CSP, HSTS, X-Frame-Options, etc.) — set in `add_security_headers()` in `app.py`
- Container runs as non-root (`USER 1001:1001`) on a scratch base image
- Dependencies are pinned to exact versions in `requirements.txt`

## Coding Conventions

- Module-level docstrings on every file
- All functions have docstrings
- Exceptions are caught and logged with `logging.error()`; functions return `False` or `None` on failure rather than raising
- `bleach.clean()` wraps all user-supplied strings before processing
- Use `http.HTTPStatus` constants instead of raw integer status codes
- New database operations go in `turso_mgmt.py`; URL logic goes in `url_mgmt.py`; routing stays in `app.py`

## Linting

Before committing, run the Super Linter task to validate code style and formatting locally.

In the IDE: open the Command Palette, select **Tasks: Run Task**, then choose **Super Linter**.

This runs the following validators inside Docker against the full codebase:

- Python: `black`, `isort`
- CSS, HTML, Markdown, YAML, JavaScript (Prettier)
- Dockerfile: `hadolint`
- GitHub Actions
- Secret scanning: `gitleaks`

The task requires Docker to be running. Output appears in a new terminal panel. Fix any reported issues before committing.

## Commit Format

All commits must follow the [Conventional Commits](https://www.conventionalcommits.org/) format. This is enforced by CI on every PR to `main`.

Format:

```text
<type>(<optional scope>): <description>
```

Allowed types: `feat`, `fix`, `chore`, `docs`, `refactor`, `build`, `ci`, `style`, `perf`, `test`

Examples:

```text
feat: add custom URL extension support
fix: handle null response from turso on get_link
chore: pin cryptography to 47.0.0
docs: update SRI hash regeneration instructions
refactor: extract turnstile validation into url_mgmt
ci: add super-linter workflow
```

## CI/CD

Pipeline runners via GitHub Actions:

- `lint.yml` — linting
- `security.yml` — security scans
- `semver.yml` — semantic versioning
- `r2-upload.yml` — static asset upload to R2
- `conventional-commits.yml` — commit message enforcement (conventional commits required on all PRs to `main`)
