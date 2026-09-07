# Dokploy applications

Use this reference for creating or changing an Application, its source, build
configuration, environment, deployment, or rollback.

Discover the existing project, environment, application, source provider,
branch or image, build method, build path, runtime settings, domains, mounts,
and deployment history. Reuse stable resources instead of creating duplicates.

Before mutation, obtain the current schemas for the exact create, source,
configuration, environment, deploy, and status operations. Do not reuse a
payload from another instance or assume every build method accepts the same
fields. Keep secret values out of JSON shown in chat, patches, and logs.

Deployment is asynchronous. API acceptance proves only that work was queued.
Follow the resulting deployment to a terminal state, inspect bounded logs on
failure, re-read the application, and verify the routed product behavior.

Distinguish deploy, redeploy, reload, rebuild, stop, cancel, and rollback by
their current documented effect. Establish downtime and data implications
before use. A deployment rollback changes application delivery state; it does
not restore database or volume contents.
