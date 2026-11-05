"""Fleet orchestration — orchestrator, mission manager, allocators, collision, failure.

Status: COMPLETE (Phases 2/5).
Components:
    - FleetOrchestrator: central coordination loop
    - MissionManager: task lifecycle tracking
    - TaskAllocator variants: nearest, hungarian, cost_optimizer
    - CollisionMonitor: robot-robot collision detection
    - CollisionAvoidance: velocity scaling to prevent collisions
    - FailureDetector: battery, stuck, comm loss, nav failure
    - CommunicationModel: latency + packet loss simulation
"""
