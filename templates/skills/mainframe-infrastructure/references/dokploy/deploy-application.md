# Deploy an application (Git or Docker image)

Prerequisites: the resolved base URL and credential access described in
[SKILL.md](../dokploy.md), plus its resource hierarchy. Verify each mutation's
current schema against the target instance before sending it. Chain resources
by id; if a create response is empty, resolve the id through the documented
read endpoints. Treat deployment as asynchronous and verify its actual status.

## 1. Create the structure

```bash
# project -> capture projectId from the response
curl --disable -sS --fail-with-body --connect-timeout 5 --max-time 30 -H "x-api-key: $DOKPLOY_API_KEY" -H "Content-Type: application/json" -d '{"name":"acme"}' "$DOKPLOY_URL/api/project.create"
# environment under the project -> capture environmentId
curl --disable -sS --fail-with-body --connect-timeout 5 --max-time 30 -H "x-api-key: $DOKPLOY_API_KEY" -H "Content-Type: application/json" -d '{"name":"production","projectId":"<projectId>"}' "$DOKPLOY_URL/api/environment.create"
# application under the environment -> capture applicationId
curl --disable -sS --fail-with-body --connect-timeout 5 --max-time 30 -H "x-api-key: $DOKPLOY_API_KEY" -H "Content-Type: application/json" -d '{"name":"web","environmentId":"<environmentId>"}' "$DOKPLOY_URL/api/application.create"
```

## 2. Set the source (pick ONE)

**GitHub** (a GitHub provider must be connected at org level first; list providers with `GET /api/github.githubProviders` to get `githubId`):
```bash
curl --disable -sS --fail-with-body --connect-timeout 5 --max-time 30 -H "x-api-key: $DOKPLOY_API_KEY" -H "Content-Type: application/json" -d '{
  "applicationId":"<id>","githubId":"<githubId>","owner":"acme","repository":"web",
  "branch":"main","buildPath":"/","triggerType":"push"}' \
  "$DOKPLOY_URL/api/application.saveGithubProvider"
```
Variants (same shape, different fields — pull schema via live-spec): `application.saveGitlabProvider`, `application.saveGiteaProvider`, `application.saveBitbucketProvider`, `application.saveGitProvider` (generic Git URL).

**Docker image** (no Git):
```bash
curl --disable -sS --fail-with-body --connect-timeout 5 --max-time 30 -H "x-api-key: $DOKPLOY_API_KEY" -H "Content-Type: application/json" -d '{
  "applicationId":"<id>","dockerImage":"nginx:1.27","username":null,"password":null,"registryUrl":null}' \
  "$DOKPLOY_URL/api/application.saveDockerProvider"
```

## 3. Build type, environment, deploy

```bash
# buildType: nixpacks | dockerfile | static | railpack | heroku_buildpacks | paketo_buildpacks
# send all keys; set the ones irrelevant to your buildType to null
curl --disable -sS --fail-with-body --connect-timeout 5 --max-time 30 -H "x-api-key: $DOKPLOY_API_KEY" -H "Content-Type: application/json" -d '{"applicationId":"<id>","buildType":"nixpacks",
  "dockerfile":null,"dockerContextPath":null,"dockerBuildStage":null,"herokuVersion":null,"railpackVersion":null}' \
  "$DOKPLOY_URL/api/application.saveBuildType"
# env is a dotenv-format string
curl --disable -sS --fail-with-body --connect-timeout 5 --max-time 30 -H "x-api-key: $DOKPLOY_API_KEY" -H "Content-Type: application/json" -d '{"applicationId":"<id>","env":"NODE_ENV=production\nPORT=3000",
  "buildArgs":null,"buildSecrets":null,"createEnvFile":false}' \
  "$DOKPLOY_URL/api/application.saveEnvironment"
# fire the build (async, returns {})
curl --disable -sS --fail-with-body --connect-timeout 5 --max-time 30 -H "x-api-key: $DOKPLOY_API_KEY" -H "Content-Type: application/json" -d '{"applicationId":"<id>"}' "$DOKPLOY_URL/api/application.deploy"
```

## 4. Watch & update

- **Status / history:** `GET /api/deployment.all?applicationId=<id>` — deployments and their `status` (`idle` / `running` / `done` / `error`).
- **Logs:** `GET /api/application.readLogs?applicationId=<id>` — build/runtime logs.
- **Update later:** `application.redeploy` rebuilds from the latest commit/config; `application.reload` restarts the container without rebuilding. Disruptive ops (`application.stop`, `clearDeployments`, `killBuild`) — see [safety.md](safety.md).

Next: expose it with a domain → [domains-tls.md](domains-tls.md). Connect a managed database → [databases.md](databases.md).
