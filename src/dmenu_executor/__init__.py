from __future__ import annotations

import argparse
import logging
from pathlib import Path

__arg_dest_level = "logging_level"
__arg_dest_formatter = "logging_formatter"
__arg_default_level = "WARNING"
__arg_default_formatter = "default"


def setup_logging(args: argparse.Namespace) -> None:
    _level = None
    _formatter = None
    _level = getattr(args, __arg_dest_level, __arg_default_level)
    if _level is None:
        _level = __arg_default_level
    logging.basicConfig(
        level=_level,
        format=r"[%(asctime)s] %(levelname)-8s | %(name)-40s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def add_logging_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--log-level",
        dest=__arg_dest_level,
        default=__arg_default_level,
        choices=("CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"),
        help="Logging level to be used by the logging library.",
    )


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("entry_file", type=Path)
    add_logging_args(parser=parser)
    return parser.parse_args()


def main():
    args = get_args()
    setup_logging(args=args)
    print("Hello World")
