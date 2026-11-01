import argparse
import logging

from dotenv import load_dotenv

from reminders import default_database_path, run_worker, smtp_config_from_environment


def main():
    parser = argparse.ArgumentParser(
        description="Send scheduled LifeLog AI task reminders by email."
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Seconds between reminder checks (default: 60).",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Check and send currently due reminders once, then exit.",
    )
    arguments = parser.parse_args()

    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    smtp_config = smtp_config_from_environment()
    run_worker(
        default_database_path(),
        smtp_config,
        interval_seconds=arguments.interval,
        once=arguments.once,
    )


if __name__ == "__main__":
    main()
