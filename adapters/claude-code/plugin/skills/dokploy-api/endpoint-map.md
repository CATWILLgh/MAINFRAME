# Endpoint map

The API groups endpoints under resource tags. This map points each known domain
to its cookbook file, or marks it **live** — meaning no hand-written recipe
exists. Tags and actions change between Dokploy versions, so fetch the exact
schema from the target instance with the live-spec `jq` technique in
[SKILL.md](SKILL.md#live-spec-navigation-the-long-tail).

## Covered by a cookbook

| Domain (tag) | Purpose | File |
|---|---|---|
| `application` | Single app: create, source, build, env, deploy | [deploy-application.md](deploy-application.md) |
| `compose` | Docker Compose stacks | [deploy-compose.md](deploy-compose.md) |
| `postgres` `mysql` `mongo` `mariadb` `redis` `libsql` | Managed databases | [databases.md](databases.md) |
| `domain` `certificates` `redirects` `port` `mounts` | Ingress, TLS, routing, volumes | [domains-tls.md](domains-tls.md) |
| `server` `cluster` `swarm` `docker` `destination` | Nodes, Swarm, containers, remote storage | [servers.md](servers.md) |
| `backup` `volumeBackups` `schedule` `rollback` | Data protection & scheduled jobs | [backups.md](backups.md) |
| `project` `environment` | Structure / hierarchy | [SKILL.md](SKILL.md#resource-hierarchy) |
| (any destructive endpoint) | Delete / disrupt safety | [safety.md](safety.md) |

## Live-spec only (no cookbook — fetch schema on demand)

| Domain (tag) | Purpose |
|---|---|
| `github` `gitlab` `gitea` `bitbucket` `gitProvider` `registry` | Git/registry provider connections (needed by app source — see deploy-application.md) |
| `deployment` `previewDeployment` `auditLog` | Deployment history, PR previews, audit trail |
| `user` `organization` `sso` `customRole` `security` `sshKey` | Identity, access control, SSH keys |
| `notification` | Email/Slack/Telegram/Discord/Gotify notifiers |
| `settings` | Instance settings, monitoring, maintenance |
| `ai` | AI provider config, log analysis, suggestions |
| `tag` `patch` | Resource tagging, patch operations |
| `whitelabeling` `stripe` `licenseKey` `admin` | Branding, billing, licensing, admin |

**Workflow:** pick the tag from this map → list its actions with `... | jq -r '.paths|keys[]|select(startswith("/<tag>."))'` → pull one action's schema with `... | jq '.paths["/<tag>.<action>"]'` → build the call per the [convention](SKILL.md#call-convention-trpc-over-openapi). Check [safety.md](safety.md) if the action mutates.
