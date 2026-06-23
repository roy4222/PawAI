# Security Policy

PawAI drives a ~15 kg quadruped robot. Please treat security issues seriously.

## Reporting a vulnerability

Please report security issues **privately** — open a
[GitHub security advisory](https://github.com/roy4222/PawAI/security/advisories/new)
or contact the maintainers — rather than filing a public issue. We aim to
acknowledge reports within a few days.

## Status

PawAI is a research / demo project. Network-facing components (the Studio
gateway, the WebRTC command path, and the navigation action servers) are
intended for use on a trusted LAN and **do not yet ship production
authentication or DDS security (SROS2)**. Hardening is in progress.

Do **not** expose these services to untrusted networks. If you deploy PawAI:

- Keep the robot and edge device on an isolated network.
- Put the Studio gateway behind your own auth/reverse proxy.
- Review and apply [`docs/security/2026-06-13-cyclonedds-hardening-template.md`](docs/security/2026-06-13-cyclonedds-hardening-template.md)
  (a customizable CycloneDDS hardening template) before any non-lab use.

## Scope

Reports about unauthenticated actuation, command injection on the WebRTC/DDS
paths, or gateway access control are especially welcome.
