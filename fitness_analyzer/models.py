"""Domain objects."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Participant:
    participant_id: str
    name: str
    baseline_heart_rate: float
    baseline_skin_response: float
    baseline_temperature: float


@dataclass(frozen=True)
class Reading:
    session_id: str
    participant_id: str
    timestamp: int
    heart_rate: float
    skin_response: float
    temperature: float
    activity_level: float
    signal_quality: float


@dataclass(frozen=True)
class Rejection:
    """One rejected field of one rejected row."""
    source: str
    row_number: int
    field: str
    reason: str


@dataclass
class LoadReport:
    """Everything produced by loading one file."""
    source: str
    records: list = field(default_factory=list)
    rejections: list = field(default_factory=list)
    rows_read: int = 0

    @property
    def rejected_rows(self):
        return len({r.row_number for r in self.rejections})
