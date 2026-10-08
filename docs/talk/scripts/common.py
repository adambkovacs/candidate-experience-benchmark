"""Shared loader for the talk's second-pass analysis.

Run any sibling script with `python3 -I script.py` from the worktree root.
Because -I drops the script directory from sys.path, every script does
`sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))` before
`import common`.

Every run record exposed here keeps the fixed 60-review denominator.
Invalid, failed, never-sent and unknown positions stay in the denominator as
non-matches. Nothing here pools runs into model-family estimates.
"""
import json
import os
import re
from collections import Counter, defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SITE = os.path.join(ROOT, "public-site")
FIELDS = ["sentiment", "follow_up_needed", "serious_concern_reported", "testimonial_potential"]
FIELD_SHORT = {"sentiment": "sent", "follow_up_needed": "follow", "serious_concern_reported": "concern", "testimonial_potential": "testi"}
LABELS = {
    "sentiment": ["positive", "negative", "mixed", "neutral", "insufficient_information"],
    "follow_up_needed": ["yes", "no", "insufficient_information"],
    "serious_concern_reported": ["yes", "no", "insufficient_information"],
    "testimonial_potential": ["yes", "no", "insufficient_information"],
}


def load_json(rel):
    with open(os.path.join(ROOT, rel)) as f:
        return json.load(f)


def load_jsonl(rel):
    with open(os.path.join(ROOT, rel)) as f:
        return [json.loads(line) for line in f if line.strip()]


def reference():
    """Frozen proposed labels v0.2 (provisional). Returns {id: {field: label}}."""
    out = {}
    for row in load_jsonl("data/pilot/proposed_labels.jsonl"):
        out[row["id"]] = dict(row["proposed_labels"])
    return out


def inputs():
    return {r["id"]: r["feedback"] for r in load_jsonl("data/pilot/inputs.jsonl")}


def rationales():
    return {r["id"]: r.get("rationale", "") for r in load_jsonl("data/pilot/proposed_labels.jsonl")}


IDS = [f"DEV-{i:03d}" for i in range(1, 61)]


class Run:
    """One configuration-pass on the 60 reviews."""

    __slots__ = ("feed", "run_id", "model", "condition", "pass_", "effort", "provider", "surface",
                 "cases", "category", "family", "label", "scores", "tokens", "cost", "batch", "meta")

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))

    def pred(self, rid):
        c = self.cases.get(rid)
        if not c or c.get("status") not in ("ok", "valid") or not c.get("prediction"):
            return None
        p = c["prediction"]
        if any(f not in p for f in FIELDS):
            return None
        return p

    def valid_count(self):
        return sum(1 for rid in IDS if self.pred(rid) is not None)

    def all_four(self, ref):
        return sum(1 for rid in IDS if (p := self.pred(rid)) is not None and all(p[f] == ref[rid][f] for f in FIELDS))

    def field_score(self, ref, f):
        return sum(1 for rid in IDS if (p := self.pred(rid)) is not None and p[f] == ref[rid][f])

    def vector(self, rid):
        p = self.pred(rid)
        return None if p is None else tuple(p[f] for f in FIELDS)

    def __repr__(self):
        return f"Run({self.feed}:{self.run_id} {self.model} {self.condition}/{self.pass_} {self.effort})"


# ---------------------------------------------------------------------------
# Category and family classification. Decision models = purpose-built typed
# Choice/decision heads. "general" = general-purpose LLMs including local ones.
# Category overlaps are acknowledged in the repo; this is a working split only.
# ---------------------------------------------------------------------------
DECISION_PATTERNS = [
    r"jev", r"solar-decide", r"liquid/d1", r"tev1", r"clef", r"luna-decisions", r"pplx-decider",
    r"openjev", r"semif", r"laya", r"anyjev", r"kev", r"alex", r"rules",
]
NATIVE_SEVEN = {"upstage/solar-decide", "liquid/d1", "togethercomputer/tev1-4b-experimental", "cloudflare/clef",
                "cloudflare/clef-flash", "openai/gpt-6-luna-decisions", "perplexity/pplx-decider-v1-27b"}


def classify(model, run_id=""):
    m = (model or "").lower()
    r = (run_id or "").lower()
    s = m + " " + r
    if "rules" in s:
        return "rules"
    for pat in DECISION_PATTERNS:
        if re.search(pat, s):
            return "decision"
    return "general"


def family(model, run_id=""):
    s = ((model or "") + " " + (run_id or "")).lower()
    table = [
        ("jev-1.13", "jev"), ("solar", "solar"), ("liquid", "liquid"), ("tev1", "tev"), ("clef-flash", "clef-flash"),
        ("clef", "clef"), ("luna-decisions", "luna-decisions"), ("pplx", "perplexity"),
        ("alex", "alex-openjev"), ("openjev", "openjev"), ("semif", "semif"), ("laya", "laya"), ("anyjev", "anyjev"),
        ("kev", "kev"), ("rules", "rules"),
        ("claude-opus-5-5", "opus-5.5"), ("opus55", "opus-5.5"), ("claude-opus-5", "opus-5"), ("opus5", "opus-5"),
        ("claude-sonnet-5-5", "sonnet-5.5"), ("sonnet55", "sonnet-5.5"), ("claude-sonnet-5", "sonnet-5"), ("sonnet5", "sonnet-5"),
        ("fable", "fable-5.1"), ("haiku", "haiku-4.5"),
        ("gpt-5.6-luna", "gpt-5.6-luna"), ("gpt-5.6-sol", "gpt-5.6-sol"), ("gpt-5.6-terra", "gpt-5.6-terra"),
        ("gpt-6-astra", "gpt-6-astra"), ("gpt-6-luna", "gpt-6-luna"), ("gpt-6-sol", "gpt-6-sol"),
        ("gemini-3.1-pro", "gemini-3.1-pro"), ("gemini31", "gemini-3.1-pro"), ("gemini-3.6", "gemini-3.6-flash"), ("gemini36", "gemini-3.6-flash"),
        ("gemini-3.7", "gemini-3.7-flash"), ("gemini37", "gemini-3.7-flash"), ("gemini-3.8", "gemini-3.8-flash"), ("gemini38", "gemini-3.8-flash"),
        ("gemma-4-26b", "gemma-26b"), ("gemma4-26b", "gemma-26b"), ("diffusiongemma", "gemma-26b"), ("gemma-4-31b", "gemma-31b"), ("gemma4-31b", "gemma-31b"),
        ("e2b", "gemma-e2b"), ("e4b", "gemma-e4b"),
        ("qwen3.8-27b", "qwen-27b"), ("qwen27", "qwen-27b"), ("qwen3.6-35b", "qwen-35b"), ("qwen36", "qwen-35b"),
        ("qwen3-8b", "qwen-8b"), ("qwen3.5-4b", "qwen-4b"), ("qwen3-1.7b", "qwen-1.7b"), ("qwen3-0.6b", "qwen-0.6b"), ("qwen/qwen3-0.6b", "qwen-0.6b"),
        ("deepseek", "deepseek-flash"), ("mistral-small-2603", "mistral-small-4"), ("mistral", "mistral-small-3.2"),
    ]
    for pat, fam in table:
        if pat in s:
            return fam
    return m or r


def _effort_norm(e):
    if e is None:
        return "na"
    e = str(e).lower()
    if e in ("not applicable", "not_applicable", "not-applicable", "na", "none"):
        return "na"
    return e


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_data_json():
    """290 original runs with inline case vectors (public-site/data.json)."""
    d = load_json("public-site/data.json")
    by_run = defaultdict(dict)
    for c in d["cases"]:
        by_run[c["configuration"]][c["id"]] = {"status": c.get("status"), "prediction": c.get("prediction")}
    runs = []
    for r in d["runs"]:
        runs.append(Run(feed="data.json", run_id=r["id"], model=r["model"], condition=r["condition"],
                        pass_="original", effort=_effort_norm(r.get("effort")), provider=None, surface=r.get("surface"),
                        cases=by_run.get(r["id"], {}), category=classify(r["model"], r["id"]), family=family(r["model"], r["id"]),
                        label=r["id"], scores=r.get("metrics"), tokens=r.get("tokens"), cost=r.get("cost"),
                        batch=None, meta={"protocolId": r.get("protocolId"), "experimentId": r.get("experimentId"),
                                          "resultStatus": r.get("resultStatus"), "timing": r.get("timing")}))
    return runs, d


def load_extended():
    """637 repeat runs (extended-cases-v1 + extended-run-catalog-v1)."""
    cases = load_json("public-site/extended-cases-v1.json")
    cat = {r["id"]: r for r in load_json("public-site/extended-run-catalog-v1.json")["runs"]}
    runs = []
    for r in cases["runs"]:
        c = cat.get(r["runId"], {})
        runs.append(Run(feed="extended", run_id=r["runId"], model=r["model"], condition=r["condition"], pass_=r["repeatPass"],
                        effort=_effort_norm(r.get("effort")), provider=r.get("provider"), surface=r.get("surface"),
                        cases={x["id"]: x for x in r["cases"]}, category=classify(r["model"], r["runId"]),
                        family=family(r["model"], r["runId"]), label=r["sourceStage"], scores=r.get("scores"),
                        tokens=c.get("tokens"), cost=c.get("cost"), batch=None,
                        meta={"sourceStage": r["sourceStage"], "experimentId": c.get("experimentId"),
                              "protocolId": c.get("protocolId"), "sourceFamily": c.get("sourceFamily"), "timing": c.get("timing")}))
    return runs


def load_additional():
    """77 runs: 63 native decision stages, 12 Sonnet 5.5 pass1 cells, 2 Cloudflare direct."""
    d = load_json("public-site/additional-cases-v1.json")
    sup = {r["id"]: r for r in load_json("public-site/supplemental-decision-runs-v1.json")["runs"]}
    runs = []
    for r in d["runs"]:
        s = sup.get(r["runId"], {})
        runs.append(Run(feed="additional", run_id=r["runId"], model=r["model"], condition=r["condition"], pass_=r["repeatPass"],
                        effort=_effort_norm(r.get("effort")), provider=r.get("provider"), surface=r.get("surface"),
                        cases={x["id"]: x for x in r["cases"]}, category=classify(r["model"], r["runId"]),
                        family=family(r["model"], r["runId"]), label=r["sourceStage"], scores=r.get("scores"),
                        tokens=None, cost=s.get("cost"), batch=None, meta={"sourceStage": r["sourceStage"], "interface": s.get("interface")}))
    return runs


def load_all():
    """All per-case runs from the three feeds. data.json runs are the original/first passes."""
    a, _ = load_data_json()
    return a + load_extended() + load_additional()


def all_runs_by_key(runs):
    """Group runs by (family, model, effort, condition) for repeat analysis."""
    g = defaultdict(list)
    for r in runs:
        g[(r.family, r.model, r.effort, r.condition)].append(r)
    return g


# ---------------------------------------------------------------------------
# Confidence loaders. Return list of dict(model, stage, id, prediction,
# conf{field: provider confidence}, prob{field: {label: p}}).
# ---------------------------------------------------------------------------

def _rec(model, stage, rid, pred, conf, prob):
    return {"model": model, "stage": stage, "id": rid, "prediction": pred, "conf": conf, "prob": prob}


def load_confidence():
    out = []
    # Jev direct P0 (historical) and native P1/P2 variants
    for stage, rel in [("direct/P0", "results/openjev/typesafe-development-v2-reconciled.jsonl"),
                       ("direct/P1", "results/jev-native-prompt-variants-v1/P1-development.jsonl"),
                       ("direct/P2", "results/jev-native-prompt-variants-v1/P2-development.jsonl")]:
        if not os.path.exists(os.path.join(ROOT, rel)):
            continue
        for row in load_jsonl(rel):
            ans = (row.get("raw_response") or {}).get("answers") or {}
            if not ans or row.get("status") not in (None, "ok", "valid", "success"):
                if not ans:
                    continue
            pred = row.get("prediction") or {f: ans[f]["choice"] for f in FIELDS if f in ans}
            if any(f not in ans for f in FIELDS):
                continue
            out.append(_rec("jev", stage, row["id"], pred,
                            {f: ans[f].get("confidence") for f in FIELDS},
                            {f: ans[f].get("probabilities") for f in FIELDS}))
    # Solar all nine stages
    s = load_json("results/solar-decide-native-full-v1/execution-adapter-v2/all-nine.public-projection.json")
    for st in s["stages"]:
        for rec in st["records"]:
            opt = rec.get("optional") or {}
            if any(f not in opt for f in FIELDS):
                continue
            out.append(_rec("solar", st["stage"], rec["id"], rec["prediction"],
                            {f: opt[f].get("confidence") for f in FIELDS}, {f: opt[f].get("probabilities") for f in FIELDS}))
    # Tev nine stages
    t = load_json("results/tev-native-v1/full-v1/public-projection.json")
    for st in t["stages"]:
        for rec in st["records"]:
            opt = rec.get("optional") or {}
            if any(f not in opt for f in FIELDS):
                continue
            out.append(_rec("tev", st["stage"], rec["id"], rec["prediction"],
                            {f: opt[f].get("confidence") for f in FIELDS}, {f: opt[f].get("probabilities") for f in FIELDS}))
    # Liquid nine stages
    for p in ("fresh1", "fresh2", "fresh3"):
        for c in ("P0", "P1", "P2"):
            rel = f"results/liquid-d1-native-v1/full-v1/{p}/{c}/development.public.json"
            if not os.path.exists(os.path.join(ROOT, rel)):
                continue
            d = load_json(rel)
            for rec in d.get("records", []):
                ans = rec.get("answers") or {}
                if any(f not in ans for f in FIELDS):
                    continue
                out.append(_rec("liquid", f"{p}/{c}", rec["id"], rec["prediction"],
                                {f: ans[f].get("confidence") for f in FIELDS}, {f: ans[f].get("probabilities") for f in FIELDS}))
    # Clef, Clef Flash, Luna Decisions via OpenRouter: provider confidence + chosen probability only
    c = load_json("results/clef-openrouter-v1/findings-v1/public-projection.json")
    for st in c["stages"]:
        for rec in st["records"]:
            cf = rec.get("confidence") or {}
            if any(f not in cf for f in FIELDS) or not rec.get("prediction"):
                continue
            out.append(_rec(st["model_key"], st["stage"], rec["id"], rec["prediction"],
                            {f: cf[f].get("confidence") for f in FIELDS},
                            {f: {rec["prediction"][f]: cf[f].get("chosen_probability")} for f in FIELDS}))
    return out


# ---------------------------------------------------------------------------
# Canonical review difficulty: share of run-passes (fixed denominator = number
# of runs in the cohort, invalid output counted as a non-match) whose answer
# matched the reference on all four fields. Lower share = harder.
# ---------------------------------------------------------------------------

def difficulty(runs, ref):
    """Return {id: {"all_four": n, "valid": n, field: n ...}} over the given runs."""
    out = {rid: {"all_four": 0, "valid": 0, **{f: 0 for f in FIELDS}} for rid in IDS}
    for r in runs:
        for rid in IDS:
            p = r.pred(rid)
            if p is None:
                continue
            out[rid]["valid"] += 1
            ok = True
            for f in FIELDS:
                if p[f] == ref[rid][f]:
                    out[rid][f] += 1
                else:
                    ok = False
            if ok:
                out[rid]["all_four"] += 1
    return out


def hardest(runs, ref, n=10):
    """IDs sorted ascending by all-four match share over the cohort (fixed denominator)."""
    d = difficulty(runs, ref)
    return sorted(IDS, key=lambda i: (d[i]["all_four"], i))[:n]


def run_cost(r):
    """(kind, usd) with kind in observed|known|estimate|unknown. Missing cost is unknown, never zero."""
    c = r.cost or {}
    for key, kind in (("actualUsd", "observed"), ("knownUsd", "known"), ("estimatedUsd", "estimate")):
        v = c.get(key)
        if v not in (None, "", "null"):
            try:
                return kind, float(v)
            except (TypeError, ValueError):
                pass
    return "unknown", None


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def md_table(headers, rows, align=None):
    align = align or ["---"] * len(headers)
    lines = ["| " + " | ".join(str(h) for h in headers) + " |", "| " + " | ".join(align) + " |"]
    for r in rows:
        lines.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(lines)


def pct(n, d):
    return "n/a" if not d else f"{100.0 * n / d:.1f}%"


if __name__ == "__main__":
    ref = reference()
    runs = load_all()
    print("runs loaded:", len(runs), Counter(r.feed for r in runs))
    print("categories:", Counter(r.category for r in runs))
    # self-check: recomputed all_four must equal the feed's own score where present
    bad = 0
    checked = 0
    for r in runs:
        sc = r.scores or {}
        if "all_four" in sc and sc["all_four"] is not None:
            checked += 1
            if r.all_four(ref) != sc["all_four"]:
                bad += 1
                if bad <= 5:
                    print("MISMATCH", r, "feed", sc["all_four"], "recomputed", r.all_four(ref))
    print(f"all_four self-check: {checked} checked, {bad} mismatches")
    conf = load_confidence()
    print("confidence records:", len(conf), Counter((c["model"]) for c in conf))
    assert bad == 0, "recomputed scores must equal feed scores"
    print("OK")
