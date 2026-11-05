"""Payment-layer exception types.

Kept in their own module so providers, the service, and the backend facade
can all raise/ catch the same errors without circular imports.
"""

from __future__ import annotations


class PaymentProviderError(RuntimeError):
    """A Circle/Arc provider operation failed (HTTP, RPC, or chain error).

    Subclasses RuntimeError so the payments router's existing
    `except (ValueError, RuntimeError)` handler surfaces it as HTTP 422.
    """


class PaymentProviderConfigError(ValueError):
    """Required provider configuration is missing or invalid.

    Raised at construction time (never on a per-request path) so a misconfigured
    PAYMENT_PROVIDER=real deployment fails loudly at startup instead of
    silently falling back to mock data.
    """
