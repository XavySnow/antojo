# Antojo Helm Chart

## Table of Contents

- [Purpose](#purpose)
- [Render](#render)
- [Important defaults](#important-defaults)
- [Attribution](#attribution)

## Purpose

A minimal, security-hardened Autopilot lab package for the Antojo application.
Read the [teaching guide](../../docs/learning/helm-cloudbuild.md) before deploying.

## Render

```bash
helm lint charts/antojo
helm template antojo charts/antojo -n antojo \
  --set-string global.imageTag=abcdef1
```

`build-required` is a render-only placeholder; deploy only an actual built SHA.
A service override is `services.<name>.image.tag`; empty means inherit the global tag.
Install a single release per namespace because application DNS names are stable.

## Important Defaults

- Internal Services are ClusterIP; `frontend-external` is a public HTTP LoadBalancer.
- Gateway API is optional and mutually exclusive with that LoadBalancer.
- Load generation is off. Redis is ephemeral, non-HA, and loses carts on replacement.
- Frontend, cart, and checkout have two replicas and PDBs with `minAvailable: 1`.
- Readiness, liveness, startup probes, and explicit resource budgets are included.
- Non-root, read-only root filesystems, no API token mounts, and seccomp are enabled.
- No shopping assistant, Gemini path, `FRONTEND_MESSAGE`, mesh, or telemetry exporter.
- The conservative default requests total 3.5 vCPU / 7 GiB before rollout surge.

Gateway mode needs the GKE Gateway controller and matching GatewayClass already
available. It provides HTTP only; TLS is a separate lesson. This chart is not a
production-ready payment platform or database architecture.

## Attribution

The topology, ports, environment connections, and health-check patterns are
adapted from Google's Apache-2.0-licensed upstream chart at commit
`c7cb6d5bfd6ea3aed768634ebbcb98cb7a523712`. The chart templates/values retain the
upstream license headers; adaptations are marked. See the root `NOTICE` and
`LICENSE-APACHE-2.0` for the chart's upstream-derived material.
