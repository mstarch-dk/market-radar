"""`python -m radar`: the same command line as `radar` (the app runs the studies this way, studyrun.py)."""
from .cli import app

if __name__ == "__main__":
    app(prog_name="radar")
