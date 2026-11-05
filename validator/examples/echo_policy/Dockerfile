# Dockerfile — deterministic echo policy container (validator sandbox fixture).
# Build:  docker build -t konnex-echo-policy validator/examples/echo_policy
# Run:    KONNEX_POLICY_IMAGE=konnex-echo-policy make verify-consensus
FROM python:3.11-slim

WORKDIR /policy

# No dependencies beyond the standard library: the sandbox runs with
# --network none and --read-only, so the image must work fully offline.
COPY weights.py policy_server.py ./

# Unbuffered so the JSON-lines transport is not delayed by pipe buffering.
ENV PYTHONUNBUFFERED=1

CMD ["python", "policy_server.py"]
