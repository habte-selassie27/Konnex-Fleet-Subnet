"""/ws/fleet WebSocket contract tests (TESTING_PLAN.md §15, Phase 9).

Verifies the dashboard's live-data channel:
- ping -> pong keep-alive
- ROBOT_STATE_UPDATE + MISSION_UPDATE snapshots arrive while a mission runs
- invalid api_key is rejected
"""

from __future__ import annotations

import json

import pytest
from starlette.testclient import TestClient

from backend.main import create_app


def _make_client() -> TestClient:
    return TestClient(create_app())


class TestFleetWebSocket:
    def test_ping_pong(self) -> None:
        with _make_client() as client:
            with client.websocket_connect("/ws/fleet?api_key=dev-only-key") as ws:
                ws.send_text("ping")
                assert ws.receive_text() == "pong"

    def test_rejects_invalid_api_key(self) -> None:
        from starlette.websockets import WebSocketDisconnect

        with _make_client() as client:
            # The server closes with 4401 during the connect handshake, so the
            # disconnect surfaces when entering websocket_connect().
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with client.websocket_connect("/ws/fleet?api_key=wrong-key") as ws:
                    ws.receive()
            assert exc_info.value.code == 4401

    def test_streams_robot_and_mission_events(self) -> None:
        with _make_client() as client:
            with client.websocket_connect("/ws/fleet?api_key=dev-only-key") as ws:
                types: set[str] = set()
                for _ in range(6):
                    data = json.loads(ws.receive_text())
                    types.add(data["type"])
                assert "ROBOT_STATE_UPDATE" in types
                assert "MISSION_UPDATE" in types

    def test_robot_state_payload_shape(self) -> None:
        with _make_client() as client:
            with client.websocket_connect("/ws/fleet?api_key=dev-only-key") as ws:
                for _ in range(12):
                    data = json.loads(ws.receive_text())
                    if data["type"] == "ROBOT_STATE_UPDATE":
                        state = data["state"]
                        assert "position" in state and "x" in state["position"]
                        assert "battery_pct" in state
                        assert "nav_state" in state
                        return
                raise AssertionError("no ROBOT_STATE_UPDATE received")

    def test_mission_update_streams_policy_and_live_popw_score(self) -> None:
        """Phase 9 upgrade: MISSION_UPDATE carries the real policy name and a
        live provisional PoPW score computed from current mission state."""
        with _make_client() as client:
            with client.websocket_connect("/ws/fleet?api_key=dev-only-key") as ws:
                mission: dict[str, object] | None = None
                for _ in range(20):
                    data = json.loads(ws.receive_text())
                    if data["type"] == "MISSION_UPDATE":
                        mission = data
                        break
                assert mission is not None, "no MISSION_UPDATE received"
                # Policy matches the configured default allocator.
                assert mission["policy"] == "nearest"
                # A live score exists for a running mission and is bounded.
                score = mission["popw_score"]
                assert isinstance(score, float)
                assert 0.0 <= score <= 100.0
