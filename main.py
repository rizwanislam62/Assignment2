"""Entry point.

    python main.py --profiles data/participants.csv --sessions data/fitness_sessions.csv --output output
"""
import sys

from fitness_analyzer.app import main

if __name__ == "__main__":
    sys.exit(main())
