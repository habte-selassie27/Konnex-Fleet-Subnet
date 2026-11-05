"""Lifecycle tests for the Konnex provider layer (protocol/konnex).

Covers:
- create_provider() factory modes: disabled / mock / real / invalid
- MockKonnexProvider full PoPW lifecycle: mission → evaluation → proof → rewards
- Reward computation rules (score scaling, high-score bonus, cap)
- get_submission_status lookups for every submission type
- Protocol conformance via the runtime-checkable KonnexProvider Protocol
- Demo script smoke test (scripts/konnex_demo.py) — the make konnex-demo path

Boundary: this layer must stay decoupled from robotics/simulation/ml/fleet
(AGENTS.md §3.2) — enforced by tests/integration/test_konnex_adapter.py for the
whole protocol/konnex package, including the files under test here.

Status: COMPLETE.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, cast

import pytest

from protocol.konnex.bittensor_provider import BittensorKonnexProvider
from protocol.konnex.factory import PROVIDER_MODES, create_provider
from protocol.konnex.mock_provider import (
    BASE_EVAL_REWARD_KNX,
    HIGH_SCORE_BONUS_MULTIPLIER,
    MAX_REWARD_PER_EVAL,
    MockKonnexProvider,
    _compute_reward,
    _mock_tx_hash,
)
from protocol.konnex.models import MissionMetadata, SubmissionReceipt
from protocol.konnex.provider import KonnexProvider
from protocol.konnex.real_provider import RealKonnexProvider
from validator.reproducibility.artifact import EvaluationArtifact

REPO_ROOT = Path(__file__).resolve().parents[2]


def make_metadata() -> MissionMetadata:
    return MissionMetadata(
        mission_id="mission_1",
        policy_id="policy_a",
        scenario_id="warehouse_v1",
        seed=42,
        robot_count=5,
        task_count=20,
        env_version="v1.0.0",
        sim_version="gazebo_harmonic",
    )


def make_artifact() -> EvaluationArtifact:
    artifact = EvaluationArtifact(
        policy_id="policy_a",
        policy_hash="a" * 64,
        scenario_id="warehouse_v1",
        seed=42,
        env_version="v1.0.0",
        sim_version="gazebo_harmonic",
        score_components={"mission_success": 0.9, "safety": 1.0},
        final_score=91.4,
        completion_time_s=245.7,
        collision_count=0,
        tasks_completed=18,
        tasks_total=20,
        energy_consumed=42.3,
        timestamp=1_700_000_000.0,
    )
    return artifact.seal()


class TestFactory:
    def test_disabled_returns_none(self) -> None:
        assert create_provider("disabled") is None

    def test_mock_returns_mock_provider(self) -> None:
        provider = create_provider("mock")
        assert isinstance(provider, MockKonnexProvider)
        assert isinstance(provider, KonnexProvider)

    def test_real_returns_real_provider(self) -> None:
        """Real mode returns the HTTP-based provider (undocumented methods still raise)."""
        provider = create_provider("real", endpoint="https://example.invalid", api_key="k")
        assert isinstance(provider, RealKonnexProvider)
        with pytest.raises(NotImplementedError):
            provider.query_rewards("p")

    def test_real_provider_undocumented_methods_raise(self) -> None:
        """Methods without a documented endpoint remain STUBs."""
        provider = RealKonnexProvider(endpoint="https://example.invalid", api_key="k")
        with pytest.raises(NotImplementedError):
            provider.query_rewards("p")
        with pytest.raises(NotImplementedError):
            provider.get_submission_status("s")

    def test_real_provider_http_surface_uses_documented_endpoints(self) -> None:
        """HTTP methods hit the documented Konnex endpoints with documented fields."""
        import json

        import httpx

        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json={"jobId": "job-123", "status": "ok"})

        transport = httpx.MockTransport(handler)
        provider = RealKonnexProvider(endpoint="https://example.invalid", api_key="k")
        provider._client = httpx.Client(base_url="https://example.invalid", transport=transport)

        receipt = provider.submit_mission(make_metadata())
        assert receipt.submission_id == "job-123"
        assert captured[-1].url.path == "/api/v1/tasks"
        payload = json.loads(captured[-1].read())
        assert {"subnet", "prompt", "rewardStable", "stakeStable", "deadline"} <= set(payload)

        provider.submit_evaluation(policy_id="p", eval_id="e", score=1.0, artifact_hash="hash-xyz")
        assert captured[-1].url.path == "/api/v1/validators/verify"
        payload2 = json.loads(captured[-1].read())
        assert payload2 == {"jobId": "e", "bundleUri": "hash-xyz"}

        provider.publish_proof(make_artifact())
        assert captured[-1].url.path == "/api/v1/validators/verify"

    def test_invalid_mode_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Invalid KONNEX_PROVIDER mode"):
            create_provider("bogus")

    def test_valid_modes(self) -> None:
        assert set(PROVIDER_MODES) == {"disabled", "mock", "real", "bittensor"}


class TestMockLifecycle:
    def test_submit_mission_returns_receipt(self) -> None:
        provider = MockKonnexProvider()
        receipt = provider.submit_mission(make_metadata())

        assert isinstance(receipt, SubmissionReceipt)
        assert receipt.status == "accepted"
        assert receipt.submission_id == "mock_sub_000001"
        assert receipt.tx_hash.startswith("0x")
        assert provider.get_mission_count() == 1

    def test_full_lifecycle_accumulates_rewards(self) -> None:
        provider = MockKonnexProvider()
        provider.submit_mission(make_metadata())
        provider.submit_evaluation("policy_a", "eval_1", 91.4, "b" * 64)
        provider.publish_proof(make_artifact())

        assert provider.get_mission_count() == 1
        assert provider.get_eval_count() == 1
        assert provider.get_proof_count() == 1

        rewards = provider.query_rewards("policy_a")
        assert rewards > 0.0
        assert provider.get_policy_rewards() == {"policy_a": rewards}

    def test_rewards_accumulate_per_policy(self) -> None:
        provider = MockKonnexProvider()
        provider.submit_evaluation("policy_a", "eval_1", 90.0, "b" * 64)
        provider.submit_evaluation("policy_a", "eval_2", 70.0, "c" * 64)
        provider.submit_evaluation("policy_b", "eval_3", 50.0, "d" * 64)

        rewards = provider.get_policy_rewards()
        assert rewards["policy_a"] > rewards["policy_b"]
        assert rewards["policy_a"] == provider.query_rewards("policy_a")
        assert rewards["policy_b"] == provider.query_rewards("policy_b")

    def test_publish_proof_records_deterministic_tx(self) -> None:
        provider = MockKonnexProvider()
        artifact = make_artifact()
        receipt = provider.publish_proof(artifact)

        assert receipt.status == "confirmed"
        assert receipt.tx_hash == _mock_tx_hash(receipt.submission_id)
        assert receipt.tx_hash.startswith("0x")
        assert len(receipt.tx_hash) == 18  # "0x" + 16 hex chars


class TestSubmissionStatus:
    def test_status_of_mission(self) -> None:
        provider = MockKonnexProvider()
        receipt = provider.submit_mission(make_metadata())
        status = provider.get_submission_status(receipt.submission_id)

        assert status["type"] == "mission"
        assert status["status"] == "confirmed"
        assert status["mission_id"] == "mission_1"

    def test_status_of_evaluation(self) -> None:
        provider = MockKonnexProvider()
        receipt = provider.submit_evaluation("policy_a", "eval_1", 88.5, "b" * 64)
        status = provider.get_submission_status(receipt.submission_id)

        assert status["type"] == "evaluation"
        assert status["score"] == 88.5
        assert cast(float, status["reward_knx"]) > 0.0

    def test_status_of_proof(self) -> None:
        provider = MockKonnexProvider()
        receipt = provider.publish_proof(make_artifact())
        status = provider.get_submission_status(receipt.submission_id)

        assert status["type"] == "proof"
        assert status["tx_hash"] == receipt.tx_hash

    def test_unknown_submission(self) -> None:
        provider = MockKonnexProvider()
        status = provider.get_submission_status("mock_sub_999999")

        assert status["type"] == "unknown"
        assert status["status"] == "not_found"


class TestRewardComputation:
    def test_base_reward_scales_with_score(self) -> None:
        low = _compute_reward(50.0)
        high = _compute_reward(79.0)
        assert low == pytest.approx(BASE_EVAL_REWARD_KNX + 50.0 * 0.1)
        assert high > low

    def test_high_score_bonus_applied(self) -> None:
        reward = _compute_reward(81.0)
        base = BASE_EVAL_REWARD_KNX + 81.0 * 0.1
        assert reward == pytest.approx(base * HIGH_SCORE_BONUS_MULTIPLIER)

    def test_reward_capped_at_max(self) -> None:
        assert _compute_reward(100.0) == pytest.approx(MAX_REWARD_PER_EVAL)
        assert _compute_reward(95.0) == pytest.approx(MAX_REWARD_PER_EVAL)

    def test_tx_hash_deterministic(self) -> None:
        assert _mock_tx_hash("mock_sub_000001") == _mock_tx_hash("mock_sub_000001")
        assert _mock_tx_hash("mock_sub_000001") != _mock_tx_hash("mock_sub_000002")


class TestProtocolConformance:
    def test_mock_satisfies_protocol(self) -> None:
        assert isinstance(MockKonnexProvider(), KonnexProvider)

    def test_real_satisfies_protocol(self) -> None:
        assert isinstance(RealKonnexProvider(endpoint="", api_key=""), KonnexProvider)

    def test_bittensor_satisfies_protocol(self) -> None:
        assert isinstance(BittensorKonnexProvider(), KonnexProvider)

    def test_protocol_methods_defined(self) -> None:
        for name in (
            "submit_mission",
            "submit_evaluation",
            "publish_proof",
            "query_rewards",
            "get_submission_status",
        ):
            assert callable(getattr(KonnexProvider, name)), f"missing {name}"


class TestDemoScript:
    def test_demo_runs_end_to_end(self, capsys: pytest.CaptureFixture[str]) -> None:
        """make konnex-demo must complete the full mock lifecycle."""
        path = REPO_ROOT / "scripts" / "konnex_demo.py"
        spec = importlib.util.spec_from_file_location("konnex_demo_script", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        # exec_module runs the script's top-level sys.path bootstrap; harmless
        # here (project root is already on sys.path via pytest pythonpath).
        spec.loader.exec_module(module)
        cast(Any, module).main()

        out = capsys.readouterr().out
        assert "Demo Summary" in out
        assert "Missions submitted:  1" in out
        assert "Evaluations submitted: 1" in out
        assert "Proofs published:    1" in out
        assert "KNX rewards" in out
