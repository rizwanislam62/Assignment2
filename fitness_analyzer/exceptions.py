"""Custom exceptions for the fitness analyzer."""


class InvalidIdentifierError(ValueError):
    """Raised when an identifier has an invalid format."""

    def __init__(self, field, value, expected):
        self.field = field
        self.value = value
        super().__init__(f"{value!r} is not a valid {field} (expected {expected})")


class InvalidRecordError(ValueError):
    """Raised when a CSV record cannot be accepted.

    `problems` is a list of (field, reason) pairs so one bad row can report
    every faulty field.
    """

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("; ".join(f"{f}: {r}" for f, r in self.problems))


class DataFileError(OSError):
    """Raised when an input file cannot be used at all (missing, unreadable, bad header)."""

    def __init__(self, path, reason):
        self.path = path
        self.reason = reason
        super().__init__(f"{path}: {reason}")
