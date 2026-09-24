"""Approved $10 master ledger, preserving historical ledger implementations."""
import fcntl
import json
from decimal import Decimal
from openrouter_paid_benchmark import BudgetLedger as LegacyBudgetLedger, number

CAP = Decimal('10')

class BudgetLedger(LegacyBudgetLedger):
    def __init__(self, path, cap_limit=None):
        self.cap_limit = CAP if cap_limit is None else number(cap_limit)
        if not 0 < self.cap_limit <= CAP:
            raise ValueError('Invalid ledger cap limit')
        self.file = open(path, 'a+')
        try:
            fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.file.seek(0)
            self.events = [json.loads(line) for line in self.file if line.strip()]
            permitted = (Decimal('1'), Decimal('5'), CAP) if cap_limit is None else (self.cap_limit,)
            if self.events and (self.events[0].get('event') != 'budget' or number(self.events[0].get('cap_usd')) not in permitted):
                raise ValueError('Ledger cap mismatch')
            if not self.events:
                self.append({'event': 'budget', 'cap_usd': str(self.cap_limit)})
            self.state()
        except BaseException:
            self.file.close()
            raise
