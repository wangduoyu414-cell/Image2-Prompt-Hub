# Production deployment v1

## Boundary

The production runtime is a single-host Docker Compose deployment with one
public Caddy entry point, a Next.js Web process, separate read-only public and
authenticated administration APIs, one migration job, PostgreSQL, Redis,
Dramatiq scheduler/workers, and an operations monitor. The
private asset authority is an external HTTPS S3-compatible service such as S3
or R2. The local `compose.yaml` MinIO stack remains a test/development tool and
is not silently promoted to production.

`compose.prod.yaml` deliberately does not publish PostgreSQL or either Python
API to the host. Caddy is the only service with host ports. The Web process
proxies public and administration calls over the internal Docker network, so
the admin session cookie and Origin/CSRF policy stay on one external origin.
Only the gateway and services that require ACME/S3/source egress join the
separate egress network; PostgreSQL remains internal. The production stack does
not expose the internal review preview service or its Web/API paths; Caddy
returns 404 for `/internal-preview*` in production.

## First deployment

1. Copy `deploy/production.env.example` to a root-owned file outside the Git
   checkout and replace every `replace-*` value. Use a URL-safe database
   password or percent-encode it in `IMAGE2_DATABASE_URL`.
2. Create an admin password hash without putting the password in shell history:

   ```console
   python -m apps.admin_api hash-password
   ```

3. Configure a private S3/R2 bucket, private credentials, an HTTPS endpoint,
   DNS for `IMAGE2_SITE_ADDRESS`, and an email for ACME expiry notices.
4. Validate before changing runtime state:

   ```console
   docker compose --env-file /secure/image2.env -f compose.prod.yaml config --quiet
   docker compose --env-file /secure/image2.env -f compose.prod.yaml build public-api web
   ```

   The services share one immutable Python image tag. If a local Compose/Buildx
   release exhibits concurrent same-tag export conflicts, build `public-api`
   (the shared Python image authority) and `web` explicitly; the admin,
   scheduler, worker, monitor, migration, and bootstrap services then reuse the
   same Python image rather than requiring distinct builds.

5. Start the stack:

   ```console
   docker compose --env-file /secure/image2.env -f compose.prod.yaml up -d --wait
   ```

6. On a new data volume, run the separately profiled Chaos fixed-history
   bootstrap once. The command is idempotent and never adds Chaos to the
   continuous scheduler:

   ```console
   docker compose --env-file /secure/image2.env -f compose.prod.yaml \
     --profile bootstrap run --rm bootstrap-fixed-history
   ```

   The six continuous sources are discovered by the scheduler/worker. The
   fixed-history bootstrap and continuous synchronization may run in either
   order because their source and package locks are independent.

The migration job is checksum-verified and must finish successfully before the
APIs start. Re-running the deployment verifies existing migrations rather than
rewriting them. A healthy deployment may correctly report `no_current` and
show zero public cases until evidence-backed human reviews are explicitly
recorded and an administrator activates a Publication v2 snapshot.

## Verification

- `GET /healthz` checks the Web process.
- `GET /readyz` checks Web plus the public and administration database paths.
- `GET /backend-v2/publication` must return a valid v2 publication response;
  `no_current` is valid before the first activation.
- `/admin/review` must require login. Only externally configured users exist;
  the repository contains no default credentials.
- PostgreSQL, API, and administration ports must not be reachable from the host
  through Compose port publishing.
- `/admin/operations` must show seven registered sources, six continuous
  scheduler-eligible sources, the latest cycle, and open alerts.

The scheduler/alert/lifecycle runbook is
`docs/operations/scheduler-monitoring-v1.md`.

## Upgrade and rollback

Build the candidate images, run `config --quiet`, and take a database backup
before `up -d --wait`. SQL migrations are forward-only and immutable. Roll back
application images only when the prior image understands every already-applied
migration; otherwise restore the pre-upgrade database backup and the matching
application images together. Publication rollback is a separate admin action
and remains constrained by active takedowns.

## Secrets and data

- Keep the runtime env file, database backups, S3 credentials, Caddy state, and
  PostgreSQL volume outside Git.
- Rotate database, S3, admin password, and session secrets independently. A
  session-secret or password-hash rotation invalidates existing admin sessions.
- Never mount production credentials into untrusted source parsing worktrees.
- Back up PostgreSQL and retain S3 objects referenced by immutable publication
  versions. A database-only backup is not a complete recovery point.
