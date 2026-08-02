"""
Entry point.

Usage:
    python main.py --once            # run a single report right now
    python main.py --schedule "08:30"  # run daily at 08:30 local time, forever
"""
import argparse
import logging
import time

from apscheduler.schedulers.blocking import BlockingScheduler

from report import run_once

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Run a single report immediately")
    parser.add_argument("--schedule", type=str, help='Daily run time, e.g. "08:30"')
    args = parser.parse_args()

    if args.once or not args.schedule:
        path = run_once()
        print(f"Report written to: {path}")
        return

    hour, minute = map(int, args.schedule.split(":"))
    scheduler = BlockingScheduler()
    scheduler.add_job(run_once, "cron", hour=hour, minute=minute)
    print(f"Scheduled daily run at {args.schedule}. Press Ctrl+C to stop.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    main()
