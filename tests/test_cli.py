#!/usr/bin/env python3
"""CLI tests for WordForge"""

import os
import pathlib
import shlex
import re
from subprocess import getstatusoutput


root_dir = pathlib.Path(__file__).resolve().parent.parent
dest_file_path: str = str(root_dir / "wordforge" / "word_forge.py")
quoted_dest_file_path: str = shlex.quote(dest_file_path)


# --------------------------------------------------
def test_exists() -> None:
    """exists"""

    assert os.path.isfile(dest_file_path)


# --------------------------------------------------
def test_usage() -> None:
    """usage"""

    for flag in ["-h", "--help"]:
        rv, out = getstatusoutput(f"{quoted_dest_file_path} {flag}")
        assert rv == 0
        assert re.match("usage", out, re.IGNORECASE)
