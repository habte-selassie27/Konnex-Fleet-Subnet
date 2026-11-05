"""Weights identity for the deterministic echo policy.

The sandbox verifies a submitted policy's SHA-256 before running it
(`DockerPolicyExecutor._verify_policy_hash`). Both the policy container and the
verification script import this module so the hash has a single source of
truth — it is never hard-coded twice.
"""

from __future__ import annotations

import hashlib

ECHO_POLICY_WEIGHTS = b"konnex-echo-policy-v1"


def echo_policy_hash() -> str:
    """SHA-256 hex digest the container reports for ``ECHO_POLICY_WEIGHTS``."""
    return hashlib.sha256(ECHO_POLICY_WEIGHTS).hexdigest()
