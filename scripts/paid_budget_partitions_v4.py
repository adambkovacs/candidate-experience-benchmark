"""Reuse the frozen partition protocol with an isolated $22.38 ledger binding."""
import importlib.util
from pathlib import Path
from openrouter_budget_v4 import BudgetLedger

_source = Path(__file__).with_name('paid_budget_partitions_v3.py')
_spec = importlib.util.spec_from_file_location('_openrouter_partitions_v4_private', _source)
_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)
_core.BudgetLedger = BudgetLedger

sha = _core.sha
allocate = _core.allocate
bound_entry = _core.bound_entry
require_child_ledger = _core.require_child_ledger
open_partition = _core.open_partition
reconcile_partition = _core.reconcile_partition
