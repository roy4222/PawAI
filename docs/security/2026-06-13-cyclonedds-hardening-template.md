# CycloneDDS Hardening Template

This note documents `config/cyclonedds-template.xml`. The file is a template only:
this commit does not set `CYCLONEDDS_URI`, does not change `ROS_DOMAIN_ID`, and
does not wire DDS settings into launch scripts or runtime environments.

Actual rollout is deferred to post-2026-06-18 Phase 4 T4A-3, where this should be
paired with SROS2 and domain planning. It is defense in depth alongside the
`/webrtc_req` filter from T5S-1 and gateway authentication.

## Threat Context

The threat model calls out the R2/DDS root cause: PawAI currently relies on an
open ROS2 DDS bus without SROS2, while CycloneDDS can bind interfaces beyond the
intended robot ethernet segment. See
2026-06-11-pawai-threat-model.md for the DDS
section and R2 context.

## CYCLONEDDS_URI

`CYCLONEDDS_URI` tells CycloneDDS which XML configuration file to load. To try
the template during the later rollout, set it on the Jetson and on every dev
machine that intentionally joins the same ROS2 DDS bus.

Example with a file URI:

```bash
export CYCLONEDDS_URI=file:///home/jetson/elder_and_dog/config/cyclonedds-template.xml
```

Example with a bare path:

```bash
export CYCLONEDDS_URI=/home/jetson/elder_and_dog/config/cyclonedds-template.xml
```

For a WSL/dev machine that joins the bus, point to that machine's local checkout:

```bash
export CYCLONEDDS_URI=/home/roy422/newLife/elder_and_dog/config/cyclonedds-template.xml
```

Do not enable this until the placeholder interface and peer addresses have been
replaced for the actual deployment.

## NetworkInterface Limiting

The template uses:

```xml
<Interfaces>
  <NetworkInterface name="eth0" multicast="false" />
</Interfaces>
```

Replace `eth0` with the real Jetson-to-Go2 ethernet interface, or use the actual
interface address if that is clearer for the host. The purpose is to stop DDS
from binding all available interfaces, including Tailscale, Wi-Fi, or a shared
demo network.

## Multicast Disabled

The template sets:

```xml
<AllowMulticast>false</AllowMulticast>
```

This disables multicast discovery. Without multicast discovery, nodes should not
discover arbitrary hosts on the local network just because they share a ROS2 DDS
domain.

## Peers Allowlist

The template uses explicit unicast peers:

```xml
<Peers>
  <Peer address="192.168.123.161" />
  <Peer address="192.168.123.x" />
</Peers>
```

Replace the sample addresses with the known DDS participants for the Go2 ethernet
segment, such as the Jetson and any intentionally joined dev machine. Every
participant that uses this unicast-only discovery pattern needs the relevant peer
entries for the other participants it should discover.

## Rollout Notes

This is not a complete DDS security boundary. It reduces discovery and interface
exposure, but it does not authenticate ROS2 participants. The post-2026-06-18
Phase 4 T4A-3 rollout should validate interface names, peer addresses,
`ROS_DOMAIN_ID`, firewall posture, and SROS2 together before enabling it for demo
or home operation.
