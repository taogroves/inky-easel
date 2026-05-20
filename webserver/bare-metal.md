# Bare-Metal Docker Compose Deployment

This guide deploys Inky Easel directly with Docker Compose on a server where
Docker is already installed. It does not use Coolify or Traefik.

The intended public path is:

```text
Browser / Inky Frame
  -> Cloudflare
  -> Cloudflare Tunnel
  -> localhost:<custom port> on your server
  -> Docker container
```

The compose file binds the portal and API to configurable host ports. The
defaults avoid common ports 3000 and 8000:

| Service | Container port | Default host binding |
| --- | --- | --- |
| `portal` | 3000 | `127.0.0.1:13000` |
| `api` | 8000 | `127.0.0.1:18080` |
| `db` | 3306 | not exposed |

Binding to `127.0.0.1` keeps the services private to the server. Cloudflare
Tunnel can still reach them when `cloudflared` runs on the same host.

## 1. Copy the project to the server

Clone the repository or copy it to your server:

```bash
git clone <your-repo-url> inky-easel
cd inky-easel/webserver
```

If the repository is already there, pull the latest changes:

```bash
cd inky-easel/webserver
git pull
```

## 2. Create the environment file

Copy the bare-metal template:

```bash
cp bare-metal.env.example .env.bare-metal
```

Edit `.env.bare-metal`:

```bash
nano .env.bare-metal
```

Generate secrets:

```bash
openssl rand -hex 32
openssl rand -hex 32
```

Use one generated value for `SERVICE_SECRET` and the other for
`BETTER_AUTH_SECRET`.

For your current domains, these values should look like:

```env
PORTAL_BIND_ADDRESS=127.0.0.1
PORTAL_HOST_PORT=13000

API_BIND_ADDRESS=127.0.0.1
API_HOST_PORT=18080

PUBLIC_BASE_URL=https://api.inky.taogroves.com
CORS_ORIGINS=https://inky.taogroves.com

BETTER_AUTH_URL=https://inky.taogroves.com
BETTER_AUTH_TRUSTED_ORIGINS=https://inky.taogroves.com
```

The database password must match in three places:

```env
MARIADB_PASSWORD=your-db-password
API_DATABASE_URL=mysql+aiomysql://inky:your-db-password@db:3306/inky_easel
PORTAL_DATABASE_URL=mysql://inky:your-db-password@db:3306/inky_easel
```

Do not use `localhost` in the database URLs. Inside Docker Compose, the database
hostname is the service name: `db`.

## 3. Start the stack

From `webserver/`:

```bash
docker compose --env-file .env.bare-metal -f docker-compose.bare-metal.yml up -d --build
```

Check status:

```bash
docker compose --env-file .env.bare-metal -f docker-compose.bare-metal.yml ps
```

Expected:

- `db` is healthy.
- `api` is healthy.
- `portal` is running.

View logs:

```bash
docker compose --env-file .env.bare-metal -f docker-compose.bare-metal.yml logs -f
```

## 4. Test locally on the server

These tests bypass Cloudflare and confirm Docker is working.

Portal:

```bash
curl -fsS http://127.0.0.1:13000/ | head
```

API:

```bash
curl -fsS http://127.0.0.1:18080/healthz
```

Expected API response:

```json
{"ok":true}
```

If you changed `PORTAL_HOST_PORT` or `API_HOST_PORT`, use your chosen ports in
the commands above.

## 5. Point Cloudflare Tunnel to the new ports

In Cloudflare Zero Trust, edit your tunnel and add two public hostnames:

| Public hostname | Service |
| --- | --- |
| `inky.taogroves.com` | `http://localhost:13000` |
| `api.inky.taogroves.com` | `http://localhost:18080` |

If you use a `cloudflared` config file instead of the dashboard, the ingress
rules should look like:

```yaml
ingress:
  - hostname: inky.taogroves.com
    service: http://localhost:13000
  - hostname: api.inky.taogroves.com
    service: http://localhost:18080
  - service: http_status:404
```

Do not point either hostname to `localhost:80` for this deployment. That was for
Coolify/Traefik. This bare-metal compose publishes the app containers directly
on the custom ports.

Also check Cloudflare DNS:

- `inky.taogroves.com` should route through the tunnel.
- `api.inky.taogroves.com` should route through the tunnel.
- Remove any direct `A` or `AAAA` records for these names if you want traffic to
  go only through Cloudflare Tunnel.

## 6. Test from your laptop

Portal:

```bash
curl -fsS https://inky.taogroves.com/ | head
```

API:

```bash
curl -fsS https://api.inky.taogroves.com/healthz
```

Expected:

- The portal returns HTML.
- The API returns `{"ok":true}`.
- The browser sees a Cloudflare certificate for each hostname.

## 7. First use

1. Open `https://inky.taogroves.com`.
2. Create the first user account.
3. Create a frame in the portal.
4. Run the setup wizard.
5. Use `https://api.inky.taogroves.com` as the frame server URL.

The frame talks to the API hostname. The portal talks to the API internally as
`http://api:8000`, so the portal container does not need the public API URL for
server-side API calls.

## Common operations

### Restart

```bash
docker compose --env-file .env.bare-metal -f docker-compose.bare-metal.yml restart
```

### Update after pulling new code

```bash
git pull
docker compose --env-file .env.bare-metal -f docker-compose.bare-metal.yml up -d --build
```

### Stop

```bash
docker compose --env-file .env.bare-metal -f docker-compose.bare-metal.yml down
```

This keeps the MariaDB volume. To delete data too, you would use `down -v`; do
not do that unless you intentionally want to wipe the database.

### Back up the database

```bash
docker compose --env-file .env.bare-metal -f docker-compose.bare-metal.yml exec db \
  mariadb-dump -u root -p"$MARIADB_ROOT_PASSWORD" "$MARIADB_DATABASE" > inky-easel.sql
```

If your shell does not load `.env.bare-metal`, export the variables first:

```bash
set -a
. ./.env.bare-metal
set +a
```

## Troubleshooting

### `address already in use`

Change the host port in `.env.bare-metal`:

```env
PORTAL_HOST_PORT=13001
API_HOST_PORT=18081
```

Then restart:

```bash
docker compose --env-file .env.bare-metal -f docker-compose.bare-metal.yml up -d
```

Update the Cloudflare Tunnel public hostname services to the same ports.

### Cloudflare returns SSL or handshake errors

For a tunnel deployment, public HTTPS terminates at Cloudflare. The origin
service should be plain HTTP:

```text
http://localhost:13000
http://localhost:18080
```

If `api.inky.taogroves.com` still has SSL errors, check that it is a tunnel
public hostname and not a direct DNS `A`/`AAAA` record to your server.

### Tunnel runs in a Docker container

If `cloudflared` runs in a container, `localhost` means the `cloudflared`
container, not the host. Prefer running `cloudflared` directly on the host for
this setup.

If you must run `cloudflared` in Docker, either:

- run it with host networking, or
- bind the app ports to an address reachable from that container and point the
  tunnel service at that address.

Do not switch `PORTAL_BIND_ADDRESS` or `API_BIND_ADDRESS` to `0.0.0.0` unless
you understand the firewall exposure. `127.0.0.1` is the safest default.

### Portal works but frames cannot fetch images

Check:

- `PUBLIC_BASE_URL=https://api.inky.taogroves.com`
- `https://api.inky.taogroves.com/healthz` works from outside your network.
- The frame setup wizard used `https://api.inky.taogroves.com` as the frame
  server URL.

### Portal sign-in or API calls fail

Check:

- `SERVICE_SECRET` is set once and shared by both `api` and `portal`.
- `BETTER_AUTH_URL=https://inky.taogroves.com`
- `BETTER_AUTH_TRUSTED_ORIGINS=https://inky.taogroves.com`
- Database URLs use `db:3306`, not `localhost`.
