#!/usr/bin/env python3
"""High-effort roster using an isolated copy of the frozen Gemini mechanics.

Planning is offline. The wrapper is hash-bound in every plan; earlier controllers
and completed series are unchanged. A proposed cap is not a budget allocation.
"""
import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve()
spec = importlib.util.spec_from_file_location('_gemini_high_frozen_mechanics', PATH.with_name('gemini_repeat_roster.py'))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
runner.SCHEMA = 'gemini-openrouter-repeat-high-v1'
runner.REVIEW_SCHEMA = 'gemini-openrouter-repeat-high-review-v1'
runner.CONFIGS = {
    'gemini31-pro-preview-high-p0-openrouter-v3': (
        'gemini31-pro-preview-high', 'google/gemini-3.1-pro-preview', 'high',
        'g31-pro-high-repeat-v1', '2.00'),
    'gemini37-flash-high-p0-openrouter-v3': (
        'gemini37-flash-high', 'google/gemini-3.7-flash', 'high',
        'g37-high-repeat-v1', '1.00'),
}
runner.SOURCE_CODE = (*runner.SOURCE_CODE, 'scripts/gemini_repeat_high.py')

if __name__ == '__main__':
    runner.main()
