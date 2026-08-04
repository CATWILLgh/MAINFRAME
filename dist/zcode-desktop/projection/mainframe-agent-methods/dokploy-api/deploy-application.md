# Deploy an application (Git or Docker image)

Prerequisites: `$DOKPLOY_URL` and `$DOKPLOY_API_KEY` in the environment; the resource hierarchy in [SKILL.md](SKILL.md#resource-hierarchy). All calls POST JSON unless noted; chain resources by id — the create response carries the new resource, or resolve the id via [Discovery](SKILL.md#discover-existing-resources) (`project.all` / `environment.byProjectId`) if the body is empty. `application.deploy` is **asynchronous** — it returns `{}` immediately and the build runs in the background.

## 1. Create the structure

```bash
H=(-H "x-api-key: $DOKPLOY_API_KEY" -H "Content-Type: application/json")
# project -> capture projectId from the response
curl -sS --fail-with-body "${H[@]}" -d '{"name":"acme"}' "$DOKPLOY_URL/api/project.create"
# environment under the project -> capture environmentId
curl -sS --fail-with-body "${H[@]}" -d '{"name":"production","projectId":"<projectId>"}' "$DOKPLOY_URL/api/environment.create"
# application under the environment -> capture applicationId
curl -sS --fail-with-body "${H[@]}" -d '{"name":"web","environmentId":"<environmentId>"}' "$DOKPLOY_URL/api/application.create"
```

## 2. Set the source (pick ONE)

**GitHub** (a GitHub provider must be connected at org level first; list providers with `GET /api/github.githubProviders` to get `githubId`):
```bash
curl -sS --fail-with-body "${H[@]}" -d '{
  "applicationId":"<id>","githubId":"<githubId>","owner":"acme","repository":"web",
  "branch":"main","buildPath":"/","triggerType":"push"}' \
  "$DOKPLOY_URL/api/application.saveGithubProvider"
```
Variants (same shape, different fields — pull schema via live-spec): `application.saveGitlabProvider`, `application.saveGiteaProvider`, `application.saveBitbucketProvider`, `application.saveGitProvider` (generic Git URL).

**Docker image** (no Git):
```bash
curl -sS --fail-with-body "${H[@]}" -d '{
  "applicationId":"<id>","dockerImage":"nginx:1.27","username":null,"password":null,"registryUrl":null}' \
  "$DOKPLOY_URL/api/application.saveDockerProvider"
```

## 3. Build type, environment, deploy

```bash
# buildType: nixpacks | dockerfile | static | railpack | heroku_buildpacks | paketo_buildpacks
# send all keys; set the ones irrelevant to your buildType to null
curl -sS --fail-with-body "${H[@]}" -d '{"applicationId":"<id>","buildType":"nixpacks",
  "dockerfile":null,"dockerContextPath":null,"dockerBuildStage":null,"herokuVersion":null,"railpackVersion":null}' \
  "$DOKPLOY_URL/api/application.saveBuildType"
# env is a dotenv-format string
curl -sS --fail-with-body "${H[@]}" -d '{"applicationId":"<id>","env":"NODE_ENV=production\nPORT=3000",
  "buildArgs":null,"buildSecrets":null,"createEnvFile":false}' \
  "$DOKPLOY_URL/api/application.saveEnvironment"
# fire the build (async, returns {})
curl -sS --fail-with-body "${H[@]}" -d '{"applicationId":"<id>"}' "$DOKPLOY_URL/api/application.deploy"
```

## 4. Watch & update

- **Status / history:** `GET /api/deployment.all?applicationId=<id>` — deployments and their `status` (`idle` / `running` / `done` / `error`).
- **Logs:** `GET /api/application.readLogs?applicationId=<id>` — build/runtime logs.
- **Update later:** `application.redeploy` rebuilds from the latest commit/config; `application.reload` restarts the container without rebuilding. Disruptive ops (`application.stop`, `clearDeployments`, `killBuild`) — see [safety.md](safety.md).

Next: expose it with a domain → [domains-tls.md](domains-tls.md). Connect a managed database → [databases.md](databases.md).
