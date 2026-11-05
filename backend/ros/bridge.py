"""ROSBridge — optional ROS 2 connectivity for the backend (Phase 1).

The ONLY module in the backend that knows about rclpy (AGENTS.md §4.10,
docs/robotics.md). Everything else in the backend is ROS-agnostic.

Modes:
  - headless (default, SIM_MODE=headless): rclpy is typically not installed;
    `is_available` is False and the bridge is inert — the backend runs on the
    deterministic headless SimulationRobotAdapter.
  - gazebo (SIM_MODE=gazebo): start() initializes rclpy, runs a spin loop in a
    background thread, and lets callers attach subscriptions whose callbacks
    are marshalled onto the asyncio loop via `on_event`.

Status: COMPLETE (Phase 1 wiring) — live ROS 2 execution NOT RUN on this
machine (rclpy is containerized).
"""

from __future__ import annotations

import asyncio
import os
import threading
from collections.abc import Awaitable, Callable
from typing import Any

try:  # pragma: no cover - availability varies by environment
    import rclpy  # noqa: F401

    _HAS_RCLPY = True
except ImportError:  # pragma: no cover
    _HAS_RCLPY = False

EventCallback = Callable[[dict[str, Any]], Awaitable[None] | None]


class ROSBridge:
    """Runs an rclpy spin loop in a background thread when available."""

    def __init__(self, node_name: str = "fleet_bridge", domain_id: int = 42) -> None:
        self._node_name = node_name
        self._domain_id = domain_id
        self._node: Any | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._subscriptions: list[Any] = []
        self._publishers: dict[str, Any] = {}
        self._handlers: dict[str, EventCallback] = {}

    @property
    def is_available(self) -> bool:
        """True when rclpy is importable (ROS 2 environment present)."""
        return _HAS_RCLPY

    @property
    def is_running(self) -> bool:
        """True once start() has initialized rclpy and the spin loop."""
        return self._running

    def start(self) -> bool:
        """Initialize rclpy and start the spin thread. Returns False when rclpy
        is unavailable or the bridge is already running."""
        if not _HAS_RCLPY or self._running:
            return False
        os.environ.setdefault("ROS_DOMAIN_ID", str(self._domain_id))
        rclpy.init()
        self._node = rclpy.create_node(self._node_name)
        self._loop = asyncio.get_event_loop()
        self._running = True
        self._thread = threading.Thread(target=self._spin, name="ros-bridge", daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        """Shut down rclpy and join the spin thread."""
        if not self._running:
            return
        self._running = False
        if self._node is not None:
            self._node.destroy_node()
            self._node = None
        if _HAS_RCLPY and rclpy.ok():
            rclpy.shutdown()
        self._thread = None

    def subscribe(self, topic: str, msg_type: Any, callback: EventCallback) -> bool:
        """Register a subscription whose callback is marshalled onto the
        asyncio loop. Returns False when the bridge is not running."""
        if not self._running or self._node is None:
            return False
        self._handlers[topic] = callback
        self._subscriptions.append(
            self._node.create_subscription(msg_type, topic, self._dispatch_factory(topic), 1)
        )
        return True

    def publish(self, topic: str, msg_type: Any, payload: Any) -> bool:
        """Publish a message. Returns False when the bridge is not running."""
        if not self._running or self._node is None:
            return False
        publisher = self._publishers.get(topic)
        if publisher is None:
            publisher = self._node.create_publisher(msg_type, topic, 1)
            self._publishers[topic] = publisher
        publisher.publish(payload)
        return True

    def _dispatch_factory(self, topic: str) -> Callable[[Any], None]:
        handler = self._handlers[topic]

        async def _invoke(msg: Any) -> None:
            outcome = handler({"topic": topic, "msg": msg})
            if outcome is not None:
                await outcome

        def dispatch(msg: Any) -> None:
            loop = self._loop
            if loop is None or not loop.is_running():
                return
            asyncio.run_coroutine_threadsafe(_invoke(msg), loop)

        return dispatch

    def _spin(self) -> None:
        while self._running:
            rclpy.spin_once(self._node, timeout_sec=0.05)
