# Network Diagnosis

PawAI has two separate network paths:

```text
developer laptop -> Tailscale -> Jetson -> Ethernet -> Go2
```

Go2 is not shared over Tailscale. It normally lives at `192.168.123.161` on the
Jetson-Go2 Ethernet link. Team members connect to Jetson; Jetson connects to Go2.

## Jetson Moves To A New Network

When Jetson moves from home to school:

- Tailscale IP should stay stable.
- Jetson Wi-Fi/LAN IP may change and should not be relied on.
- Go2 IP should stay `192.168.123.161` if Ethernet remains Jetson <-> Go2.

The dangerous case is using Jetson Ethernet for school network access, because
that removes the Go2 link.

## Diagnosis Order

1. Local Tailscale can see Jetson:
   ```bash
   tailscale status
   tailscale ping <jetson-host-or-ip>
   ```
2. SSH alias works:
   ```bash
   ssh "$JETSON_HOST" 'echo OK && hostname'
   ```
3. Jetson has a Go2-facing interface:
   ```bash
   ssh "$JETSON_HOST" "ip -br addr | grep 192.168.123 || true"
   ```
4. Jetson can ping Go2:
   ```bash
   ssh "$JETSON_HOST" "ping -c 1 -W 2 ${ROBOT_IP:-192.168.123.161}"
   ```
5. Gateway diagnosis:
   ```bash
   ssh "$JETSON_HOST" "curl -fsS http://127.0.0.1:8080/health"
   curl -fsS "http://${JETSON_TAILSCALE_IP}:8080/health"
   ```

Interpretation:

- Jetson local health works, laptop Tailscale health fails: Tailscale or sharing path issue.
- Both health checks fail: Gateway is not running or crashed.
- Both health checks work, browser fails: Studio frontend env likely points at the wrong host.

## Common Causes

- Team member did not accept the Tailscale share link.
- Tailscale is installed but not logged in.
- `JETSON_HOST` alias does not match `~/.ssh/config`.
- Jetson is online, but Ethernet is not connected to Go2.
- Jetson's default route accidentally uses the Go2 Ethernet interface.
- Demo is not running, so Gateway 8080 correctly reports unavailable.
