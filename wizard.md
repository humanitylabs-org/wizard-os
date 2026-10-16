---
wizard: 0.2
id: wizard-supervisor
name: Supervisor
version: 0.1.0-prototype
type: service
category: system
summary: Prototype system supervisor for private maintenance decisions and verified recovery.
license: GPL-3.0-only
source: https://github.com/humanitylabs-org/wizard-os/tree/prototype/supervisor-v01/prototypes/supervisor
runtime:
  kind: runtipi
  config: runtipi/config.json
  compose: runtipi/docker-compose.yml
api:
  port: 8798
  path: /api
  spec: openapi.json
mcp:
  port: 8798
  path: /mcp
  transport: streamable-http
skill: skill/SKILL.md
view:
  path: /
  port: 8798
  source:
    path: web
    build: python3 scripts/check_view.py
    dist: web
provides: [supervisor]
system: true
uses: []
needs: []
health: /healthz
---

# Supervisor prototype

An isolated system component. Its shipped enrollment contains only a disposable service and internal job. It does not change live maintenance or the default installation. Read the packaged skill before use.
