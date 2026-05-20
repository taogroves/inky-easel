# Deploying Inky Easel on Coolify

This guide walks through hosting the full stack (MariaDB, FastAPI API, Next.js
portal) on [Coolify](https://coolify.io) using the Docker Compose build pack.

## What you are deploying

| Service | Compose name | Container port | Public? |
| --- | --- | --- | --- |
| MariaDB | `db` | 3306 | **No** — internal only |
| FastAPI | `api` | 8000 | Yes — frames poll this URL |
| Next.js portal | `portal` | 3000 | Yes — browser UI + auth |

The compose file does **not** bind MariaDB (or the HTTP services) to host ports.
Coolify's proxy (Traefik) routes HTTPS traffic to `api` and `portal` on the
private Docker network. That avoids clashes with other stacks on the same server
(for example another MariaDB already using port 3306).

## Prerequisites

- A Coolify server (v4 recommended) with Docker available.
- A domain you control (for example `easel.example.com`).
- This repository in GitHub (public repo, GitHub App, or deploy key).
- TLS: Coolify can issue certificates via Let's Encrypt once DNS points at the
  server.

Plan for **two public hostnames** (or one hostname with a path-based setup — two
subdomains is simpler):

| Hostname | Routes to | Used for |
| --- | --- | --- |
| `https://easel.example.com` | `portal:3000` | Sign-in, schedules, setup wizard |
| `https://api.easel.example.com` | `api:8000` | Frame `POST /api/frame/poll`, image assets |

Frames must reach the **API** hostname over HTTPS (or HTTP on a trusted LAN).
The portal's `PUBLIC_BASE_URL` must match that API origin so generated image
URLs work on the device.

## Step 1 — Create a project and resource

1. Open the Coolify dashboard.
2. Create or select a **Project**.
3. Click **+ New Resource**.
4. Connect your Git repository:
   - **Public repository**: paste the Git URL.
   - **Private**: configure a [GitHub App](https://coolify.io/docs/applications/ci-cd/github/integration#with-github-app-recommended) or [deploy key](https://coolify.io/docs/applications/ci-cd/github/integration#with-deploy-keys).
5. Choose the branch to deploy (for example `main`).

## Step 2 — Select the Docker Compose build pack

1. On the resource setup screen, change the build pack from **Nixpacks** to
   **Docker Compose**.
2. Set these paths (paths are relative to the repository root):

   | Setting | Value |
   | --- | --- |
   | **Base Directory** | `webserver` |
   | **Docker Compose Location** | `docker-compose.yml` |

   Coolify's working directory for the deployment will be `webserver/`. The API
   image build still uses the repo root (`context: ..` in the compose file) so
   `frame-firmware/` is included in the API container.

3. Save and continue.

Do **not** add custom `networks:` blocks to `docker-compose.yml`. Coolify
creates an isolated network and attaches Traefik to it; custom networks can
cause intermittent 504 / unreachable HTTPS issues
([Coolify docs](https://coolify.io/docs/knowledge-base/docker/compose#do-not-define-custom-networks)).

## Step 3 — Environment variables

Coolify reads variables referenced as `${VAR}` in the compose file. Copy
`webserver/.env.example` as a checklist and set every secret in the Coolify UI
(**Environment Variables** for this resource).

### Database (MariaDB)

| Variable | Example | Notes |
| --- | --- | --- |
| `MARIADB_DATABASE` | `inky_easel` | Database name |
| `MARIADB_USER` | `inky` | Application user |
| `MARIADB_PASSWORD` | *(long random)* | Must match URLs below |
| `MARIADB_ROOT_PASSWORD` | *(long random)* | Root password |

Do **not** set `MARIADB_PORT` on Coolify. The database is not published on the
host; only `api` and `portal` connect via `db:3306`.

### Connection strings (must match MariaDB credentials)

| Variable | Example |
| --- | --- |
| `API_DATABASE_URL` | `mysql+aiomysql://inky:<password>@db:3306/inky_easel` |
| `PORTAL_DATABASE_URL` | `mysql://inky:<password>@db:3306/inky_easel` |

Use the hostname `db` (the compose service name), not `localhost`.

### Shared secret (portal ↔ API)

| Variable | Notes |
| --- | --- |
| `SERVICE_SECRET` | Long random string; same value for `api` and `portal` |

Generate with `openssl rand -hex 32` or similar.

### Public URLs (critical)

| Variable | Set to |
| --- | --- |
| `PUBLIC_BASE_URL` | `https://api.easel.example.com` |
| `CORS_ORIGINS` | `https://easel.example.com` |
| `BETTER_AUTH_URL` | `https://easel.example.com` |
| `BETTER_AUTH_TRUSTED_ORIGINS` | `https://easel.example.com` |

`PUBLIC_BASE_URL` is what the server embeds in frame image URLs. It must be the
**API** origin your Pico can reach, not the portal hostname.

### Optional

| Variable | Default | Notes |
| --- | --- | --- |
| `CONTENT_CACHE_MINUTES` | `15` | API content cache TTL |
| `NOMINATIM_USER_AGENT` | — | Required for geocoding; include contact info per [OSM policy](https://operations.osmfoundation.org/policies/nominatim/) |

Leave `API_PORT`, `PORTAL_PORT`, and `MARIADB_PORT` unset on Coolify. They only
apply when using `docker-compose.override.yml` for local development.

## Step 4 — Assign domains to services

After Coolify parses the compose file, it lists services (`db`, `api`, `portal`).

1. **`db`**: leave **without** a domain and **without** port mapping. It should
   stay private on the stack network.

2. **`portal`**: assign your portal domain. Because the container listens on
   port **3000**, enter the domain in Coolify as:
   - `https://easel.example.com:3000`

   Coolify's proxy terminates TLS on 443 and forwards to container port 3000.

3. **`api`**: assign your API domain with container port **8000**:
   - `https://api.easel.example.com:8000`

4. Enable HTTPS / Let's Encrypt in Coolify for both domains once DNS is correct.

### DNS records

Point both hostnames at your Coolify server IP (A/AAAA records), or use a
wildcard if your Coolify server is configured for one.

## Step 5 — Deploy

1. Click **Deploy** (or push to the connected branch if auto-deploy is on).
2. Watch the build logs. All three images should build; `db` should become
   healthy before `api` and `portal` start.
3. If deployment fails with `address already in use` on port **3306**, you are
   likely using an older compose file that published MariaDB on the host, or
   you have a `docker-compose.override.yml` in the repo that adds port mappings.
   Use the current `docker-compose.yml` from this repository (no `db` ports) and
   do not commit a override file to Git.

### Healthy deployment checklist

On the server (SSH), you can verify:

```bash
docker ps --filter "name=bf5cq"   # use your Coolify project/container prefix
```

- `db` container: `healthy`
- `api` container: `healthy` (`/healthz`)
- `portal` container: running (depends on api + db)

From your laptop:

```bash
curl -fsS https://api.easel.example.com/healthz
curl -fsSI https://easel.example.com/
```

## Step 6 — First use

1. Open `https://easel.example.com` and create the first user account.
2. Create a frame in the portal and run the setup wizard.
3. For production bundles, the wizard uses `PUBLIC_BASE_URL` as the frame server
   URL (`https://api.easel.example.com`). You do not need a LAN IP on Coolify.
4. Flash `frame-firmware/flash_loader_main.py` to the Pico as `main.py`, write
   the SD bundle, and reset the frame.

See `frame-firmware/README.md` for hardware details.

## Troubleshooting

### `failed to bind host port 0.0.0.0:3306/tcp: address already in use`

Another process or stack on the Coolify host already uses 3306. The fix is **not**
to stop system MariaDB unless you intend to — the fix is to **stop publishing**
the compose `db` service on the host. Current `docker-compose.yml` does not map
`db` ports. Redeploy after pulling the latest compose file.

If you still see 3306 in the error, check that:

- `webserver/docker-compose.override.yml` is **not** in your Git repository.
- You did not add a custom `ports:` entry for `db` in Coolify's raw compose editor.

### `No available server` in the browser

Usually an unhealthy container or wrong domain port:

- Confirm domain includes `:3000` for portal and `:8000` for api.
- Check `docker ps` health status and container logs in Coolify.
- Ensure `BETTER_AUTH_URL` matches the portal URL exactly (scheme + host, no trailing path).

### Frames cannot load images

- `PUBLIC_BASE_URL` must be the **API** URL the frame uses to poll.
- API must be reachable from the frame's Wi-Fi (HTTPS cert must be valid for
  production; LAN dev often uses `http://<lan-ip>:8000` instead).
- `CORS_ORIGINS` only affects browser calls from the portal, not the frame.

### Portal loads but API calls fail

- `SERVICE_SECRET` must match on `api` and `portal`.
- `PORTAL_DATABASE_URL` / `API_DATABASE_URL` must use password and host `db`.

### Build fails: cannot find `frame-firmware`

The API Dockerfile expects the **repository root** as build context. Base
Directory must be `webserver`, not the repo root alone with a relocated compose
file.

## Local development vs Coolify

| Concern | Local (`docker compose up`) | Coolify |
| --- | --- | --- |
| Host ports | Copy `docker-compose.override.example.yml` → `docker-compose.override.yml` | Not used |
| DB host | `localhost:3306` (via override) | `db:3306` (internal) |
| HTTPS | Optional | Recommended via Coolify proxy |
| URLs | `http://localhost:3000` / `:8000` | Your real domains |

Quick local start:

```bash
cd webserver
cp .env.example .env          # edit secrets
cp docker-compose.override.example.yml docker-compose.override.yml
docker compose up --build
```

## Reference

- [Coolify — Docker Compose build pack](https://coolify.io/docs/applications/build-packs/docker-compose)
- [Coolify — Compose networking and domains](https://coolify.io/docs/knowledge-base/docker/compose)
- In-repo overview: `webserver/README.md`
