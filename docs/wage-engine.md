# Approximate senior wage engine

## Confidence and scope

Milestone 4 does **not** claim to reproduce Hattrick's private wage formula. Current
factual wages come from CHPP and remain authoritative. A future wage is recalculated only
when the simulated player crosses a birthday, and that recalculation is labeled
`approximate-low-confidence` with model version
`approx-foxtrick-10158d18192f-2026-08-09`.

No current official or strong open-source source audited on 2026-08-09 exposed a complete
forward wage formula. Hattrick Organizer imports salary but does not predict it. Foxtrick
contains a community reverse skill-from-wage estimator, not an official forward model,
and its goalkeeper branch is explicitly a placeholder.

## Sources audited

- [Hattrick Rules](https://wiki.hattrick.org/wiki/Rules): wages are paid weekly; the
  documented base is EUR 250; salary depends on skills and age; foreign players add 20%;
  a specialty adds 10%.
- [Hattrick Wiki wage research](https://wiki.hattrick.org/wiki/Wages): community wage
  tables, birthday-update behavior, and research caveats. This is not official formula
  disclosure.
- [Foxtrick `psico.js` at commit `10158d1`](https://github.com/minj/foxtrick/blob/10158d18192fd0b9bd4046c6d7ef1d60985632b8/content/lib/psico.js): community outfield
  coefficients and high-skill discount used by the approximation.
- [HO economy parser at commit `31622cc`](https://github.com/ho-dev/HattrickOrganizer/blob/31622ccd42e104e21a853122ffd269bd9e98dc88/src/main/java/core/file/xml/XMLEconomyParser.java): confirms current salary is imported as a fact; no forward formula was found.

## Implemented approximation

For Defending, Playmaking, Passing, Winger, and Scoring, the engine evaluates Foxtrick's
community power curves. The largest component is counted fully and the other components
at 50%. Set Pieces adds 0.25% per level. Goalkeeping is linearly interpolated from the
community mono-skill table because Foxtrick's goalkeeper coefficients are unusable.

The engine then applies a community age discount after age 28, adds the EUR 250 base, and
adds the documented foreign (20%) and specialty (10%) surcharges. Surcharges are shown
separately. Inputs require all seven fractional skills in `[0, 21)` so uncertainty is not
hidden by invented missing values.

Characterization examples for a 20-year-old domestic player with all unlisted skills at
4.00:

| Skills | Estimated weekly wage |
| --- | ---: |
| Playmaking 10.00 | EUR 1,684 |
| Playmaking 10.00, Defending 9.00, Passing 8.00 | EUR 2,002 |
| Playmaking 10.00, foreign, specialty | EUR 2,189 |

These numbers test the implementation; they are not golden Hattrick outputs.

## Projection timing

The imported player wage is used until the weekly simulator advances the player into a
new Hattrick age year. The estimated wage then uses that week's projected fractional
skills and new integer age, and remains in force until another birthday. Every block
checkpoint and the plan end report per-player and squad weekly wages.

The exact ordering of a real Hattrick birthday and the wage update within the weekly
economic/training cycle has not been verified. The simulator currently advances training
and age, then applies the birthday estimate for that projected week. This must be checked
manually before decisions depend on a boundary week.

## Known uncertainty

- The skill curves are reverse-estimator research translated into a forward approximation.
- Community sources disagree about secondary-skill weighting; Foxtrick's active code uses
  50%, while some wiki prose describes lower high-skill weights.
- Goalkeeping uses table interpolation, not a verified formula.
- Age discount mechanics and exact birthday ordering are not officially verified.
- Loyalty, mother-club effects, currency conversion, and wage rounding may differ from the
  live game.

The model is suitable for scenario sensitivity only. Current CHPP salary is the only
value presented as factual.
