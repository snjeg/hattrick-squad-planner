def revenue_share(match_type: int, *, is_home: bool) -> float | None:
    """Return the club's share using official match-type rules."""
    if match_type == 1:  # league
        return 1.0 if is_home else 0.0
    if match_type == 3:  # national cup
        return 2 / 3 if is_home else 1 / 3
    if match_type in {2, 4, 5, 8, 9, 12}:  # qualifier and friendlies
        return .5
    return None
