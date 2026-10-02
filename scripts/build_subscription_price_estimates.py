#!/usr/bin/env python3
"""Build a public, offline API-list-price proxy for subscription benchmark runs.

No inference, account API, or paid endpoint is used. Monetary amounts are USD.
"""

import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public-site"
CHECKED = "2026-10-02"
PROJECTION = "public-evidence/subscription-pricing-v1/usage-aggregates.json"

# Exact requested model IDs only. Rates are current standard short-context API
# list prices, not the historic subscription price or an observed charge.
RATES = {
    "claude-haiku-4-5-20251001": ("1", "0.10", "1.25", "2", "5", "https://platform.claude.com/docs/en/models/haiku-4-5/overview"),
    "claude-sonnet-5": ("2", "0.20", "2.50", "4", "10", "https://platform.claude.com/docs/en/models/sonnet-5/overview"),
    "claude-opus-5": ("5", "0.50", "6.25", "10", "25", "https://platform.claude.com/docs/en/models/opus-5/overview"),
    "claude-opus-5-5": ("4", "0.20", "5", "8", "20", "https://platform.claude.com/docs/en/models/opus-5-5/overview"),
    "claude-fable-5-1": ("10", "0.25", "12.50", "20", "50", "https://platform.claude.com/docs/en/models/fable-5-1/overview"),
    "gpt-5.6-luna": ("0.20", "0.02", "0.25", "0.25", "1.20", "https://developers.openai.com/api/docs/models/gpt-5.6-luna"),
    "gpt-5.6-terra": ("2", "0.20", "2.50", "2.50", "12", "https://developers.openai.com/api/docs/models/gpt-5.6-terra"),
    "gpt-5.6-sol": ("4", "0.40", "5", "5", "20", "https://developers.openai.com/api/docs/models/gpt-5.6-sol"),
    "gpt-6-luna": ("0.10", "0.01", "0.125", "0.125", "0.50", "https://developers.openai.com/api/docs/models/gpt-6-luna"),
    "gpt-6-sol": ("2", "0.20", "2.50", "2.50", "10", "https://developers.openai.com/api/docs/models/gpt-6-sol"),
    "gpt-6-astra": ("10", "1", "12.50", "12.50", "50", "https://developers.openai.com/api/docs/models/gpt-6-astra"),
}


def read_json(path):
    return json.loads(path.read_text())


def integer(value):
    return value if type(value) is int and value >= 0 else None


def tokens_from_claude_usage(usages):
    fields = ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens", "output_tokens")
    if not usages or any(any(integer(u.get(k)) is None for k in fields) for u in usages):
        return None
    summed = {k: sum(u[k] for u in usages) for k in fields}
    details = [u.get("cache_creation") for u in usages]
    if all(isinstance(d, dict) and all(integer(d.get(k)) is not None for k in
                                         ("ephemeral_5m_input_tokens", "ephemeral_1h_input_tokens")) for d in details):
        five = sum(d["ephemeral_5m_input_tokens"] for d in details)
        hour = sum(d["ephemeral_1h_input_tokens"] for d in details)
        if five + hour != summed["cache_creation_input_tokens"]:
            five = hour = None
    else:
        five = hour = None
    thinking = [u.get("output_tokens_details", {}).get("thinking_tokens") for u in usages]
    return dict(input=summed["input_tokens"], cacheRead=summed["cache_read_input_tokens"],
                cacheWrite=summed["cache_creation_input_tokens"], cacheWrite5m=five,
                cacheWrite1h=hour, output=summed["output_tokens"],
                reasoningOutput=sum(thinking) if all(integer(x) is not None for x in thinking) else None)


def claude_sidecar(run):
    url = run.get("evidenceUrl") or ""
    marker = "/blob/main/"
    if marker not in url:
        return None
    rel = url.split(marker, 1)[1]
    # The published evidence path can be a sanitized copy. Only a local,
    # separately saved batch ledger with measured usage can resolve buckets.
    p = ROOT / rel
    candidates = [Path(str(p) + suffix) for suffix in
                  (".batches.jsonl", ".batches.normalized.jsonl", ".batches-normalized.jsonl")]
    candidates += [p.with_name(p.stem + suffix) for suffix in
                   (".batches.jsonl", ".batches.normalized.jsonl", ".batches-normalized.jsonl")]
    candidates.append(p)
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            rows = [json.loads(s) for s in candidate.read_text().splitlines() if s.strip()]
            tokens = tokens_from_claude_usage([r["usage"] for r in rows])
        except (KeyError, ValueError, TypeError):
            continue
        published = run.get("tokens") or {}
        if tokens is not None and (published.get("input") in
                (tokens["input"], tokens["input"] + tokens["cacheRead"] + tokens["cacheWrite"]) and
                published.get("cachedInput") == tokens["cacheRead"] and
                published.get("cacheWrite") == tokens["cacheWrite"] and
                published.get("output") == tokens["output"]):
            return tokens, candidate.relative_to(ROOT).as_posix()
    return None


def codex_sidecar(run):
    url = run.get("evidenceUrl") or ""
    marker = "/blob/main/"
    if marker not in url:
        return None
    p = ROOT / url.split(marker, 1)[1]
    candidates = [p.with_name("development-attempts.jsonl"),
                  p.with_name("development-batch-attempts.jsonl")]
    if p.is_file():
        try:
            rows = [json.loads(s) for s in p.read_text().splitlines() if s.strip()]
            linked = {r.get("batch_attempt_file") for r in rows if r.get("batch_attempt_file")}
            if len(linked) == 1:
                candidates.insert(0, ROOT / linked.pop())
        except (ValueError, TypeError):
            pass
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            rows = [json.loads(s) for s in candidate.read_text().splitlines() if s.strip()]
            usages = [r.get("usage") for r in rows]
            keys = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens",
                    "output_tokens", "reasoning_output_tokens")
            if not usages or any(not isinstance(u, dict) or any(integer(u.get(k)) is None for k in keys)
                                 for u in usages):
                continue
            sums = {k: sum(u[k] for u in usages) for k in keys}
        except (ValueError, TypeError):
            continue
        t = run.get("tokens") or {}
        if (sums["input_tokens"], sums["cached_input_tokens"], sums["output_tokens"]) != (
                t.get("input"), t.get("cachedInput"), t.get("output")):
            continue
        return (dict(input=sums["input_tokens"], cacheRead=sums["cached_input_tokens"],
                     cacheWrite=sums["cache_write_input_tokens"], cacheWrite5m=None,
                     cacheWrite1h=None, output=sums["output_tokens"],
                     reasoningOutput=sums["reasoning_output_tokens"]),
                candidate.relative_to(ROOT).as_posix())
    return None


def rate_info(model):
    raw = RATES.get(model)
    if raw is None:
        return None
    return dict(inputUsdPerMillion=raw[0], cacheReadUsdPerMillion=raw[1],
                cacheWrite5mUsdPerMillion=raw[2], cacheWrite1hUsdPerMillion=raw[3],
                outputUsdPerMillion=raw[4], sourceUrl=raw[5], checkedDate=CHECKED,
                basis="current standard short-context API list price")


def estimate(model, tokens, complete):
    rate = rate_info(model)
    if rate is None:
        return None, "unpriced_exact_model", None
    if tokens is None or any(integer(tokens.get(k)) is None for k in ("input", "cacheRead", "output")):
        return None, "missing_token_component", None
    if model.startswith("claude-"):
        write = integer(tokens.get("cacheWrite"))
        five, hour = integer(tokens.get("cacheWrite5m")), integer(tokens.get("cacheWrite1h"))
        if write is None or (write and (five is None or hour is None or five + hour != write)):
            return None, "cache_write_duration_unknown", None
        five, hour = five or 0, hour or 0
        uncached = tokens["input"]
    else:
        # OpenAI input_tokens contains cached tokens. Cache-write telemetry is
        # separately reported by the CLI when available.
        write = integer(tokens.get("cacheWrite"))
        if write is None:
            return None, "cache_write_tokens_unreported", None
        uncached = tokens["input"] - tokens["cacheRead"] - write
        if uncached < 0:
            return None, "invalid_input_partition", None
        five, hour = write, 0
    parts = dict(input=Decimal(uncached) * Decimal(rate["inputUsdPerMillion"]),
                 cacheRead=Decimal(tokens["cacheRead"]) * Decimal(rate["cacheReadUsdPerMillion"]),
                 cacheWrite5m=Decimal(five) * Decimal(rate["cacheWrite5mUsdPerMillion"]),
                 cacheWrite1h=Decimal(hour) * Decimal(rate["cacheWrite1hUsdPerMillion"]),
                 output=Decimal(tokens["output"]) * Decimal(rate["outputUsdPerMillion"]))
    amount = sum(parts.values()) / Decimal(1_000_000)
    return str(amount), "complete" if complete else "known_usage_only", {k: str(v / Decimal(1_000_000)) for k, v in parts.items()}


def row_entry(run_id, model, tokens, complete, evidence, scope):
    amount, status, parts = estimate(model, tokens, complete)
    bindings = []
    for source in evidence:
        candidate = ROOT / source.split(";", 1)[0]
        if candidate.is_file():
            bindings.append(dict(sourceKind="saved_attempt_ledger" if candidate.suffix == ".jsonl" else "public_aggregate_report",
                                 sha256=hashlib.sha256(candidate.read_bytes()).hexdigest()))
    return dict(runId=run_id, model=model, scope=scope, tokens=tokens,
                usageStatus="complete" if complete else "partial_or_unverified",
                estimateStatus=status, estimateUsd=amount, estimatedComponentsUsd=parts,
                actualSubscriptionChargeUsd=None, rate=rate_info(model), evidence=[PROJECTION],
                sourceBindings=bindings,
                note="Output already includes reasoning tokens; reasoning is displayed, never added again. "
                     "API-equivalent estimate is not a subscription charge or quota measurement.")


def run_tokens(run):
    t = run.get("tokens") or {}
    if run["surface"] == "Claude subscription":
        sidecar = claude_sidecar(run)
        if sidecar:
            return sidecar
        inp, read, write = (integer(t.get(k)) for k in ("input", "cachedInput", "cacheWrite"))
        # Some legacy public aggregates use total input, others uncached input.
        # Only when total < cache components is the uncached interpretation forced.
        if inp is not None and read is not None and write is not None and inp < read + write:
            return dict(input=inp, cacheRead=read, cacheWrite=write,
                        cacheWrite5m=None, cacheWrite1h=None, output=integer(t.get("output")),
                        reasoningOutput=integer(t.get("reasoning"))), "public-site/data.json"
        return None, "public-site/data.json; input partition unresolved"
    sidecar = codex_sidecar(run)
    if sidecar:
        return sidecar
    return (dict(input=integer(t.get("input")), cacheRead=integer(t.get("cachedInput")),
                 cacheWrite=integer(t.get("cacheWrite")), cacheWrite5m=None, cacheWrite1h=None,
                 output=integer(t.get("output")), reasoningOutput=integer(t.get("reasoning"))),
            "public-site/data.json")


def repeat_tokens(usage, model):
    t = (usage or {}).get("tokens") or {}
    if model.startswith("claude-"):
        write = integer(t.get("cache_creation_input_tokens"))
        return dict(input=integer(t.get("input_tokens")), cacheRead=integer(t.get("cache_read_input_tokens")),
                    cacheWrite=write, cacheWrite5m=0 if write == 0 else None,
                    cacheWrite1h=0 if write == 0 else None,
                    output=integer(t.get("output_tokens")), reasoningOutput=integer(t.get("thinking_tokens")))
    return dict(input=integer(t.get("input_tokens")), cacheRead=integer(t.get("cached_input_tokens")),
                cacheWrite=integer(t.get("cache_write_input_tokens")), cacheWrite5m=None, cacheWrite1h=None,
                output=integer(t.get("output_tokens")), reasoningOutput=integer(t.get("reasoning_output_tokens")))


def repeat_source_file(name, series, pass_name, condition):
    config = series["configuration"]
    if name == "claude-repeats.json":
        if pass_name == "original":
            return ROOT / "results/claude-subscription-2026-09-23" / f"{config}-development.jsonl.batches-normalized.jsonl" if condition == "P0" else None
        return ROOT / "results/repeatability-v1" / f"claude-{config}" / pass_name / condition / "development.attempts.jsonl"
    if name == "claude-roster-repeats.json":
        if pass_name == "original":
            if condition == "P0":
                return ROOT / "results/subscription-batch-p0-2026-09-23" / config / "development.batches.normalized.jsonl"
            return ROOT / "results/prompt-comparison-v1-2026-09-24/runs" / config / condition / "development.jsonl.batches.jsonl"
        return ROOT / "results/repeatability-v1/claude-roster-v1" / config / pass_name / condition / "development.attempts.jsonl"
    if name == "haiku-fresh-matched3.json":
        return ROOT / "results/repeatability-v1/claude-haiku-fresh-matched3" / pass_name / condition / "development.attempts.jsonl"
    return None


def repeat_claude_buckets(name, series, pass_name, condition, summary):
    path = repeat_source_file(name, series, pass_name, condition)
    if not path or not path.is_file():
        return summary, None
    try:
        rows = [json.loads(s) for s in path.read_text().splitlines() if s.strip()]
        raw = tokens_from_claude_usage([r["usage"] for r in rows])
    except (KeyError, ValueError, TypeError):
        return summary, None
    if raw and all(raw[k] == summary[k] for k in ("input", "cacheRead", "cacheWrite", "output")):
        return raw, path.relative_to(ROOT).as_posix()
    return summary, None


def build():
    runs = {}
    for row in read_json(PUBLIC / "data.json")["runs"]:
        if row.get("surface") not in ("Claude subscription", "Codex subscription"):
            continue
        tokens, source = run_tokens(row)
        runs[row["id"]] = row_entry(row["id"], row.get("model"), tokens,
                                     row.get("tokens", {}).get("complete") is True,
                                     [source], "historical_development")
    phases, series_totals = {}, {}
    names = ("claude-repeats.json", "claude-roster-repeats.json", "haiku-fresh-matched3.json",
             "repeats.json", "codex-fresh-repeats.json")
    for name in names:
        doc = read_json(PUBLIC / name)
        all_series = doc.get("series", doc)
        all_series = all_series if isinstance(all_series, list) else [all_series]
        for series in all_series:
            config, model = series["configuration"], series["model"]
            keys = []
            for pass_name, conditions in series["passes"].items():
                for condition, phase in conditions.items():
                    key = f"{config}:{pass_name}:{condition}"
                    summary = repeat_tokens(phase.get("usage"), model)
                    raw_source = None
                    if model.startswith("claude-"):
                        summary, raw_source = repeat_claude_buckets(name, series, pass_name, condition, summary)
                    state = phase.get("status", phase.get("completionStatus"))
                    report_complete = (name == "repeats.json" and series.get("completedConditions") == 9 and
                                       not series.get("missingPasses") and phase.get("score", {}).get("denominator") == 60)
                    complete = (state in ("complete", "completed") or report_complete) and all(
                        integer(summary.get(k)) is not None for k in ("input", "cacheRead", "cacheWrite", "output"))
                    phases[key] = row_entry(key, model, summary, complete,
                                            ["public-site/" + name] + ([raw_source] if raw_source else []),
                                            "repeat_development_phase")
                    phases[key]["configuration"] = config
                    phases[key]["pass"] = pass_name
                    phases[key]["condition"] = condition
                    keys.append(key)
            values = [Decimal(phases[k]["estimateUsd"]) for k in keys if phases[k]["estimateUsd"] is not None]
            series_totals[config] = dict(configuration=config, model=model, phaseKeys=keys,
                                         pricedPhases=len(values), totalPhases=len(keys),
                                         estimatedUsdForPricedPhases=str(sum(values)),
                                         fullSeriesEstimateUsd=str(sum(values)) if all(
                                             phases[k]["estimateStatus"] == "complete" for k in keys) else None,
                                         actualSubscriptionChargeUsd=None)
    rates = {k: rate_info(k) for k in RATES}
    return dict(schema="subscription-price-estimates-v1", generatedAt=CHECKED,
                currency="USD", rateBasis="current public standard short-context API list prices, checked 2026-10-02",
                billingNote="Subscriptions have no observed per-request charge here. These figures are API-equivalent proxies, not paid amounts or quota use.",
                accounting="Claude input tokens exclude separately reported cache reads/writes. OpenAI input tokens include cached input; subtract cached and reported cache writes before applying the base input rate. Output contains reasoning tokens, which are never added again.",
                rates=rates, runs=runs, repeatPhases=phases, repeatSeries=series_totals)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=PUBLIC / "subscription-price-estimates.json")
    parser.add_argument("--provenance-output", type=Path, default=ROOT / PROJECTION)
    args = parser.parse_args()
    data = build()
    provenance = dict(schema="subscription-usage-aggregates-v1", generatedAt=CHECKED,
                      note="Usage-only projection. Source SHA-256 values bind saved input bytes; private raw attempts are not published here.",
                      runs={key: {field: entry[field] for field in ("model", "tokens", "usageStatus", "sourceBindings")}
                            for key, entry in data["runs"].items()},
                      repeatPhases={key: {field: entry[field] for field in ("model", "tokens", "usageStatus", "sourceBindings")}
                                    for key, entry in data["repeatPhases"].items()})
    args.provenance_output.parent.mkdir(parents=True, exist_ok=True)
    args.provenance_output.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")
    args.output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    print(f"{len(data['runs'])} historical runs, {len(data['repeatPhases'])} repeat phases, {len(data['repeatSeries'])} series")
    print(f"priced: {sum(x['estimateUsd'] is not None for x in data['runs'].values())} historical, "
          f"{sum(x['estimateUsd'] is not None for x in data['repeatPhases'].values())} repeat phases")


if __name__ == "__main__":
    main()
