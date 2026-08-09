# Player contribution engine

## Scope and result

Milestone 5 calculates one senior player's raw contribution to midfield and the left,
central, and right defense and attack sectors. The result is a deterministic numeric
vector for one position, side, individual order, and match context. It is **not** a
displayed Hattrick sector rating, a whole-lineup calculation, a player ranking, or a
lineup recommendation. The engine is framework-free and does not call CHPP, FastAPI, the
database, or React.

`starting` is the verified match-start vector. HO's minute-zero stamina factor is always
`1.0`, so stamina does not alter this result. The plan adapter compares the current factual
snapshot with projected trainable skills after each manual training block. It does not
write projections back to factual snapshots.

## Pinned source

Primary community reference audited on 2026-08-09:

- Hattrick Organizer commit `b58f36e2eecc98ba14d88be49c3042c575698134`;
- `src/main/java/core/rating/RatingPredictionModel.java`, especially
  `initRatingContributionParameterMap`, `calcSkillRating`, `calcForm`,
  `calcExperience`, `calcStamina`, `calcMatchAverageStaminaFactor`, and `calcWeather`;
- `src/main/java/core/model/player/MatchRoleID.java` and `IMatchRoleID.java` for roles;
- `src/main/java/core/constants/player/PlayerSpeciality.java` for specialty IDs;
- `src/main/java/core/rating/RatingPredictionManager.java` to verify that Schum remains
  HO's active default.

Hattrick Organizer is a community implementation, not an official disclosure of
Hattrick's private rating formula. Constants are labeled
`community-reference-high-confidence` and pinned in the returned model version. Current
official position/order documentation checked legal combinations, but does not publish
the numerical contribution formula.

## Formula implemented

For each required skill and target sector, HO's individual layer is translated as:

```text
skill_rating(x) = max(0, x - 1)
form_factor     = 0.378 * sqrt(min(7, skill_rating(form)))
loyalty_bonus  = skill_rating(loyalty) / 19
mother_club     = 1.5 instead of the loyalty bonus
effective_skill = (skill_rating(fractional_skill) + loyalty_bonus) * form_factor

experience_base(x) = -0.00000725*x^4 + 0.0005*x^3
                     - 0.01336*x^2 + 0.176*x
where x = skill_rating(experience)

raw_sector = sum(effective_skill * position_coefficient)
             + experience_base * sector_experience_factor
```

Experience is added only to a sector with a positive positional/skill contribution, as in
HO. Sector experience factors are `0.73` midfield, `0.345` side defense, `0.48` central
defense, `0.375` side attack, and `0.45` central attack.

## Stamina call-path audit

The follow-up audit traced the exact pinned call path rather than only the polynomial:

1. `getPlayerRatingMatchBeginning` reads `playerRatingCache` at minute `0`.
2. `calcPlayerRating` calls `getPositionContribution` for every rating sector.
3. `getPositionContribution` adds experience, then applies weather and minute-specific
   `calcStamina`. At minute zero, `calcStamina` returns `1.0` because its starting `r0` is
   at least `102`, then capped by `min(1, r0 / 100)`.
4. `calcPlayerRating` multiplies each sector by its sector scale, weights midfield by
   three, sums, and applies the nonlinear conversion `pow(sum, 1.2) / 4`.
5. Only then does `getPlayerMatchAverageRating` multiply that scalar player rating by
   `getMatchAverageStaminaFactor`.

The scalar 90-minute multiplier is:

```text
min(1, -0.0033 * stamina^2 + 0.085 * stamina + 0.51)
```

Therefore multiplying this module's raw vector by the factor is not equivalent to HO. If
`T(v) = pow(weighted(v), 1.2) / 4` and `k` is the stamina factor, HO computes `k*T(v)`,
whereas pre-multiplying the vector produces `T(k*v) = k^1.2*T(v)`. They differ for
`0 < k < 1`.

Milestone 5 consequently exposes only the verified match-start vector. It does not expose
a raw `match_average` vector or the scalar HO player rating. Both the nonlinear conversion
and average-stamina placement remain deferred to Milestone 6; this is a boundary correction,
not an additional team-rating implementation.

Weather is separate match context. Technical players receive `1.05` in sun and `0.95` in
rain; Quick players receive `0.95` in sun or rain; Powerful players receive `0.95` in sun
and `1.05` in rain. Other combinations use `1.0`. Sunny or rainy requests require known
specialty rather than assuming none.

The sole coefficient-level specialty override is a Technical defensive forward's
side-attack Passing coefficient: `0.41` rather than `0.31`. Random/situational special
events are not modeled.

## Position and order coefficients

The complete typed table lives in `backend/app/contribution/coefficients.py`. Values below
are transcribed from HO's active `initRatingContributionParameterMap`; left/right roles
are mirrored.

| Role / order | Coefficients |
| --- | --- |
| Goalkeeper normal | GK→side defense `.61`; Def→side defense `.25`; GK→central defense `.87`; Def→central defense `.35` |
| Wingback normal | Def→same defense `.92`; Def→central defense `.38`; PM→midfield `.15`; Wing→same attack `.59` |
| Wingback offensive | `.74`, `.35`, `.20`, `.69` in the same sequence |
| Wingback defensive | `1.00`, `.43`, `.10`, `.45` |
| Wingback towards middle | `.75`, `.70`, `.20`, `.35` |
| Central defender normal | Def→same defense `.52`; Def→central defense `1.00`; PM→midfield `.25` |
| Central defender offensive | `.40`, `.73`, `.40` in the same sequence |
| Central defender towards wing | Def→same defense `.81`; Def→central defense `.67`; PM→midfield `.15`; Wing→same attack `.26` |
| Winger normal | Def→same defense `.35`; Def→central defense `.20`; PM→midfield `.45`; Pass→central attack `.11`; Pass→same attack `.26`; Wing→same attack `.86` |
| Winger offensive | `.22`, `.13`, `.30`, `.13`, `.29`, `1.00` |
| Winger defensive | `.61`, `.25`, `.30`, `.05`, `.21`, `.69` |
| Winger towards middle | `.29`, `.25`, `.55`, `.16`, `.15`, `.74` |
| Inner midfielder normal | Def→same defense `.19`; Def→central defense `.40`; PM→midfield `1.00`; Pass→central attack `.33`; Score→central attack `.22`; Pass→same attack `.26` |
| Inner midfielder offensive | `.09`, `.16`, `.95`, `.49`, `.31`, `.36` |
| Inner midfielder defensive | `.27`, `.58`, `.95`, `.18`, `.13`, `.14` |
| Inner midfielder towards wing | Def→same defense `.24`; Def→central defense `.33`; PM→midfield `.90`; Pass→central attack `.23`; Pass→same attack `.31`; Wing→same attack `.59` |
| Forward normal | PM→midfield `.25`; Pass→central attack `.33`; Score→central attack `1.00`; Pass/Wing/Score→each side attack `.14/.24/.27` |
| Forward defensive | PM→midfield `.35`; Pass→central attack `.53`; Score→central attack `.56`; Pass/Wing/Score→each side attack `.31/.13/.13` |
| Forward towards wing | PM→midfield `.15`; Pass→central attack `.23`; Score→central attack `.66`; Pass→same/opposite attack `.21/.06`; Wing `.64/.21`; Score `.51/.19` |

For centered central defenders and inner midfielders, HO's contribution is split
symmetrically across the side sectors; exact half-values are kept in code. A towards-wing
order requires an explicit left or right slot because choosing a direction would invent
match context.

All 19 ordinary role/order combinations are supported: goalkeeper normal; wingback and
winger normal/defensive/offensive/towards-middle; central defender normal/offensive/
towards-wing; inner midfielder normal/defensive/offensive/towards-wing; and forward
normal/defensive/towards-wing. Side-location variants are independent.

Set Pieces is intentionally absent from the seven ordinary open-play sectors, though it
remains in normalized state for future special-event work.

## Validation and unknowns

Only skills used by the role/order are required. Required fractional skills must be finite
in `[0, 21)`; form `[0, 9)`; stamina `[0, 10)`; and experience/loyalty `[0, 21)`.
Mother-club status, form, stamina, and experience must be known. Loyalty may be unknown
only when the known mother-club bonus supersedes it. Specialty must be known when it can
change the result. Unsupported combinations are rejected rather than filled with zero.

## API and plan comparison

`POST /api/training-plans/{plan_id}/players/{player_id}/contributions` accepts position,
side, order, and assumed weather. It returns current, after-each-block, and final projected
match-start vectors plus the final delta and applied modifiers. Factual form, experience,
loyalty, mother-club status, and specialty stay constant; only simulator-projected
trainable skills change. Stamina remains available in normalized state for the future
scalar layer but is not needed for the match-start vector.

## Deferred team layer discovered during research

HO also contains player sums, position overcrowding, team spirit, home advantage, match
attitude, coach/team modifiers, tactics, sector scale factors, and a nonlinear displayed-
sector conversion. The pinned scale factors are midfield `.312`, side defense `.834`,
central defense `.501`, central attack `.513`, and side attack `.615`, followed by
`pow(raw * scale, 1.2) / 4 + 1` in that model.

Those values are recorded solely as Milestone 6 research. **None of that layer is
implemented or invoked in Milestone 5.** Its semantics and ordering require a separate
audit. No lineup enumeration, comparison, scoring, or recommendation belongs here.

## Remaining uncertainty and manual validation

- HO's coefficients and experience curve are community estimates and can change.
- The match-average stamina ambiguity is resolved: it is a post-conversion scalar factor
  in HO and is intentionally absent from this raw-vector API.
- Fractional skills are plan estimates because CHPP exposes visible integer skills.
- Specialty weather modifiers cover deterministic base-rating effects, not special events.
- Public community position tables contain small rounded values differing from current HO;
  the pinned current HO source wins for this model version.
- Revalidate the pinned commit and golden cases before Milestone 6 builds a team layer.
