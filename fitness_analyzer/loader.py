"""CSV loading: files -> typed records plus a list of rejections."""
import csv
from pathlib import Path

from .exceptions import DataFileError, InvalidIdentifierError, InvalidRecordError
from .models import LoadReport, Participant, Reading, Rejection
from .validators import (check_range, parse_number, validate_participant_id,
                         validate_session_id)

PARTICIPANT_COLUMNS = ["participant_id", "name", "baseline_heart_rate",
                       "baseline_skin_response", "baseline_temperature"]
SESSION_COLUMNS = ["session_id", "participant_id", "timestamp", "heart_rate",
                   "skin_response", "temperature", "activity_level", "signal_quality"]


def _read_rows(path, required_columns):
    """Yield (row_number, row_list) after checking the header. Row numbers are
    file line numbers (header = line 1)."""
    path = Path(path)
    try:
        with open(path, encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            try:
                header = [h.strip() for h in next(reader)]
            except StopIteration:
                raise DataFileError(path, "file is empty") from None
            missing = [c for c in required_columns if c not in header]
            if missing:
                raise DataFileError(path, f"missing required column(s): {', '.join(missing)}")
            yield header
            for row in reader:
                if row:  # skip fully blank lines
                    yield reader.line_num, row
    except FileNotFoundError:
        raise DataFileError(path, "file not found") from None
    except PermissionError:
        raise DataFileError(path, "permission denied") from None
    except UnicodeDecodeError as exc:
        raise DataFileError(path, f"not valid UTF-8 ({exc.reason})") from None
    except csv.Error as exc:
        raise DataFileError(path, f"malformed CSV ({exc})") from None


def _row_to_dict(header, row):
    if len(row) != len(header):
        raise InvalidRecordError(
            [("row", f"expected {len(header)} fields but found {len(row)}")])
    return {name: value.strip() for name, value in zip(header, row)}


def _collect(parsers, values):
    """Run each (field, callable) and gather every problem instead of stopping at the first."""
    problems, out = [], {}
    for name, func in parsers:
        try:
            out[name] = func(values[name])
        except KeyError:
            problems.append((name, "column not present in row"))
        except InvalidIdentifierError as exc:
            problems.append((exc.field, str(exc)))
        except InvalidRecordError as exc:
            problems.extend(exc.problems)
    if problems:
        raise InvalidRecordError(problems)
    return out


def _ranged(field, integer=False):
    def parse(raw):
        value = parse_number(field, raw, integer)
        return check_range(field, value)
    return parse


def _non_empty(field):
    def parse(raw):
        if raw == "":
            raise InvalidRecordError([(field, "missing value")])
        return raw
    return parse


def _timestamp(raw):
    value = parse_number("timestamp", raw, integer=True)
    if value < 0:
        raise InvalidRecordError([("timestamp", f"{value} must not be negative")])
    return value


def parse_participant(values):
    d = _collect([
        ("participant_id", validate_participant_id),
        ("name", _non_empty("name")),
        ("baseline_heart_rate", _ranged("baseline_heart_rate")),
        ("baseline_skin_response", _ranged("baseline_skin_response")),
        ("baseline_temperature", _ranged("baseline_temperature")),
    ], values)
    return Participant(**d)


def parse_reading(values, known_participants):
    d = _collect([
        ("session_id", validate_session_id),
        ("participant_id", validate_participant_id),
        ("timestamp", _timestamp),
        ("heart_rate", _ranged("heart_rate")),
        ("skin_response", _ranged("skin_response")),
        ("temperature", _ranged("temperature")),
        ("activity_level", _ranged("activity_level")),
        ("signal_quality", _ranged("signal_quality")),
    ], values)
    if d["participant_id"] not in known_participants:
        raise InvalidRecordError(
            [("participant_id", f"unknown participant {d['participant_id']!r}")])
    return Reading(**d)


class CsvLoader:
    """Loads the participant file and session files, never aborting on a bad row."""

    def load_participants(self, path):
        return self._load(path, PARTICIPANT_COLUMNS, parse_participant, unique_key="participant_id")

    def load_sessions(self, path, participants):
        known = {p.participant_id for p in participants}
        report = self._load(path, SESSION_COLUMNS, lambda v: parse_reading(v, known))
        self._reject_conflicts(report)
        return report

    def _load(self, path, columns, parser, unique_key=None):
        report = LoadReport(source=Path(path).name)
        rows = _read_rows(path, columns)
        header = next(rows)
        seen = set()
        for row_number, row in rows:
            report.rows_read += 1
            try:
                record = parser(_row_to_dict(header, row))
                if unique_key:
                    key = getattr(record, unique_key)
                    if key in seen:
                        raise InvalidRecordError([(unique_key, f"duplicate {key!r}")])
                    seen.add(key)
            except InvalidRecordError as exc:
                for fld, reason in exc.problems:
                    report.rejections.append(Rejection(report.source, row_number, fld, reason))
                continue
            report.records.append((row_number, record))
        return report

    @staticmethod
    def _reject_conflicts(report):
        """Reject readings that contradict earlier ones in the same session:
        a different participant, or a repeated timestamp."""
        owners, stamps, kept = {}, set(), []
        for row_number, r in report.records:
            owner = owners.setdefault(r.session_id, r.participant_id)
            problem = None
            if owner != r.participant_id:
                problem = ("participant_id",
                           f"session {r.session_id} belongs to {owner}, not {r.participant_id}")
            elif (r.session_id, r.timestamp) in stamps:
                problem = ("timestamp", f"duplicate timestamp {r.timestamp} in {r.session_id}")
            if problem:
                report.rejections.append(Rejection(report.source, row_number, *problem))
            else:
                stamps.add((r.session_id, r.timestamp))
                kept.append((row_number, r))
        report.records = kept
