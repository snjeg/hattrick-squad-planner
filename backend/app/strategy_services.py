from app.schemas import StrategyMatrixResponse, StrategyPreferencesRequest
from app.strategy import StrategyPreferences, build_position_skill_matrix


def get_strategy_matrix(payload: StrategyPreferencesRequest) -> StrategyMatrixResponse:
    matrix = build_position_skill_matrix(
        StrategyPreferences(
            primary_tactic=payload.primary_tactic,
            preferred_formations=tuple(payload.preferred_formations),
        )
    )
    return StrategyMatrixResponse.model_validate(matrix)
