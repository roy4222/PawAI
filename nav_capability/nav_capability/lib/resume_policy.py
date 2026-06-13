"""Pure-Python guard for route_runner resume_policy.

Layer-1 local source of truth for Lane 6 T6-7:
`resume_policy=operator_confirm|auto` and `REACTIVE_PROFILE=open_space|indoor_tight`.
Do not import pawai_contracts from nav_capability.
"""
from dataclasses import dataclass
from typing import Optional

RESUME_POLICY_OPERATOR_CONFIRM = "operator_confirm"
RESUME_POLICY_AUTO = "auto"
DEFAULT_RESUME_POLICY = RESUME_POLICY_OPERATOR_CONFIRM

REACTIVE_PROFILE_OPEN_SPACE = "open_space"
REACTIVE_PROFILE_INDOOR_TIGHT = "indoor_tight"
DEFAULT_REACTIVE_PROFILE = REACTIVE_PROFILE_OPEN_SPACE

ALLOWED_RESUME_POLICIES = frozenset(
    {RESUME_POLICY_OPERATOR_CONFIRM, RESUME_POLICY_AUTO}
)
ALLOWED_REACTIVE_PROFILES = frozenset(
    {REACTIVE_PROFILE_OPEN_SPACE, REACTIVE_PROFILE_INDOOR_TIGHT}
)


@dataclass(frozen=True)
class ResumePolicyResolution:
    requested_policy: str
    reactive_profile: Optional[str]
    effective_policy: str
    rejected: bool
    reason: Optional[str] = None


def _normalize_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return str(value).strip()


def resolve_resume_policy(
    requested_policy: Optional[str],
    reactive_profile: Optional[str],
) -> ResumePolicyResolution:
    """Return the safe effective resume policy for the route runner.

    `auto` resume is allowed only for the `open_space` reactive profile. Tight
    or unknown profile contexts fall back to `operator_confirm`.
    """
    policy = (
        DEFAULT_RESUME_POLICY
        if requested_policy is None
        else _normalize_optional(requested_policy)
    )
    profile = _normalize_optional(reactive_profile)

    if policy not in ALLOWED_RESUME_POLICIES:
        return ResumePolicyResolution(
            requested_policy=policy,
            reactive_profile=profile,
            effective_policy=DEFAULT_RESUME_POLICY,
            rejected=True,
            reason=f"unknown resume_policy '{policy}'",
        )

    if policy == RESUME_POLICY_OPERATOR_CONFIRM:
        return ResumePolicyResolution(
            requested_policy=policy,
            reactive_profile=profile,
            effective_policy=RESUME_POLICY_OPERATOR_CONFIRM,
            rejected=False,
        )

    if profile == REACTIVE_PROFILE_OPEN_SPACE:
        return ResumePolicyResolution(
            requested_policy=policy,
            reactive_profile=profile,
            effective_policy=RESUME_POLICY_AUTO,
            rejected=False,
        )

    if profile in ALLOWED_REACTIVE_PROFILES:
        reason = f"resume_policy=auto is not allowed for reactive_profile '{profile}'"
    else:
        reason = f"resume_policy=auto requires reactive_profile '{REACTIVE_PROFILE_OPEN_SPACE}'"

    return ResumePolicyResolution(
        requested_policy=policy,
        reactive_profile=profile,
        effective_policy=DEFAULT_RESUME_POLICY,
        rejected=True,
        reason=reason,
    )
