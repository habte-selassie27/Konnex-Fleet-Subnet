# infra/grafana/

Grafana provisioning directory (mounted read-only at `/etc/grafana/provisioning` by docker-compose).

Status: STUB — add `datasources/` and `dashboards/` provisioning YAML as monitoring comes online (Phase 2+).

Convention (AGENTS.md §5.8): all metrics carry descriptive labels — `robot_id`, `policy`, `scenario`.
