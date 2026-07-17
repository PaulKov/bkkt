class ConnectCtlError(Exception):
    """Base error for connectctl."""


class ConfigError(ConnectCtlError):
    """Config file / settings error."""


class RepoLayoutError(ConnectCtlError):
    """Repository layout / connector path parsing error."""


class RenderError(ConnectCtlError):
    """Failed to render a connector manifest."""


class ValidationError(ConnectCtlError):
    """Connector validation error (naming rules, required fields, etc.)."""


class LifecycleDisabledError(ValidationError):
    """The manifest is intentionally disabled via connectctl.lifecycle."""


class TagConflictError(ValidationError):
    """Conflicting tag-derived parameters for a connector."""


class ConnectApiError(ConnectCtlError):
    """Kafka Connect REST API failure."""


class GitError(ConnectCtlError):
    """Git invocation/diff error."""


class KafkaMetricsError(ConnectCtlError):
    """Kafka metrics collection error."""
