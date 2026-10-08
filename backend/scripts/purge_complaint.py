#!/usr/bin/env python3
"""CLI retention helper: delete a complaint + its events + photo files.

Usage:
    cd backend
    .venv/bin/python scripts/purge_complaint.py 7

Suggested retention (see README): purge resolved/confirmed complaints
older than ~90 days, e.g. from a weekly cron job.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal  # noqa: E402
from app.api.admin import delete_complaint_completely  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        print(__doc__)
        return 2
    complaint_id = int(sys.argv[1])
    db = SessionLocal()
    try:
        files = delete_complaint_completely(db, complaint_id)
        print(f"Deleted complaint {complaint_id} and {files} photo file(s).")
        return 0
    except Exception as e:  # includes the FastAPI 404 for missing ids
        print(f"Error: {e}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
