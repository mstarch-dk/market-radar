"""Study reports that production code reads, as typed contracts with one loader: a model per report for the parts
that are consumed, under a common header (`Header`), written by `write` and read by `load`.

The design: docs/architecture.md, *Study reports*.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Generic, Literal, TypeVar

import pandas as pd
from pydantic import BaseModel, ConfigDict, ValidationError

from ..config import write_text
from ..jsonsafe import dumps
from ..paths import REPORTS

SCHEMA_VERSION = 1
HEADER = ("schema_version", "kind", "created", "data_asof", "rule_hash")


class _Open(BaseModel):
    """The consumed fields typed; everything else in the report kept as it is."""
    model_config = ConfigDict(extra="allow")


class Header(_Open):
    """Every consumed report's header. `schema_version`: `SCHEMA_VERSION` when it was written; `kind`: the
    report's name (a key of `ARTIFACTS`); `created`: when the study ran (local time, as `generated`); `data_asof`:
    the last day of data the study saw (prices' last session, or the long histories' last month-end); `rule_hash`:
    the rule the study tested, where a rule can change under it (the proposal rule's settings hash)."""
    schema_version: int
    kind: str
    created: datetime
    data_asof: date | None
    rule_hash: str | None = None


# ---------------- the rule study (backtest/propose_study.py) ----------------

class Summary(_Open):
    """One split of a study's results across formation dates."""
    dates: int | None = None
    mean: float | None = None
    gross_mean: float | None = None
    t: float | None = None
    effective_n: float | None = None
    hit: float | None = None
    dd_median: float | None = None
    dd_p10: float | None = None
    vs_kept_mean: float | None = None


class Split(_Open):
    all: Summary | None = None
    holdout: Summary | None = None
    by_regime: dict[str, Summary | None] = {}


class ProposeCell(_Open):
    kept: Split | None = None
    exits: Split | None = None


class StudyUniverse(_Open):
    first: str | None = None
    last: str | None = None
    dates: int | None = None
    tickers: int | None = None
    fund_names: int | None = None


class IC(_Open):
    mean: float | None = None
    t: float | None = None
    dates: int | None = None


class ProposeStudy(Header):
    rule_hash: str
    asof: str | None = None
    universe: StudyUniverse = StudyUniverse()
    us_only: dict[str, bool] = {}
    results: dict[str, dict[str, dict[str, ProposeCell]]]     # tilt → basket size → horizon (months)
    ic: dict[str, IC] = {}
    cost_bps: float | None = None
    holdout_from: str | None = None
    caveats: list[str] = []


# ---------------- the long-run study (backtest/longrun.py) ----------------

class Window(_Open):
    first: date | None = None
    last: date | None = None


class Survivorship(_Open):
    implied_haircut: float | None = None
    configured_haircut: float | None = None
    window: Window = Window()
    study_top_quintile_excess_1m: float | None = None
    survivorship_free_same_months: float | None = None
    survivorship_free_since_1927: float | None = None
    note: str | None = None


class Verdict(_Open):
    label: str | None = None
    why: list[str] = []


class StudySettings(_Open):
    """What a study ran with (the fields a reader shows)."""
    holdout_from: str | None = None
    n_top: int | None = None
    fee_bps: float | None = None
    park: str | None = None
    cost_per_6m: float | None = None
    dd_cut: float | None = None
    trend: bool | None = None
    cooldown: int | None = None
    buffer: int | None = None
    rf: str | None = None


class Labelled(_Open):
    key: str
    label: str | None = None


class LongrunSummary(_Open):
    dates: int | None = None
    eff_n: float | None = None
    ic_mean: float | None = None
    ic_t: float | None = None
    spread: float | None = None
    spread_t: float | None = None
    top_excess: float | None = None
    top_excess_t: float | None = None
    top_vs_market: float | None = None


class LongrunVariant(_Open):
    all: LongrunSummary | None = None
    holdout: LongrunSummary | None = None
    by_decade: dict[str, LongrunSummary | None] = {}
    by_trend: dict[str, LongrunSummary | None] = {}
    by_recession: dict[str, LongrunSummary | None] = {}


class LongrunPanel(_Open):
    label: str | None = None
    members: int | None = None
    n_top: int | None = None
    months: int | None = None
    first: date | None = None
    last: date | None = None
    variants_tried: int | None = None
    results: dict[str, dict[str, LongrunVariant]] = {}       # horizon → variant
    verdicts: dict[str, dict[str, Verdict]] = {}


class Rolling(_Open):
    share_negative: float | None = None


class Drawdown(_Open):
    max: float | None = None
    peak: date | None = None
    months_to_recover: int | None = None


class BaseRate(_Open):
    first: date | None = None
    last: date | None = None
    ann_return: float | None = None
    t: float | None = None
    last_10y_ann: float | None = None
    roll6: Rolling = Rolling()
    roll12: Rolling = Rolling()
    drawdown: Drawdown = Drawdown()


class LongrunStudy(Header):
    survivorship: Survivorship | None = None
    datasets_asof: dict[str, str] = {}
    settings: StudySettings = StudySettings()
    panels: dict[str, LongrunPanel] = {}
    errors: dict[str, str] = {}
    base_rates: dict[str, BaseRate | None] = {}
    caveats: list[str] = []


# ---------------- the score study (backtest/study.py) ----------------

class ScoreSummary(_Open):
    dates: int | None = None
    q: list[float | None] | None = None
    ic_mean: float | None = None
    ic_t: float | None = None
    ic_pos: float | None = None
    spread: float | None = None
    spread_t: float | None = None
    top_excess: float | None = None
    top_hit: float | None = None
    top_dkk: float | None = None
    acwi_dkk: float | None = None
    top_beats_acwi: float | None = None


class ScoreVariant(_Open):
    all: ScoreSummary | None = None
    holdout: ScoreSummary | None = None
    by_regime: dict[str, ScoreSummary | None] = {}
    by_group: dict[str, ScoreSummary | None] = {}


class VariantInfo(_Open):
    key: str
    baseline: bool = False
    pit: bool = True


class MomentumCorr(_Open):
    mean: float | None = None
    dates: int | None = None


class RuleVsHeld(_Open):
    """The exit rule against holding the same basket (`hold` and `both`: the baskets themselves)."""
    dates: int | None = None
    mean: float | None = None
    acwi_mean: float | None = None
    beats_acwi: float | None = None
    mean_diff: float | None = None
    t: float | None = None
    helped: float | None = None
    worst: float | None = None
    best: float | None = None
    exits_mean: float | None = None


class ScoreExits(_Open):
    n_top: int | None = None
    months: int | None = None
    fee_bps: float | None = None
    summary: dict[str, RuleVsHeld] | None = None
    inputs_missing: dict[str, float] = {}


class ScoreStudy(Header):
    signal: str = "momentum"
    universe: StudyUniverse
    results: dict[str, dict[str, ScoreVariant | None]]     # horizon → variant
    settings: StudySettings = StudySettings()
    variants: list[VariantInfo] = []
    variants_tried: int | None = None
    verdicts: dict[str, dict[str, Verdict]] = {}
    decay: dict[str, dict[str, float | None]] = {}          # variant → horizon → mean IC
    turnover: dict[str, float | None] = {}
    momentum_corr: MomentumCorr | None = None
    exits: ScoreExits | None = None
    caveats: list[str] = []


class Outcome(_Open):
    """A basket's outcome across formation dates, with the rule or held (`hold`)."""
    dates: int | None = None
    ret_mean: float | None = None
    ret_p10: float | None = None
    diff_mean: float | None = None
    diff_t: float | None = None
    helped: float | None = None
    dd_mean: float | None = None
    dd_worst: float | None = None
    exits_mean: float | None = None
    sharpe_mean: float | None = None
    sortino_mean: float | None = None
    calmar_mean: float | None = None
    ir_mean: float | None = None
    hold: Outcome | None = None


class ExitVariant(_Open):
    all: Outcome | None = None
    holdout: Outcome | None = None
    verdict: Verdict = Verdict()


class ExitStudy(Header):
    settings: StudySettings = StudySettings()
    variants: list[Labelled] = []
    results: dict[str, dict[str, ExitVariant]] = {}         # horizon → variant


class Activity(_Open):
    trades: float | None = None
    fees_pct: float | None = None


class TwinStat(_Open):
    mean: float | None = None
    t: float | None = None


class TwinSplit(_Open):
    sharpe: TwinStat | None = None


class VsTwin(_Open):
    all: TwinSplit | None = None


class RedeployArm(_Open):
    all: Outcome | None = None
    holdout: Outcome | None = None
    activity: Activity | None = None
    vs_twin: VsTwin | None = None
    verdict: Verdict | None = None


class RedeployStudy(Header):
    settings: StudySettings = StudySettings()
    arms: list[Labelled] = []
    results: dict[str, dict[str, RedeployArm]] = {}         # horizon → arm
    caveats: list[str] = []



@dataclass(frozen=True)
class Spec:
    file: str
    model: type[Header]
    command: str


ARTIFACTS: dict[str, Spec] = {
    "propose-study": Spec("propose-study.json", ProposeStudy, "radar study propose"),
    "longrun-study": Spec("longrun-study.json", LongrunStudy, "radar study longrun"),
    "score-study": Spec("score-study.json", ScoreStudy, "radar study score"),
    "exit-study": Spec("exit-study.json", ExitStudy, "radar study exits"),
    "redeploy-study": Spec("redeploy-study.json", RedeployStudy, "radar study redeploy"),
}

M = TypeVar("M", bound=Header)
Status = Literal["ok", "stale", "missing", "invalid"]


@dataclass(frozen=True)
class Loaded(Generic[M]):
    """A report as read: the model when it could be read (`ok` or `stale`), else None, and why."""
    name: str
    status: Status
    report: M | None = None
    reason: str | None = None
    legacy: bool = False           # written before the header: read as schema version 0

    @property
    def ok(self) -> bool:
        return self.status == "ok"


def _spec(name: str) -> Spec:
    if name not in ARTIFACTS:
        raise ValueError(f"unknown study report {name} (known: {', '.join(ARTIFACTS)})")
    return ARTIFACTS[name]


def path(name: str) -> Path:
    return (REPORTS / _spec(name).file).now()


def _asof(raw: dict) -> str | None:
    """A version-0 report's last day of data: `asof`, or the latest of `data_asof`'s months (the long-run study)."""
    if raw.get("asof"):
        return str(raw["asof"])
    d = raw.get("data_asof")
    if isinstance(d, dict) and d:
        return month_end(max(d.values()))
    return None


def month_end(month: str) -> str:
    """'2026-08' → '2026-08-31'."""
    return (pd.Period(month, "M").end_time.normalize()).date().isoformat()


def _upgrade(raw: dict, name: str) -> dict:
    """A report from before the header (version 0): its `generated`, `asof` / `data_asof` and `settings_hash`
    stand in for the header."""
    head = {"schema_version": 0, "kind": name, "created": raw.get("generated"), "data_asof": _asof(raw),
            "rule_hash": raw.get("settings_hash")}
    if isinstance(raw.get("data_asof"), dict):       # the long-run study's last month per dataset, now its own key
        head["datasets_asof"] = raw["data_asof"]
    return head | {k: v for k, v in raw.items() if k not in HEADER}


def _first_error(e: ValidationError) -> str:
    err = e.errors()[0]
    where = ".".join(str(x) for x in err["loc"]) or "the report"
    more = f" (and {e.error_count() - 1} more)" if e.error_count() > 1 else ""
    return f"{where}: {err['msg']}{more}"


_cache: dict = {}


def load(name: str, *, rule_hash: str | None = None) -> Loaded:
    """The report `name` (a key of `ARTIFACTS`) as its model. `rule_hash`: the rule the reader acts on; a report
    that tested another one is `stale` (its numbers are given, never acted on). Otherwise `ok`, `missing` or
    `invalid` (unreadable, another kind, a newer schema, or not matching the model), each with a reason; a report
    from before the header is `legacy`. Never a silent fallback: what a reader does without the report is its own,
    stated choice. Cached per file version."""
    spec = _spec(name)
    f = (REPORTS / spec.file).now()
    try:
        st = f.stat()
    except FileNotFoundError:
        return Loaded(name, "missing", reason=f"no {name} yet: run `{spec.command}`")
    key = (str(f), st.st_mtime_ns, st.st_size)
    if _cache.get(name, (None,))[0] != key:
        _cache[name] = (key, _read(name, spec, f))
    got = _cache[name][1]
    if got.report is None or rule_hash is None or got.report.rule_hash == rule_hash:
        return got
    return Loaded(name, "stale", got.report, f"{name} tested another rule (settings {got.report.rule_hash}, "
                  f"today's {rule_hash}): run `{spec.command}` again", got.legacy)


def _read(name: str, spec: Spec, f: Path) -> Loaded:
    try:
        raw = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return Loaded(name, "invalid", reason=f"{f.name} can't be read ({e}): run `{spec.command}` again")
    if not isinstance(raw, dict):
        return Loaded(name, "invalid", reason=f"{f.name} is not a report: run `{spec.command}` again")
    legacy = "schema_version" not in raw
    if legacy:
        raw = _upgrade(raw, name)
    v = raw.get("schema_version")
    if isinstance(v, int) and v > SCHEMA_VERSION:
        return Loaded(name, "invalid", reason=f"{f.name} was written by a newer Market Radar (schema {v}, this one "
                      f"reads up to {SCHEMA_VERSION})")
    if raw.get("kind") != name:
        return Loaded(name, "invalid", reason=f"{f.name} holds a {raw.get('kind')} report, not {name}")
    try:
        rep = spec.model.model_validate(raw)
    except ValidationError as e:
        return Loaded(name, "invalid", reason=f"{f.name} doesn't match its contract ({_first_error(e)}): "
                      f"run `{spec.command}` again")
    return Loaded(name, "ok", rep, legacy=legacy)


def stamp(name: str, rep: dict, data_asof: str | None, rule_hash: str | None = None) -> dict:
    """The report with its header first (`created` is the report's `generated` time when it has one)."""
    _spec(name)
    head = {"schema_version": SCHEMA_VERSION, "kind": name,
            "created": rep.get("generated") or pd.Timestamp.now().isoformat(timespec="seconds"),
            "data_asof": data_asof, "rule_hash": rule_hash}
    return head | {k: v for k, v in rep.items() if k not in HEADER}


def write(name: str, rep: dict, *, data_asof: str | None, rule_hash: str | None = None,
          file: str | None = None) -> Header:
    """Stamp, check against the contract, then write `rep` to the reports folder (as `file` when the same contract
    is written under another name, e.g. score-study-<signal>.json). Returns the report as its model, as a reader
    gets it. Raises when the report breaks the contract, so a writer can't put out a report its readers can't
    read."""
    spec = _spec(name)
    text = dumps(stamp(name, rep, data_asof, rule_hash), indent=1)
    try:
        checked = spec.model.model_validate(json.loads(text))
    except ValidationError as e:
        raise ValueError(f"{name} doesn't match its contract, not written: {_first_error(e)}") from e
    REPORTS.mkdir(parents=True, exist_ok=True)
    f = (REPORTS / (file or spec.file)).now()
    write_text(f, text)
    return checked
