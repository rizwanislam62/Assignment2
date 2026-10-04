import csv
import shutil
import tempfile
import unittest
from pathlib import Path

from fitness_analyzer.analysis import FitnessSession, SessionAnalyzer
from fitness_analyzer.app import run
from fitness_analyzer.exceptions import (DataFileError, InvalidIdentifierError,
                                         InvalidRecordError)
from fitness_analyzer.loader import CsvLoader
from fitness_analyzer.models import Participant, Reading
from fitness_analyzer.validators import (check_range, parse_number,
                                         validate_participant_id, validate_session_id)

DATA = Path(__file__).resolve().parent.parent / "data"
SESSION_HEADER = ("session_id,participant_id,timestamp,heart_rate,skin_response,"
                  "temperature,activity_level,signal_quality\n")
PROFILE_HEADER = ("participant_id,name,baseline_heart_rate,baseline_skin_response,"
                  "baseline_temperature\n")
PERSON = Participant("P001", "Test", 70, 1.0, 32.0)


def reading(t, hr=70, quality=0.9, activity=0.5, skin=1.0, temp=32.0):
    return Reading("FIT-2026-001", "P001", t, hr, skin, temp, activity, quality)


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def write(self, name, text):
        p = self.tmp / name
        p.write_text(text, encoding="utf-8", newline="")
        return p


class IdentifierTests(unittest.TestCase):
    def test_valid_ids(self):
        self.assertEqual(validate_participant_id("P001"), "P001")
        self.assertEqual(validate_session_id("FIT-2026-001"), "FIT-2026-001")

    def test_invalid_ids(self):
        for bad in ["001", "P01", "P0011", "p001", "P001\n", " P001", ""]:
            with self.assertRaises(InvalidIdentifierError):
                validate_participant_id(bad)
        for bad in ["FIT-26-102", "FIT-2026-1", "FIT-2026-0011", "REC-2026-001"]:
            with self.assertRaises(InvalidIdentifierError):
                validate_session_id(bad)

    def test_identifier_error_is_value_error(self):
        self.assertTrue(issubclass(InvalidIdentifierError, ValueError))


class NumberTests(unittest.TestCase):
    def test_boundaries_accepted(self):
        self.assertEqual(check_range("signal_quality", 0.0), 0.0)
        self.assertEqual(check_range("signal_quality", 1.0), 1.0)
        self.assertEqual(check_range("heart_rate", 30), 30)
        self.assertEqual(check_range("heart_rate", 220), 220)

    def test_just_outside_rejected(self):
        for field, value in [("signal_quality", 1.01), ("signal_quality", -0.01),
                             ("heart_rate", 29), ("heart_rate", 221), ("temperature", 55)]:
            with self.assertRaises(InvalidRecordError):
                check_range(field, value)

    def test_bad_numbers(self):
        for raw in ["", "fast", "nan", "inf"]:
            with self.assertRaises(InvalidRecordError):
                parse_number("heart_rate", raw)
        with self.assertRaises(InvalidRecordError):
            parse_number("timestamp", "1.5", integer=True)


class LoaderTests(TempDirCase):
    def participants(self):
        return CsvLoader().load_participants(DATA / "participants.csv").records

    def test_valid_files_load_cleanly(self):
        people = [p for _, p in self.participants()]
        self.assertEqual(len(people), 3)
        report = CsvLoader().load_sessions(DATA / "fitness_sessions.csv", people)
        self.assertEqual((len(report.records), len(report.rejections)), (29, 0))
        self.assertIsInstance(report.records[0][1].heart_rate, float)
        self.assertIsInstance(report.records[0][1].timestamp, int)

    def test_official_invalid_file(self):
        people = [p for _, p in self.participants()]
        report = CsvLoader().load_sessions(DATA / "fitness_sessions_invalid.csv", people)
        self.assertEqual(report.rejected_rows, 10)
        self.assertEqual(len(report.records), 1)
        fields = {(r.row_number, r.field) for r in report.rejections}
        self.assertIn((8, "participant_id"), fields)   # unknown person
        self.assertIn((12, "row"), fields)             # short row
        self.assertIn((5, "activity_level"), fields)   # missing value
        self.assertEqual(sum(1 for r in report.rejections if r.row_number == 11), 3)

    def test_missing_file(self):
        with self.assertRaises(DataFileError) as ctx:
            CsvLoader().load_participants(self.tmp / "nope.csv")
        self.assertIn("not found", str(ctx.exception))

    def test_missing_column_and_empty_file(self):
        bad = self.write("bad.csv", "participant_id,name\nP001,A\n")
        with self.assertRaises(DataFileError):
            CsvLoader().load_participants(bad)
        with self.assertRaises(DataFileError):
            CsvLoader().load_participants(self.write("empty.csv", ""))

    def test_non_utf8_file(self):
        p = self.tmp / "latin.csv"
        p.write_bytes(PROFILE_HEADER.encode() + b"P001,Ren\xe9,70,1.0,32\n")
        with self.assertRaises(DataFileError):
            CsvLoader().load_participants(p)

    def test_extra_fields_rejected(self):
        people = [p for _, p in self.participants()]
        f = self.write("s.csv", SESSION_HEADER + "FIT-2026-001,P001,0,70,1,32,0.1,0.9,extra\n")
        report = CsvLoader().load_sessions(f, people)
        self.assertEqual(len(report.records), 0)
        self.assertEqual(report.rejections[0].field, "row")

    def test_duplicate_timestamp_and_mixed_owner(self):
        people = [p for _, p in self.participants()]
        f = self.write("s.csv", SESSION_HEADER
                       + "FIT-2026-001,P001,0,70,1,32,0.1,0.9\n"
                       + "FIT-2026-001,P001,0,71,1,32,0.1,0.9\n"
                       + "FIT-2026-001,P002,1,71,1,32,0.1,0.9\n")
        report = CsvLoader().load_sessions(f, people)
        self.assertEqual(len(report.records), 1)
        self.assertEqual({r.field for r in report.rejections}, {"timestamp", "participant_id"})

    def test_boundary_values_accepted_in_file(self):
        people = [p for _, p in self.participants()]
        f = self.write("s.csv", SESSION_HEADER
                       + "FIT-2026-001,P001,0,30,0,25,0,0\n"
                       + "FIT-2026-001,P001,1,220,50,42,1,1\n")
        report = CsvLoader().load_sessions(f, people)
        self.assertEqual((len(report.records), len(report.rejections)), (2, 0))


class AnalysisTests(unittest.TestCase):
    def analyse(self, readings):
        return SessionAnalyzer().analyse(FitnessSession("FIT-2026-001", PERSON, readings))

    def test_normal(self):
        r = self.analyse([reading(t, hr=72, activity=0.1) for t in range(4)])
        self.assertEqual(r["classification"], "Normal (near baseline)")
        self.assertEqual(r["recovery"], "not applicable")

    def test_thresholds(self):
        # baseline 70: 87.5 is +25% exactly (moderate), 122.5 is +75% exactly (high)
        mod = self.analyse([reading(0, 70), reading(1, 87.5), reading(2, 70)])
        self.assertEqual(mod["classification"], "Moderate exertion")
        high = self.analyse([reading(0, 70), reading(1, 122.5), reading(2, 70)])
        self.assertEqual(high["classification"], "High exertion")
        below = self.analyse([reading(0, 70), reading(1, 87.4), reading(2, 70)])
        self.assertEqual(below["classification"], "Normal (near baseline)")

    def test_unusual_when_activity_low(self):
        r = self.analyse([reading(t, hr=110, activity=0.05) for t in range(4)])
        self.assertEqual(r["classification"], "Unusual")

    def test_recovery(self):
        good = self.analyse([reading(0, 70), reading(1, 130), reading(2, 80)])
        self.assertEqual(good["recovery"], "recovering")
        slow = self.analyse([reading(0, 70), reading(1, 130), reading(2, 125)])
        self.assertEqual(slow["recovery"], "slow recovery")
        unseen = self.analyse([reading(0, 70), reading(1, 100), reading(2, 130)])
        self.assertEqual(unseen["recovery"], "not observed")

    def test_insufficient_data(self):
        low = self.analyse([reading(t, quality=0.49) for t in range(5)])
        self.assertEqual(low["classification"], "Insufficient data")
        few = self.analyse([reading(0), reading(1)])
        self.assertEqual(few["classification"], "Insufficient data")
        mostly_bad = self.analyse([reading(0), reading(1), reading(2)]
                                  + [reading(t, quality=0.1) for t in range(3, 8)])
        self.assertEqual(mostly_bad["classification"], "Insufficient data")

    def test_quality_boundary_is_usable(self):
        r = self.analyse([reading(t, quality=0.5) for t in range(3)])
        self.assertNotEqual(r["classification"], "Insufficient data")

    def test_low_quality_readings_excluded_from_stats(self):
        r = self.analyse([reading(0, 70), reading(1, 70), reading(2, 70),
                          reading(3, 200, quality=0.1)])
        self.assertEqual(r["peak_heart_rate"], 70)


class EndToEndTests(TempDirCase):
    def test_full_run_creates_outputs_and_is_repeatable(self):
        out_dir = self.tmp / "nested" / "output"
        sessions = [DATA / "fitness_sessions.csv", DATA / "fitness_sessions_invalid.csv"]
        messages = []
        self.assertEqual(run(DATA / "participants.csv", sessions, out_dir, out=messages.append), 0)
        names = {"analysis_summary.csv", "analysis_report.txt", "rejected_records.txt"}
        self.assertEqual({p.name for p in out_dir.iterdir()}, names)
        first = {n: (out_dir / n).read_bytes() for n in names}
        run(DATA / "participants.csv", sessions, out_dir, out=lambda m: None)
        self.assertEqual(first, {n: (out_dir / n).read_bytes() for n in names})
        with open(out_dir / "analysis_summary.csv", encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 6)

    def test_missing_session_file_is_skipped(self):
        messages = []
        code = run(DATA / "participants.csv",
                   [self.tmp / "missing.csv", DATA / "fitness_sessions.csv"],
                   self.tmp / "o", out=messages.append)
        self.assertEqual(code, 1)
        self.assertTrue(any("not found" in m for m in messages))
        self.assertTrue((self.tmp / "o" / "analysis_summary.csv").exists())

    def test_missing_profile_file_is_fatal(self):
        code = run(self.tmp / "missing.csv", [DATA / "fitness_sessions.csv"],
                   self.tmp / "o", out=lambda m: None)
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
