"""Reviewed $22.38 OpenRouter ceiling; earlier ledger implementations stay frozen."""
import fcntl
import json
from decimal import Decimal
from pathlib import Path
from openrouter_paid_benchmark import BudgetLedger as LegacyBudgetLedger, number

CAP = Decimal('22.38')
OLD_CAP = Decimal('12.38')


class BudgetLedger(LegacyBudgetLedger):
    def __init__(self, path, cap_limit=None):
        self.is_master = cap_limit is None
        self.cap_limit = CAP if self.is_master else number(cap_limit)
        if not 0 < self.cap_limit <= CAP:
            raise ValueError('Invalid ledger cap limit')
        if self.is_master and not Path(path).is_file():
            raise ValueError('Require an existing master ledger')
        self.file = open(path, 'r+' if self.is_master else 'a+')
        try:
            fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.file.seek(0)
            raw = self.file.read()
            if raw and not raw.endswith('\n'):
                raise ValueError('Incomplete budget ledger')
            self.events = [json.loads(line) for line in raw.splitlines() if line.strip()]
            permitted = (Decimal('1'), Decimal('5'), Decimal('10'), OLD_CAP) if self.is_master else (self.cap_limit,)
            if self.events and (self.events[0].get('event') != 'budget' or
                                number(self.events[0].get('cap_usd')) not in permitted):
                raise ValueError('Ledger provenance differs')
            if not self.events:
                if self.is_master:
                    raise ValueError('Empty master ledger')
                self.append({'event': 'budget', 'cap_usd': str(self.cap_limit)})
            self.state()
        except BaseException:
            self.file.close()
            raise

    def state(self):
        if self.is_master:
            for event in self.events:
                if event.get('event') == 'cap_amendment' and number(event['cap_usd']) > OLD_CAP:
                    from openrouter_budget_amendment_v3 import validate_event, counterpart_committed
                    proposal = validate_event(event, 'master')
                    if Path(self.file.name).resolve() != Path(proposal['master']['path']):
                        raise ValueError('Amendment belongs to another master')
                    if not counterpart_committed(proposal, event['review_path'], 'master'):
                        raise ValueError('Original master prefix or amendment changed')
                    if not counterpart_committed(proposal, event['review_path'], 'authority'):
                        raise ValueError('Authority amendment is not committed')
        return super().state()

    def amend_cap(self, new_cap, reason):
        if self.is_master and number(new_cap) > OLD_CAP:
            raise ValueError('Use separately reviewed amendment activation')
        return super().amend_cap(new_cap, reason)
