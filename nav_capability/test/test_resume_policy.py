"""Pure-logic tests for route_runner resume_policy guard."""
import pytest

from nav_capability.lib.resume_policy import (
    DEFAULT_RESUME_POLICY,
    RESUME_POLICY_AUTO,
    RESUME_POLICY_OPERATOR_CONFIRM,
    resolve_resume_policy,
)


@pytest.mark.parametrize("profile", [None, "open_space", "indoor_tight", "garbage"])
def test_default_resume_policy_is_operator_confirm_for_any_profile(profile):
    resolution = resolve_resume_policy(None, profile)

    assert DEFAULT_RESUME_POLICY == RESUME_POLICY_OPERATOR_CONFIRM
    assert resolution.effective_policy == RESUME_POLICY_OPERATOR_CONFIRM
    assert resolution.rejected is False


def test_open_space_allows_auto_resume_policy():
    resolution = resolve_resume_policy(RESUME_POLICY_AUTO, "open_space")

    assert resolution.effective_policy == RESUME_POLICY_AUTO
    assert resolution.rejected is False


def test_indoor_tight_rejects_auto_resume_policy_and_falls_back_to_operator_confirm():
    resolution = resolve_resume_policy(RESUME_POLICY_AUTO, "indoor_tight")

    assert resolution.effective_policy == RESUME_POLICY_OPERATOR_CONFIRM
    assert resolution.rejected is True


@pytest.mark.parametrize("profile", [None, "open_space", "indoor_tight", "garbage"])
def test_operator_confirm_resume_policy_is_allowed_for_any_profile(profile):
    resolution = resolve_resume_policy(RESUME_POLICY_OPERATOR_CONFIRM, profile)

    assert resolution.effective_policy == RESUME_POLICY_OPERATOR_CONFIRM
    assert resolution.rejected is False


@pytest.mark.parametrize(
    "requested_policy,profile",
    [
        ("garbage", "open_space"),
        ("", "open_space"),
        (RESUME_POLICY_AUTO, None),
        (RESUME_POLICY_AUTO, "garbage"),
    ],
)
def test_unknown_policy_or_profile_falls_back_to_operator_confirm(requested_policy, profile):
    resolution = resolve_resume_policy(requested_policy, profile)

    assert resolution.effective_policy == RESUME_POLICY_OPERATOR_CONFIRM
    assert resolution.rejected is True
