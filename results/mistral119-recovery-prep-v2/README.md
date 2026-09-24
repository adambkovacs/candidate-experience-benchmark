# Mistral 119B smoke recovery, second checkpoint

Both P0 smoke conditions (`none` and `high`) used the unchanged `mistralai/mistral-small-2603` model on `mistral/zdr`, after about 1 hour 50 minutes since the preceding provider failures. Public endpoint metadata reported an available route, but each first inference request again returned HTTP 429. Neither condition produced a model response, and neither was admitted to a full development run. DEV-002 and DEV-003 were not sent in either smoke.

The separate outputs preserve every earlier attempt. Each new failure retains its full $0.04177920 reservation as an unknown-charge upper bound, not an observed charge. Both partitions are sealed in [the budget receipts](../hosted-recovery-budget-v2/). The failed smoke inspections explicitly reject development admission.

Next step: wait for a meaningful provider-capacity change before another bounded smoke, or record a separately approved provider surface if one becomes suitable. Do not treat catalogue availability as evidence that inference works or repeat the same failing smoke in a tight loop. No provider key, fallback, model substitution, or local download was introduced.
