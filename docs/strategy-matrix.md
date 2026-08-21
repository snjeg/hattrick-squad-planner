# Position × Skill × Tactical Context Matrix

## Purpose and boundary

The Strategy matrix describes the skills a desired football identity needs before a future
cycle optimizer chooses training. It is a framework-independent domain under
backend/app/strategy and is exposed by POST /api/strategy/matrix.

The matrix is not a lineup selector, team-rating calculator, target-skill prescription or
training recommendation.

## Two independent layers

### Direct positional contribution

Direct contribution means that a skill contributes to one or more of the seven ordinary
open-play match sectors for that position/order. The matrix reads
POSITION_ORDER_WEIGHTS from backend/app/contribution/coefficients.py. It does not copy or
maintain a second coefficient table.

Primary source:

- Hattrick Organizer commit b58f36e2eecc98ba14d88be49c3042c575698134,
  RatingPredictionModel.initRatingContributionParameterMap;
- existing audit: docs/player-contribution-engine.md;
- community cross-reference: https://wiki.hattrick.org/wiki/Contribution.

For one cell, coefficient_total is the sum of that skill's raw coefficients across all
sectors in the canonical left/center representation. Left/right mirror variants are
equivalent and are not duplicated as separate visual rows. Individual orders remain
separate.

Set Pieces has no ordinary seven-sector coefficient in the pinned contribution model, so
its direct value is zero. A tactic can still give it a separate tactical highlight.

### Tactical relevance

Tactical relevance is an immutable overlay. It does not alter direct coefficients,
normalized values or dots. The overlay describes skills the current Rules say contribute to
tactic strength or execution:

| Tactic | Matrix overlay | Evidence represented |
| --- | --- | --- |
| Normal | None | Normal has no tactic-specific skill requirement. |
| Attack in the Middle | Passing for every outfield role | Rules say total outfield Passing determines tactic skill; no invented per-role weight. |
| Attack on Wings | Passing for every outfield role | Same source statement as AIM. |
| Counter Attacks | Passing primary and Defending supporting for wingbacks/central defenders | Rules state only defenders contribute and Passing counts twice Defending. Relative weights 1.0 and 0.5 preserve that ratio, not a complete CA formula. |
| Pressing | Defending for every outfield role | Rules identify total outfield Defending. Stamina, experience and Powerful specialty also matter but are outside the seven columns. |
| Play Creatively | None in the seven skill cells | Rules say PC has no specific contributing skill or tactic level; specialties matter. |
| Long Shots | Scoring primary and Set Pieces supporting for every outfield role | Rules state Scoring counts three times Set Pieces. Relative weights 1.0 and 1/3 preserve that ratio, not the event formula. |

Tactic audit source checked 2026-08-21:

- Hattrick Rules, Match tactics:
  https://wiki.hattrick.org/wiki/Rules
- Hattrick Wiki tactic overview:
  https://wiki.hattrick.org/wiki/Tactics
- Counter Attacks community context:
  https://wiki.hattrick.org/wiki/Counter-attacks

The Rules page is the source of the implemented skill relationships. The tactic overview and
community article provide context only. No Hattrick Organizer tactic-strength coefficients
are used by this overlay.

## Dots and normalization

Dots show direct importance within one position/order profile:

1. Sum raw direct coefficients per skill across sectors.
2. Divide each sum by the maximum skill sum in that row.
3. Keep zero as zero dots.
4. Quantize positive normalized values into equal thirds with
   ceil(3 × normalized relevance), capped at three.

This gives:

- greater than 0 through 1/3: one dot;
- greater than 1/3 through 2/3: two dots;
- greater than 2/3 through 1: three dots.

The API returns raw per-sector coefficients, coefficient_total, normalized_relevance and
dot_count. The UI tooltip exposes these values. This is a documented visualization choice,
not a claim that Hattrick uses three importance bands.

Color encodes tactical level independently:

- none: no overlay;
- supporting: a sourced secondary/less-weighted input;
- primary: the primary or sole sourced skill input.

## Formation preferences

The API validates preferred formations against the existing team-rating LEGAL_FORMATIONS
set and echoes them in StrategyPreferences. The UI initially selects none; there is no
developer-defined universal default.

Milestone 9 keeps preferences request-scoped. Persistence is deferred until team/user
ownership is modeled, avoiding a global singleton preference record that would be wrong for
hosted use. The typed contract is ready for the next optimizer.

## Determinism and mutation safety

- role, order, skill, coefficient and formation ordering are fixed;
- coefficient and overlay mappings are immutable;
- building any tactic matrix leaves the contribution mapping unchanged;
- identical preferences serialize identically;
- strategy calls do not read or write factual player tables.

## Known uncertainty

- HO contribution coefficients are a pinned high-confidence community model, not official
  disclosure.
- AIM/AOW and Pressing expose qualitative participation only because this milestone does
  not have a reliable complete numerical tactic-strength formula.
- CA and Long Shots preserve officially documented relative input ratios but do not claim a
  full tactic-level or outcome formula.
- Pressing stamina/experience/specialty and Play Creatively specialties cannot be expressed
  in the seven requested skill columns; notes make those omissions explicit.
- The matrix describes requirements. It does not establish universal target skill levels.
