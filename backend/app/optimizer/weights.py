import math
from types import MappingProxyType

from app.optimizer.types import ObjectiveMode, ObjectiveWeights

WEIGHT_PRESETS = MappingProxyType(
    {
        ObjectiveMode.TEAM_FIRST: ObjectiveWeights(
            peak_strength=0.28,
            depth=0.16,
            flexibility=0.10,
            rotation=0.08,
            training_efficiency=0.13,
            transfer_value=0.04,
            wage_efficiency=0.08,
            capital_efficiency=0.05,
            liquidity=0.08,
        ),
        ObjectiveMode.BALANCED: ObjectiveWeights(
            peak_strength=0.18,
            depth=0.12,
            flexibility=0.08,
            rotation=0.07,
            training_efficiency=0.15,
            transfer_value=0.13,
            wage_efficiency=0.10,
            capital_efficiency=0.08,
            liquidity=0.09,
        ),
        ObjectiveMode.PROFIT_FIRST: ObjectiveWeights(
            peak_strength=0.10,
            depth=0.08,
            flexibility=0.05,
            rotation=0.05,
            training_efficiency=0.18,
            transfer_value=0.25,
            wage_efficiency=0.11,
            capital_efficiency=0.10,
            liquidity=0.08,
        ),
    }
)


def normalized_weights(mode: ObjectiveMode, custom: ObjectiveWeights | None) -> ObjectiveWeights:
    selected = custom or WEIGHT_PRESETS[mode]
    values = selected.as_mapping()
    if any(not math.isfinite(value) or value < 0 for value in values.values()):
        raise ValueError("Objective weights must be finite and non-negative")
    total = sum(values.values())
    if total <= 0:
        raise ValueError("At least one objective weight must be positive")
    normalized = {name: value / total for name, value in values.items()}
    return ObjectiveWeights(**normalized)
