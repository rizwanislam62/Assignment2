"""Orchestration and command-line interface."""
import argparse
import sys
from pathlib import Path

from .analysis import FitnessSession, SessionAnalyzer
from .exceptions import DataFileError
from .loader import CsvLoader
from .reports import ReportWriter

DEFAULT_PROFILES = "data/participants.csv"
DEFAULT_SESSIONS = ["data/fitness_sessions.csv", "data/fitness_sessions_invalid.csv"]


def build_parser():
    p = argparse.ArgumentParser(description="Smart Fitness Session Analyzer")
    p.add_argument("--profiles", default=DEFAULT_PROFILES, help="participants CSV")
    p.add_argument("--sessions", nargs="+", default=DEFAULT_SESSIONS,
                   help="one or more session CSV files")
    p.add_argument("--output", default="output", help="output directory")
    return p


def run(profiles_path, session_paths, output_dir, out=print):
    """Run the whole pipeline. Returns an exit code (0 ok, 1 some files skipped, 2 fatal)."""
    loader = CsvLoader()
    try:
        profile_report = loader.load_participants(profiles_path)
    except DataFileError as exc:
        out(f"ERROR: cannot load participant profiles - {exc}")
        return 2
    if not profile_report.records:
        out("ERROR: no valid participant profiles were loaded; cannot continue.")
        return 2
    participants = {rec.participant_id: rec for _, rec in profile_report.records}

    reports, results, exit_code = [profile_report], [], 0
    analyzer = SessionAnalyzer()
    for path in session_paths:
        try:
            report = loader.load_sessions(path, participants.values())
        except DataFileError as exc:
            out(f"WARNING: skipping session file - {exc}")
            exit_code = 1
            continue
        reports.append(report)
        grouped = {}
        for _, reading in report.records:
            grouped.setdefault(reading.session_id, []).append(reading)
        for session_id in sorted(grouped):
            readings = grouped[session_id]
            session = FitnessSession(session_id, participants[readings[0].participant_id], readings)
            result = analyzer.analyse(session)
            result["source_file"] = report.source
            results.append(result)

    rejections = [rej for rep in reports for rej in rep.rejections]
    created = ReportWriter(output_dir).write_all(results, rejections, reports)

    accepted = sum(len(r.records) for r in reports)
    rejected_rows = sum(r.rejected_rows for r in reports)
    out("Completion summary")
    out(f"  Accepted rows : {accepted}")
    out(f"  Rejected rows : {rejected_rows}")
    out(f"  Sessions analysed: {len(results)}")
    out("  Files created :")
    for p in created:
        out(f"    {p}")
    return exit_code


def main(argv=None):
    args = build_parser().parse_args(argv)
    return run(Path(args.profiles), [Path(s) for s in args.sessions], Path(args.output))


if __name__ == "__main__":
    sys.exit(main())
