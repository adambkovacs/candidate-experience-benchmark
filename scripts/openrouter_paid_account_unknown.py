#!/usr/bin/env python3
"""Explicit operator accounting of one unknown charge at its full reserved bound.

This does not assert actual cost, reduce the accounted budget, modify inference
outputs, or retry a request. Review the evidence before invoking this helper.
"""
import argparse
import json
from openrouter_paid_benchmark import BudgetLedger, LEDGER_PATH

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt',required=True)
    parser.add_argument('--reason',required=True)
    parser.add_argument('--evidence',required=True,help='Immutable attempt output JSONL')
    args=parser.parse_args()
    ledger=BudgetLedger(LEDGER_PATH)
    try:
        event=ledger.finalize_unknown_at_reserved_upper_bound(args.attempt,args.reason,args.evidence)
        print(json.dumps({'event':event,'aggregate_accounted_usd':str(ledger.accounted())},indent=2))
    finally:ledger.close()
if __name__=='__main__':main()
