"""The layers between the app and the studies hold (the import-linter contracts in pyproject.toml; see
docs/architecture.md, *Layers*): the kernel imports neither, the studies don't import the report builder, and
the app never imports a study."""
from pathlib import Path

from importlinter.cli import lint_imports

ROOT = Path(__file__).resolve().parents[1]


def test_the_import_contracts_hold(capsys):
    code = lint_imports(config_filename=str(ROOT / "pyproject.toml"), no_cache=True, no_logo=True)
    assert code == 0, capsys.readouterr().out
