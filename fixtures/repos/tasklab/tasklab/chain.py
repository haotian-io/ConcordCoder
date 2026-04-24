"""file-runnable: one module calls another in the same package."""

from tasklab import helpers as H


def pipeline_value(n: int) -> int:
    """Return helpers.double(n) + 1; exercises cross-file call."""
    # CONCORD_TASK_BEGIN
    return 0
    # CONCORD_TASK_END
