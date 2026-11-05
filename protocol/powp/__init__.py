"""PoPW (Proof of Physical Work) protocol package.

Provides the on-chain proof data model and serialization for evaluation artifacts.
"""

from protocol.powp.proof import ProofOfPhysicalWork
from protocol.powp.serializer import serialize_proof

__all__ = ["ProofOfPhysicalWork", "serialize_proof"]
