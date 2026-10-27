"""Your trading rules as the app and the skills see them: the kinds and templates from config/rules.yaml, and a
rule as it may be stored (validate). Checking an action against them is rulecheck.py; the store is
userstore/rulestore.py.

The rules are yours and a mirror, never a gate: every output that carries them says so (DISCLAIMER)."""
from __future__ import annotations

from functools import cache
from typing import Any

from . import market_views, userstore
from .config import load_yaml
from .errors import Invalid

DISCLAIMER = ("These are your own rules, checked against the radar's data: a mirror, never a gate. Nothing is "
              "blocked or sent anywhere, and a verdict is not advice to trade or not to trade. Unknown never "
              "means complies.")
SEVERITIES = ("hard", "soft", "reminder")
STATUSES = ("active", "archived")
EXPOSURE_KINDS = ("etf", "sector", "industry", "region", "ticker")
NUMBER_TYPES = ("pct", "dkk", "int", "days")


@cache
def config() -> dict:
    return load_yaml("rules.yaml")


def kinds() -> dict[str, dict]:
    return config()["kinds"]


def near_band(kind: str) -> float:
    return float(kinds()[kind].get("near", config()["near"]))


def _number(key: str, spec: dict, v: Any) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v:
        raise Invalid(f"{spec.get('label', key)} must be a number.")
    if not spec.get("min", float("-inf")) <= v <= spec.get("max", float("inf")):
        raise Invalid(f"{spec.get('label', key)} must be between {spec['min']:g} and {spec['max']:g}.")
    return int(v) if spec["type"] in ("int", "days") else float(v)


def _param(key: str, spec: dict, v: Any) -> Any:
    t = spec["type"]
    if t in NUMBER_TYPES:
        return _number(key, spec, v)
    if t == "choice":
        if v not in spec["choices"]:
            raise Invalid(f"{spec.get('label', key)} must be one of {', '.join(map(str, spec['choices']))}.")
        return v
    if t == "tickers":
        out = [str(x).strip().upper() for x in v or [] if str(x).strip()] if isinstance(v, list) else []
        if not out:
            raise Invalid(f"{spec.get('label', key)}: name at least one ticker.")
        return list(dict.fromkeys(out))
    if t == "exposures":
        exps: list[dict] = []
        for e in v if isinstance(v, list) else []:
            if not isinstance(e, dict) or e.get("kind") not in EXPOSURE_KINDS or not str(e.get("key") or "").strip():
                raise Invalid(f"{spec.get('label', key)}: each entry needs a kind ({', '.join(EXPOSURE_KINDS)}) "
                              "and a key.")
            key_ = str(e["key"]).strip()
            exps.append({"kind": e["kind"], "key": key_.upper() if e["kind"] in ("etf", "ticker") else key_})
        if not exps:
            raise Invalid(f"{spec.get('label', key)}: name at least one exposure.")
        return exps
    raise ValueError(f"unknown parameter type {t!r} in config/rules.yaml")


def _scope(scope: dict | None) -> dict:
    s = dict(scope or {"portfolios": "real"})
    unknown = set(s) - {"portfolios", "kind", "tag", "style"}
    if unknown:
        raise Invalid(f"Unknown scope field: {', '.join(sorted(unknown))}.")
    p = s.get("portfolios", "real")
    if isinstance(p, list):
        ids = [int(x) for x in p]
        missing = [i for i in ids if not userstore.get_portfolio(i)]
        if not ids or missing:
            raise Invalid(f"No portfolio {missing[0]}." if missing else "Choose at least one portfolio.")
        s["portfolios"] = ids
    elif p not in ("real", "all"):
        raise Invalid("The scope's portfolios are real, all or a list of portfolio ids.")
    else:
        s["portfolios"] = p
    if s.get("kind") is not None and s["kind"] not in userstore.PORTFOLIO_KINDS:
        raise Invalid(f"Account kind must be one of {', '.join(userstore.PORTFOLIO_KINDS)}.")
    if s.get("style") is not None and s["style"] not in config()["styles"]:
        raise Invalid(f"Style must be one of {', '.join(config()['styles'])}.")
    if s.get("tag") is not None:
        s["tag"] = userstore.norm_tag(s["tag"]) or None
    return {k: v for k, v in s.items() if v is not None}


def validate(rule: dict) -> dict:
    """A rule as it can be stored: a statement (trimmed), a known kind with its parameters in range (defaults
    filled in), a resolvable scope and a known severity; Invalid naming the first problem. The app's add, edit
    and restore and `radar rules add` all go through it."""
    r = dict(rule, statement=(rule.get("statement") or "").strip())
    if not r["statement"]:
        raise Invalid("A rule needs a statement, in your own words.")
    kind = r.get("kind")
    if kind not in kinds():
        raise Invalid(f"Unknown rule kind {kind!r}: one of {', '.join(kinds())}.")
    schema = kinds()[kind].get("params") or {}
    given = dict(r.get("params") or {})
    extra = set(given) - set(schema)
    if extra:
        raise Invalid(f"{kinds()[kind]['label']} has no parameter {', '.join(sorted(extra))}.")
    params = {}
    for key, spec in schema.items():
        v = given.get(key, spec.get("default"))
        if v is None:
            raise Invalid(f"{spec.get('label', key)} is missing.")
        params[key] = _param(key, spec, v)
    r["params"] = params
    r["scope"] = _scope(r.get("scope"))
    r["severity"] = r.get("severity") or "soft"
    if r["severity"] not in SEVERITIES:
        raise Invalid(f"Severity must be one of {', '.join(SEVERITIES)}.")
    r["status"] = r.get("status") or "active"
    if r["status"] not in STATUSES:
        raise Invalid("Status must be active or archived.")
    r["rationale"] = (r.get("rationale") or "").strip() or None
    return r


def templates() -> list[dict]:
    return [{"key": t["key"], "kind": t["kind"], "statement": t["statement"], "params": t.get("params") or {},
             "scope": t.get("scope") or {"portfolios": "real"}, "severity": t.get("severity", "soft"),
             "rationale": t.get("rationale")} for t in config()["templates"]]


def catalogue() -> dict:
    """What the editor offers: each kind with its parameters, the styles, horizons and severities, and the views'
    exposure vocabulary (ETFs, sectors, regions) for theme caps."""
    mv = market_views.catalogue()
    out_kinds = []
    for key, k in kinds().items():
        params = [{"key": p, "type": s["type"], "label": s.get("label", p), "min": s.get("min"), "max": s.get("max"),
                   "default": s.get("default"), "choices": s.get("choices")} for p, s in (k.get("params") or {}).items()]
        out_kinds.append({"key": key, "label": k["label"], "when": k["when"], "sides": k["sides"],
                          "needs": k.get("needs"), "params": params})
    return {"kinds": out_kinds, "styles": config()["styles"], "horizons": list(config()["horizons"]),
            "severities": list(SEVERITIES), "account_kinds": list(userstore.PORTFOLIO_KINDS),
            "exposure_kinds": list(EXPOSURE_KINDS), "etfs": mv["etfs"], "sectors": mv["sectors"],
            "regions": mv["regions"]}


def horizon_months(h: str | None) -> int | None:
    """'6m' -> 6, '3y' -> 36; None when missing or not one of the known horizons."""
    return config()["horizons"].get(str(h)) if h else None
