from __future__ import annotations

from pathlib import Path

from connectctl.metrics.loc import (
    calc_loc_stats,
    count_sloc,
    is_test_python_file,
    iter_py_files,
)


def test_count_sloc_excludes_blank_and_comment_only_lines() -> None:
    text = """
# module comment

x = 1
y = 2  # inline comment stays code

\"\"\"module docstring\"\"\"
"""

    assert count_sloc(text) == 3


def test_is_test_python_file_matches_repo_test_conventions() -> None:
    assert is_test_python_file(Path("tests/test_example.py")) is True
    assert is_test_python_file(Path("pkg/tests/helpers.py")) is True
    assert is_test_python_file(Path("tests/conftest.py")) is True
    assert is_test_python_file(Path("pkg/conftest.py")) is True
    assert is_test_python_file(Path("pkg/test_helpers.py")) is True
    assert is_test_python_file(Path("connectctl/services/export/service.py")) is False


def test_iter_py_files_ignores_local_test_virtualenvs(tmp_path: Path) -> None:
    tracked = tmp_path / "connectctl" / "sample.py"
    tracked.parent.mkdir(parents=True, exist_ok=True)
    tracked.write_text("VALUE = 1\n", encoding="utf-8")

    ignored = tmp_path / ".test_venv_bkkt" / "lib" / "site.py"
    ignored.parent.mkdir(parents=True, exist_ok=True)
    ignored.write_text("VALUE = 2\n", encoding="utf-8")

    files = {p.relative_to(tmp_path).as_posix() for p in iter_py_files(tmp_path)}
    assert "connectctl/sample.py" in files
    assert ".test_venv_bkkt/lib/site.py" not in files


def test_calc_loc_stats_breaks_min_max_ties_by_path(tmp_path: Path) -> None:
    """Keep generated metrics stable across filesystem traversal order."""

    empty_b = tmp_path / "b_empty.py"
    empty_a = tmp_path / "a_empty.py"
    largest_z = tmp_path / "z_largest.py"
    largest_c = tmp_path / "c_largest.py"

    empty_b.write_text("", encoding="utf-8")
    empty_a.write_text("", encoding="utf-8")
    largest_z.write_text("A = 1\nB = 2\n", encoding="utf-8")
    largest_c.write_text("A = 1\nB = 2\n", encoding="utf-8")

    stats = calc_loc_stats(
        [empty_b, largest_z, largest_c, empty_a],
        root=tmp_path,
        top_n=10,
    )

    assert stats.min_lines == 0
    assert stats.min_path == "a_empty.py"
    assert stats.max_lines == 2
    assert stats.max_path == "c_largest.py"
