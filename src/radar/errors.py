"""What the domain raises when a request can't be done as asked: something missing, a clash with what is stored,
or input that isn't valid (with the issues, field by field). The API answers each with its HTTP status and one
shape, `{"detail": {"message", "issues"}}` (api/app.py, one handler); the CLI prints the message. They are
ValueErrors, so code that catches ValueError keeps working."""
from __future__ import annotations


class RadarError(ValueError):
    status = 400

    def __init__(self, message: str, issues: list[dict] | None = None):
        super().__init__(message)
        self.message = message
        self.issues = issues or []


class Unreadable(RadarError):
    """A file that can't be read as what it claims to be."""
    status = 400


class NotFound(RadarError):
    """What was asked for isn't there."""
    status = 404


class Conflict(RadarError):
    """It clashes with what is stored (a name taken, rows that would be lost, something already running)."""
    status = 409


class Invalid(RadarError):
    """The input breaks a rule; `issues` lists them (field, level, message) when there are several."""
    status = 422
