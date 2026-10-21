#!/usr/bin/env python3
"""Run a declared judged review as forks of one shared context (the review kit's command); see review_kit/command.py."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from review_kit import command  # noqa: E402

if __name__ == "__main__":
    sys.exit(command.main())
