# Kev and Jev historical unknown-cost risk hold proposal

The [read-only audit](JEV_KEV_UNKNOWN_BOUND_AUDIT_2026-10-07.md) identifies three old unknown charges. Their existing OpenRouter accounting retains $0.003032064. Four full Choice-question contexts at the saved route prices would bound them at $0.012128256, leaving **$0.009096192** of additional uncertainty. This proposal creates a separate OpenRouter-only risk hold for that *difference*. It is not a measured provider charge and does not authorize another request.

The [offline controller](../scripts/jev_kev_unknown_risk_hold_v1.py) checks the exact Kev DEV-026, Jev DEV-018, and Jev DEV-060 attempt IDs; frozen four-question payloads; saved route identity and tariff; original unknown evidence; both Jev closed child ledgers and reconciliations; and the old Kev unknown event in the current master. Its [proposal manifest](../results/jev-kev-unknown-risk-hold-v1/proposal.json) binds the controller, test, monetary readers, audit, and immutable evidence by SHA-256. The [review receipt](../results/jev-kev-unknown-risk-hold-v1/root-review.json) is deliberately unapproved. `verify` is read-only; `admit` is a separate gated operation and must not be invoked before root and independent review.

If approved, `admit` would allocate one empty $0.009096192 child under the current $22.38 master and place a matching hold in the versioned OpenRouter-only authority. The allocation has a distinct ID, leaves the three original reservations and all known charges unchanged, and contains no inference or settle event. Its unused child allocation must **not** be released while the historical billing uncertainty remains. A failed authority hold after child allocation leaves an encumbered child; the same reviewed command can recover that exact state without allocating a second child. It refuses a released or different hold and a duplicate admission claim.

Offline checks from the repository root:

```sh
PYTHONPATH=scripts python3 scripts/jev_kev_unknown_risk_hold_v1.py verify
PYTHONPATH=scripts python3 -m pytest -q tests/test_jev_kev_unknown_risk_hold_v1.py
```

Before any later admission, recheck the current master and authority heads, remaining capacity, all source bindings, and the exact reviewed proposal SHA. This offline proposal makes no cap increase, fourth repeat pass, provider request, or release decision.
