# Endpoint map (43 domains)

The API groups 529 endpoints under resource tags. This map points each domain to its cookbook file, or marks it **live** — meaning no hand-written recipe exists, so fetch the exact schema via the live-spec `jq` technique in [SKILL.md](SKILL.md#live-spec-navigation-the-long-tail). Counts are approximate endpoint totals per tag.

## Covered by a cookbook

| Domain (tag) | Purpose | File |
|---|---|---|
| `application` (~31) | Single app: create, source, build, env, deploy | [deploy-application.md](deploy-application.md) |
| `compose` (~31) | Docker Compose stacks | [deploy-compose.md](deploy-compose.md) |
| `postgres` `mysql` `mongo` `mariadb` `redis` `libsql` (~16 each) | Managed databases | [databases.md](databases.md) |
| `domain` `certificates` `redirects` `port` `mounts` (~5–9) | Ingress, TLS, routing, volumes | [domains-tls.md](domains-tls.md) |
| `server` `cluster` `swarm` `docker` `destination` (~4–17) | Nodes, Swarm, containers, remote storage | [servers.md](servers.md) |
| `backup` `volumeBackups` `schedule` `rollback` (~2–12) | Data protection & scheduled jobs | [backups.md](backups.md) |
| `project` `environment` (~7–9) | Structure / hierarchy | [SKILL.md](SKILL.md#resource-hierarchy) |
| (any destructive endpoint) | Delete / disrupt safety | [safety.md](safety.md) |

## Live-spec only (no cookbook — fetch schema on demand)

| Domain (tag) | Purpose |
|---|---|
| `github` `gitlab` `gitea` `bitbucket` `gitProvider` `registry` | Git/registry provider connections (needed by app source — see deploy-application.md) |
| `deployment` `previewDeployment` `auditLog` | Deployment history, PR previews, audit trail |
| `user` `organization` `sso` `customRole` `security` `sshKey` | Identity, access control, SSH keys |
| `notification` (~41) | Email/Slack/Telegram/Discord/Gotify notifiers |
| `settings` (~53) | Instance settings, monitoring, maintenance |
| `ai` | AI provider config, log analysis, suggestions |
| `tag` `patch` | Resource tagging, patch operations |
| `whitelabeling` `stripe` `licenseKey` `admin` | Branding, billing, licensing, admin |

**Workflow:** pick the tag from this map → list its actions with `... | jq -r '.paths|keys[]|select(startswith("/<tag>."))'` → pull one action's schema with `... | jq '.paths["/<tag>.<action>"]'` → build the call per the [convention](SKILL.md#call-convention-trpc-over-openapi). Check [safety.md](safety.md) if the action mutates.
