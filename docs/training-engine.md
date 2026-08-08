# Senior training engine reference

## Reference revision and scope

The primary reference is Hattrick Organizer (HO) commit [`31622ccd42e104e21a853122ffd269bd9e98dc88`](https://github.com/ho-dev/HattrickOrganizer/commit/31622ccd42e104e21a853122ffd269bd9e98dc88), dated 2026-06-22. A direct default-branch audit on 2026-08-08 confirmed that this was still the repository HEAD. This milestone translates the current senior Schum predictor into independent Python domain code; it does not copy the Java design and does not implement youth training.

Exact HO references used:

- [`core/training/WeeklyTrainingType.java`](https://github.com/ho-dev/HattrickOrganizer/blob/31622ccd42e104e21a853122ffd269bd9e98dc88/src/main/java/core/training/WeeklyTrainingType.java): Schum formula, skill breakpoint, coach/assistant/intensity/stamina/age factors, time combination, cap, coefficients, and osmosis rates.
- [`core/training/TrainingPerPlayer.java`](https://github.com/ho-dev/HattrickOrganizer/blob/31622ccd42e104e21a853122ffd269bd9e98dc88/src/main/java/core/training/TrainingPerPlayer.java): player age at the training date and the value passed to the formula.
- [`core/training/TrainingPerWeek.java`](https://github.com/ho-dev/HattrickOrganizer/blob/31622ccd42e104e21a853122ffd269bd9e98dc88/src/main/java/core/training/TrainingPerWeek.java): weekly training inputs.
- [`core/model/player/Player.java`](https://github.com/ho-dev/HattrickOrganizer/blob/31622ccd42e104e21a853122ffd269bd9e98dc88/src/main/java/core/model/player/Player.java): actual senior match-sector-to-training-minute reconstruction.
- [`core/model/constants/TrainingConstants.java`](https://github.com/ho-dev/HattrickOrganizer/blob/31622ccd42e104e21a853122ffd269bd9e98dc88/src/main/java/core/model/constants/TrainingConstants.java): supported configuration bounds.
- `core/training/type/` classes selected by `WeeklyTrainingType.instance`: `GoalkeepingWeeklyTraining`, `DefendingWeeklyTraining`, `PlaymakingWeeklyTraining`, `CrossingWeeklyTraining`, `ShortPassesWeeklyTraining`, `ScoringWeeklyTraining`, `SetPiecesWeeklyTraining`, `ShootingWeeklyTraining`, `ThroughPassesWeeklyTraining`, `DefensivePositionsWeeklyTraining`, and `WingAttacksWeeklyTraining`. These define trained skills, position sectors, bonus sectors, and type-specific osmosis.

## Formula

For one trained skill in one weekly update:

```text
gain = min(1,
  coefficient_percent
  * skill_factor
  * coach_factor
  * assistant_factor
  * intensity_factor
  * stamina_factor
  * age_factor
  * effective_time_factor
  * 0.01
)
skill_after = skill_before + gain
```

The skill factor uses the visible integer part of the fractional skill. HO documents the
formula input as visible skill 0-20, while `Player.getSub4Skill` retains a separate
subskill in 0.0-0.999. The engine therefore accepts fractional skills in `[0, 21)`,
including values such as `20.25`, and rejects 21.0:

```text
visible skill < 9: 16.289 * exp(-0.1396 * visible_skill)
visible skill >= 9: 54.676 / visible_skill - 1.438
```

Inputs and factors:

| Input | Implemented factor / bound |
| --- | --- |
| head coach | weak 4 = 0.7343; inadequate 5 = 0.8324; passable 6 = 0.92; solid 7 = 1.0; excellent 8 = 1.0375 |
| assistant coaches | `1 + 0.035 * total_levels`; HO uses total skill levels, 0-10, not assistant count |
| intensity | `intensity / 100`; accepted configuration 1-100 |
| stamina share | `1 - stamina_share / 100`; accepted configuration 10-100 |
| age | `54 / (integer_years + 37)` for senior ages 17+ |

All validation errors raise `ValueError`; invalid HO inputs are not silently clamped.

## Exact age representation

`HattrickAge` stores `years` plus `days` in 0-111. One Hattrick year is 112 days, so a fractional representation is `years + days / 112`. `advance_week()` adds seven days and correctly rolls `17y111d` to `18y6d`.

HO's `TrainingPerPlayer` computes an age value at the training date but the current call into `WeeklyTrainingType.calculateSkillIncreaseOfTrainingWeek` passes an integer age. The engine therefore preserves exact days for deterministic week-by-week progression while using integer years in the pinned HO age factor. It intentionally does not invent within-year interpolation.

## Training definitions and eligibility

Position abbreviations: GK goalkeeper, WB wingback, CD central defender, W winger, IM inner midfielder, F forward.

| Training type | Skill(s) | Coefficient | Full positions | Half-rate positions | Osmosis positions/rate |
| --- | --- | ---: | --- | --- | --- |
| Goalkeeping | goalkeeping | 5.10% | GK | - | - |
| Defending | defending | 2.88% | WB, CD | - | GK, W, IM, F at 1/6 |
| Playmaking | playmaking | 3.36% | IM | W | GK, WB, CD, F at 1/8 |
| Winger (Crossing) | winger | 4.80% | W | WB | CD, IM, F at 1/8; GK receives none |
| Short Passes | passing | 3.60% | W, IM, F | - | GK, WB, CD at 1/6 |
| Scoring | scoring | 3.24% | F | - | GK, WB, CD, W, IM at 1/6 |
| Set Pieces | set pieces | 14.70% | all | - | - |
| Shooting | scoring and set pieces | 1.50% each | all | - | - |
| Through Passes | passing | 3.15% | WB, CD, W, IM | - | GK, F at 1/6 |
| Defensive Positions | defending | 1.38% | GK, WB, CD, W, IM | - | F at 1/6 |
| Wing Attacks | winger | 3.12% | W, F | - | GK, WB, CD, IM at 5/39 |

Set Pieces adds a separate 25% time bonus for minutes in HO's `Goal` or
`SetPiecesTaker` sectors. The bonus is capped at 90 minutes but can raise the total
effective factor to 1.25. A player with 10 goalkeeper minutes and 80 outfield minutes
therefore receives 10 goalkeeper bonus minutes, not 90. In the normalized resolver,
`is_set_piece_taker=True` means the player held that role throughout the supplied
appearances; exact role changes remain the caller's responsibility.

Eligibility is not embedded in the formula. `TrainingDefinition` describes the rates and `resolve_training_exposure` converts positional appearances into full, partial, osmosis, and bonus minutes. `effective_time_factor` then applies HO's priority:

1. use full-rate minutes, capped at 90;
2. fill the remaining direct cap with half-rate minutes;
3. fill any remaining direct cap with osmosis minutes;
4. add an independently capped eligible bonus.

Thus 36 full Playmaking minutes plus 90 winger minutes yields `(36 + 54 * 0.5) / 90 = 0.7`. No direct full/partial/osmosis combination can consume more than 90 weekly minutes. Each positional appearance is also constrained to 0-90 minutes.

## Osmosis

HO includes background or "osmosis" training in the same weekly predictor but with explicit type-specific positional sectors and rates. This implementation keeps it in the named `osmosis_minutes` component, separate from direct full/partial minutes. It is never silently granted by the calculation engine; a caller must supply or derive an eligible exposure.

### Current-source discrepancy found during audit

`CrossingWeeklyTraining` contains inconsistent representations: its active `osmosisTrainingSectors` list contains central defence, inner midfield, and forward, while its older `_PrimaryTrainingSkillOsmosisTrainingPositions` array also contains goalkeeper. Current historical training calculation in `Player.calculateWeeklyTraining` derives minutes from the sector lists. The engine therefore follows the active sector path and gives a goalkeeper no Winger/Crossing osmosis. This corrects the initial Milestone 2 implementation, which had generalized the rule to all positions except winger and wingback.

## Fractional results and golden references

The engine accepts a numeric fractional skill and returns `skill_before`, `skill_gain`, `skill_after`, visible values before/after, `skill_up`, and the effective training fraction. It does not persist or infer subskills.

Golden tests are hand-evaluated from the pinned `WeeklyTrainingType.java` formula with a relative/absolute tolerance of `1e-12`:

| Case | Inputs (in addition to fractional skill) | Expected gain |
| --- | --- | ---: |
| full Playmaking | age 17y0d, skill 7.25, solid coach, assistants 10, intensity 100, stamina 10, 90 full | 0.2502749659204538 |
| partial Winger | age 19y7d, skill 9.2, passable coach, assistants 8, intensity 90, stamina 15, 90 half | 0.09667712102400002 |
| mixed Playmaking | age 18y43d, skill 8.4, excellent coach, assistants 5, intensity 100, stamina 20, 36 full + 90 partial | 0.12007668581577603 |
| Defending osmosis | age 17y0d, skill 10.5, solid coach, assistants 10, intensity 100, stamina 10, 90 osmosis | 0.0235006272 |
| Set Pieces bonus | age 17y0d, skill 12.1, solid coach, assistants 10, intensity 100, stamina 10, 90 full + 90 bonus | 0.6961874062500002 |

## Uncertainties and manual validation

- HO intentionally feeds integer age years to this formula despite calculating training-date age more precisely. A future change to interpolate age-days would diverge from the pinned reference and needs evidence from Hattrick or a newer HO revision.
- Osmosis and the Set Pieces goalkeeper/taker bonus are faithfully exposed because current HO predicts them. Before using them for automated long-range planning, compare representative cases in the HO UI and current official Hattrick training documentation. In particular, manually verify the Crossing goalkeeper inconsistency described above.
- Match position/minute reconstruction is out of scope. Callers are responsible for producing accurate normalized exposures, including substitutions, set-piece-taker role changes, and multiple matches.
- HO's formula caps a single weekly gain at 1.0. This is preserved, but boundary cases should be compared against a current HO installation before Milestone 3.
- Community formulas can change. Revalidate the pinned revision, all coefficients, and golden cases before building optimization on top.
