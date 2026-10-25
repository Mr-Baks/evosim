"""Shared pytest configuration.

Production code opens log files through relative paths (e.g.
'logs/error_log.txt' in Command.complete). Running every test inside a throwaway
working directory
that already contains a ``logs/`` folder keeps the repository clean and
makes the suite independent of the caller's current directory.
"""
import pytest


@pytest.fixture(autouse=True)
def isolated_cwd(tmp_path, monkeypatch):
    (tmp_path / 'logs').mkdir()
    monkeypatch.chdir(tmp_path)
    yield
