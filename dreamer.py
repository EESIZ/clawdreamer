#!/usr/bin/env python3
"""Dreamer: Neuroscience-inspired memory consolidation.

Runs NREM -> REM -> Dream Log, like a sleeping brain.

Usage:
    python3 dreamer.py              # full dream cycle
    python3 dreamer.py --nrem-only  # just NREM phase
    python3 dreamer.py --dry-run    # preview without writing
"""

import argparse
import json
import logging
import sys
import time

from dream_log import write_dream_log
from nrem import run_nrem
from rem import run_rem

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("dreamer")


def main():
    parser = argparse.ArgumentParser(description="Dreamer -- AI memory consolidation")
    parser.add_argument("--nrem-only", action="store_true",
                        help="Run only NREM phase (episode -> semantic)")
    parser.add_argument("--rem-only", action="store_true",
                        help="Run only REM phase (decay + pruning)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview mode: log actions without writing to DB")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable debug logging")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.dry_run:
        log.warning("=== DRY RUN MODE -- no changes will be written ===")
        log.error("Dry-run not yet implemented")
        sys.exit(1)

    log.info("=" * 60)
    log.info("Dreamer starting...")
    log.info("=" * 60)

    start = time.time()

    # Phase 1: NREM
    if not args.rem_only:
        log.info("")
        log.info("Phase 1: NREM (Episode -> Semantic)")
        log.info("-" * 40)
        nrem_result = run_nrem()
    else:
        nrem_result = {
            "episodes": 0, "chunks": 0, "clusters": 0,
            "created": 0, "skipped_dup": 0, "processed_dates": [],
            "created_ids": [],
        }

    # Phase 2: REM
    if not args.nrem_only:
        log.info("")
        log.info("Phase 2: REM (Integration + Pruning)")
        log.info("-" * 40)
        rem_result = run_rem(nrem_result)
    else:
        rem_result = {
            "total_memories": 0, "conflicts_found": 0, "merged": 0,
            "consolidated": 0, "deleted": 0, "split_created": 0,
            "decayed": 0, "soft_deleted": 0, "archived": 0,
        }

    # Phase 3: Dream Log
    log.info("")
    log.info("Phase 3: Dream Log")
    log.info("-" * 40)
    log_path = write_dream_log(nrem_result, rem_result)

    elapsed = time.time() - start

    log.info("")
    log.info("=" * 60)
    log.info("Dream cycle complete. (%.1fs)", elapsed)
    log.info("Dream log: %s", log_path)
    log.info("=" * 60)

    # Print summary to stdout for cron log capture
    summary = {
        "nrem": nrem_result,
        "rem": rem_result,
        "dream_log": log_path,
        "elapsed_seconds": round(elapsed, 1),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
