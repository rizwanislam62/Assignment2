# Smart Fitness Session Analyzer (Assignment II, Option A)

Run from this folder:

    python main.py --profiles data/participants.csv --sessions data/fitness_sessions.csv data/fitness_sessions_invalid.csv --output output

With no arguments the same official files are used. Run the tests with:

    python -m unittest discover -s tests -v

## Layout
| Module | Role |
|---|---|
| `exceptions.py` | `InvalidIdentifierError`, `InvalidRecordError`, `DataFileError` |
| `validators.py` | Regex identifier checks (`^P\d{3}$`, `^FIT-\d{4}-\d{3}$`), numeric parsing and range checks |
| `models.py` | `Participant`, `Reading`, `Rejection`, `LoadReport` |
| `loader.py` | `CsvLoader`: csv module, typed values, row-length checks, per-field rejection records |
| `analysis.py` | `FitnessSession`, `SessionAnalyzer`; rules documented in the module docstring |
| `reports.py` | `ReportWriter`: the three output files |
| `app.py` | Command line and pipeline |

## Rules
- **Signal quality:** readings below 0.5 are a data-quality issue and are excluded from all statistics (not rejected).
- **Insufficient data:** fewer than 3 usable readings, or fewer than 60% of the session, gives "Insufficient data" instead of a normal/unusual verdict.
- **Classification:** peak heart rate vs the participant's baseline: under +25% Normal, +25% to under +75% Moderate exertion, +75% or more High exertion. A 25%+ rise with mean activity under 0.30 is "Unusual".
- **Recovery:** share of the peak elevation gone by the last usable reading; 50% or more is "recovering".
- **Ranges:** heart rate 30-220, skin response 0-50, temperature 25-42 C, activity and quality 0-1.
- Rows are also rejected for a wrong field count, duplicate timestamps within a session, and a session that mixes participants.
