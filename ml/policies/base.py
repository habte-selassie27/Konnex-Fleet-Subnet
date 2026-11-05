"""FleetPolicy Protocol — every policy (baseline or RL) implements this.

Status: STUB — interface defined (SYSTEM_PROMPT.md §3.3), implementation pending.

Contract:
    def assign(self, fleet_state: FleetState, tasks: list[Task]) -> list[Assignment]: ...
    def step(self, obs: dict[str, Observation]) -> dict[str, Action]: ...
    def reset(self) -> None: ...

No policy may directly command a robot or read simulator internals.
"""
