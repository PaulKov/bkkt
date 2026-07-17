from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional


try:
    # kafka-python provides AbstractTokenProvider for SASL/OAUTHBEARER.
    from kafka.sasl.oauth import AbstractTokenProvider

    _KAFKA_PYTHON_AVAILABLE = True
except Exception:  # pragma: no cover
    # Keep module importable even if optional dependency is missing.
    # We raise a clear error when the provider is actually instantiated.
    AbstractTokenProvider = object
    _KAFKA_PYTHON_AVAILABLE = False


@dataclass
class CachedToken:
    token: str
    expires_at_epoch_s: float


class AwsMskIamTokenProvider(AbstractTokenProvider):
    """SASL/OAUTHBEARER token provider for Amazon MSK IAM.

    Uses the official AWS helper library `aws-msk-iam-sasl-signer-python`.
    The helper generates a signed URL-based token based on AWS credentials
    available in the environment (default credentials chain).

    Notes:
    - This provider is primarily used via :class:`connectctl.kafka.metrics.KafkaMetricsClient`.
    - The module is designed to be importable even when optional dependencies are not installed.
    """

    def __init__(
        self,
        *,
        region: str,
        aws_profile: Optional[str] = None,
        refresh_skew_s: int = 60,
    ):
        if not _KAFKA_PYTHON_AVAILABLE:
            raise RuntimeError(
                "kafka-python is required for IAM auth token provider. "
                "Install it with: pip install kafka-python"
            )

        self.region = region
        self.aws_profile = aws_profile
        self.refresh_skew_s = int(refresh_skew_s)
        self._cached: Optional[CachedToken] = None

    def _generate(self) -> CachedToken:
        try:
            from aws_msk_iam_sasl_signer import MSKAuthTokenProvider
        except Exception as e:
            raise RuntimeError(
                "aws-msk-iam-sasl-signer-python is required for IAM auth. "
                "Install it with: pip install aws-msk-iam-sasl-signer-python"
            ) from e

        # The library supports the default credential chain. Named profiles are also supported,
        # but kafka-python doesn't provide a direct way to pass a boto session, so the
        # most compatible approach is to rely on AWS_PROFILE env var. We set it only
        # if the caller explicitly requests it.
        if self.aws_profile:
            import os

            os.environ.setdefault("AWS_PROFILE", self.aws_profile)

        token, expiry_ms = MSKAuthTokenProvider.generate_auth_token(self.region)

        # expiry returned by the lib is typically in milliseconds from epoch
        # (or may be None in old versions).
        expires_at = time.time() + 15 * 60
        try:
            if expiry_ms:
                expires_at = float(expiry_ms) / 1000.0
        except Exception:
            pass

        return CachedToken(token=str(token), expires_at_epoch_s=expires_at)

    def token(self) -> str:
        # kafka-python calls token() repeatedly; cache to avoid generating on every request.
        now = time.time()
        if (
            self._cached
            and (self._cached.expires_at_epoch_s - self.refresh_skew_s) > now
        ):
            return self._cached.token

        self._cached = self._generate()
        return self._cached.token
