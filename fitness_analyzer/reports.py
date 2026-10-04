"""Writes the three output files."""
import csv
from pathlib import Path

CSV_COLUMNS = ["source_file", "session_id", "participant_id", "participant_name",
               "readings_total", "readings_usable", "classification", "recovery",
               "avg_heart_rate", "peak_heart_rate", "peak_elevation_pct", "recovery_pct",
               "skin_ratio", "temp_change", "mean_activity", "mean_signal_quality", "reasons"]


class ReportWriter:
    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)

    def write_all(self, results, rejections, load_reports):
        """Create the output directory if needed and (over)write all files.
        Returns the list of created paths."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        paths = [self._summary_csv(results), self._report_txt(results),
                 self._rejected_txt(rejections, load_reports)]
        return paths

    def _summary_csv(self, results):
        path = self.output_dir / "analysis_summary.csv"
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
            writer.writeheader()
            for r in results:
                writer.writerow({**r, "reasons": " | ".join(r["reasons"])})
        return path

    def _report_txt(self, results):
        path = self.output_dir / "analysis_report.txt"
        lines = ["SMART FITNESS SESSION ANALYSIS REPORT", "=" * 38, ""]
        for r in results:
            lines.append(f"{r['session_id']} - {r['participant_name']} ({r['participant_id']})"
                         f"   [{r['source_file']}]")
            lines.append(f"  Result  : {r['classification']}")
            lines.append(f"  Recovery: {r['recovery']}")
            lines.append(f"  Usable readings: {r['readings_usable']} of {r['readings_total']}")
            lines.append("  Why:")
            lines.extend(f"    - {reason}" for reason in r["reasons"])
            lines.append("")
        if not results:
            lines.append("No sessions could be analysed.")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines) + "\n")
        return path

    def _rejected_txt(self, rejections, load_reports):
        path = self.output_dir / "rejected_records.txt"
        lines = ["REJECTED RECORDS", "=" * 16, ""]
        for rep in load_reports:
            lines.append(f"{rep.source}: {rep.rows_read} rows read, "
                         f"{rep.rejected_rows} rejected, {len(rep.records)} accepted")
        lines.append("")
        for rej in rejections:
            lines.append(f"{rej.source} | row {rej.row_number} | field: {rej.field} | {rej.reason}")
        if not rejections:
            lines.append("No rejected records.")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines) + "\n")
        return path
