# Decision Log

This file records product and architectural decisions that materially affect future development.

---

## 2026-08-10 - Roster scenarios return evidence, not action policy

**Decision:** Milestone 7 represents sales, purchases, and planning-role changes as explicit
checkpoint transitions. It evaluates the resulting squad, wages, aggregate training capacity,
and low/base/high manual transfer cash against a synthetic no-transition baseline. It does not
rank scenarios or infer Keep/Sell/Buy labels.

**Reason:** The application must be able to explain that a sale has little modeled competitive
cost, saves wages, frees capacity, and raises assumed capital without silently turning those
facts into a recommendation. Recommendation policy belongs to Milestone 8.

**Consequence:** Transitions run after a completed block in deterministic sell/buy/role order;
their wage effects apply to the following period. Hypothetical players are scenario-local,
complete labeled assumptions. Operating and transfer cash remain separate, and existing
bounded-search/wage uncertainty is preserved in outputs.

**Revisit:** Milestone 8 may add versioned objective weights and recommendation history, but it
must consume these scenario primitives rather than bypass their timing and accounting rules.

---

## 2026-08-09 — Squad quality is decomposed and search-bounded

**Decision:** Milestone 6B evaluates the whole squad through deterministic bounded candidate
search over every Milestone 6A formation. Planning roles remain checkpoint-local. The optional
competitive composite weights peak strength 40%, one-player depth resilience 25%, formation
flexibility 20%, and rotation quality 15%; all components remain separately available.

**Reason:** Best-XI strength alone rewards brittle squads, and double-counting it alongside an
identical best formation would obscure depth. A bounded beam is locally interactive and
traceable for 20–25 players without pretending to be the future global optimizer.

**Consequence:** Results are labeled “best found,” left/right mirror pruning relies on symmetric
v1 profile weights, and replacement sensitivity performs an equivalent bounded re-search for
one unavailable starter at a time. Transfer, finance, acquisition, and automatic training
decisions remain outside this domain.

---

## 2026-08-09 — Team ratings evaluate explicit lineups at match start

**Decision:** Milestone 6A accepts one user-selected legal XI and explicit match context. It
reuses the Milestone 5 contribution primitive, applies HO overcrowding before experience,
aggregates seven sectors, then applies verified team factors and nonlinear conversion. It
does not select or recommend players.

**Reason:** This preserves the pinned HO operation order and creates a deterministic future
evaluation primitive without allowing the milestone to become an optimizer.

**Consequence:** Match-average ratings, formation confusion, and squad-level reasoning are
deferred. HO applies stamina inside each minute's aggregation, so match-start output is safer
than a scalar average approximation.

---

## 2026-08-08 — Product focus

**Decision:** The product is a squad-development and training-planning tool, not primarily a lineup planner.

**Reason:** The main problem is optimizing multi-season training, squad construction, wages, finances and player exits.

---

## 2026-08-08 — No universal training cycle

**Decision:** Do not hard-code a universal sequence such as PM → Passing → Defending → Winger → Scoring.

**Reason:** Optimal training depends on the current squad, finances, player ages, wage pressure, training-slot availability and strategic goal.

Use rolling re-evaluation instead.

---

## 2026-08-08 — Current-first planning

**Decision:** Long-term optimization should recommend the next training block while simulating multiple future blocks.

**Reason:** New youth prospects, player sales, purchases, wage changes and changing finances can invalidate a fixed multi-season plan.

---

## 2026-08-08 — Player statuses

**Decision:** Support Keep / Maybe / Sell as strategic user inputs.

**Reason:** The optimizer cannot know subjective long-term commitment to a player from CHPP data alone.

---

## 2026-08-08 — Spare training slots

**Decision:** Unused training slots should be considered profit opportunities rather than automatically wasted.

**Reason:** Managers can train additional players and sell them to finance the long-term squad.

---

## 2026-08-08 — Selling does not equal training switch

**Decision:** A sale trainee should not automatically be sold when his primary training phase ends.

**Reason:** A later overlapping training block, such as Passing after Playmaking, may add valuable secondary skills before sale.

---

## 2026-08-08 — CHPP architecture

**Decision:** CHPP will be an external data adapter feeding normalized internal domain objects.

**Reason:** Core simulation and tests must work without live CHPP access and should survive XML/API changes.

---

## 2026-08-08 — Historical snapshots

**Decision:** Persist player identity separately from append-only player snapshots.

**Reason:** Historical observations are needed later for subskill estimation, training reconstruction and wage tracking.

---

## 2026-08-08 — CHPP safety

**Decision:** Use documented and approved CHPP interfaces only. Never scrape Hattrick HTML.

**Reason:** Compliance with Hattrick CHPP rules is a hard product constraint.

---

## 2026-08-08 — Initial technology

**Decision:** Use React + TypeScript for frontend and FastAPI + SQLAlchemy for backend.

Use SQLite locally through DATABASE_URL and retain compatibility with PostgreSQL.

**Reason:** Simple local development while supporting a future hosted/multi-user version.

---

## 2026-08-08 — Training formula reference

**Decision:** Hattrick Organizer / Schum training calculations will be the primary implementation reference for the training engine.

**Reason:** They provide an established community implementation with fractional skill progression.

Training logic must be validated before optimization is built.

---

## 2026-08-08 — Financial model

**Decision:** Separate operating cash flow from total cash flow.

**Operating cash flow** excludes player transfers.

**Total cash flow** includes transfers and other capital events.

**Reason:** This distinguishes a financially sustainable squad from a club whose finances depend on selling trainees.

---

## 2026-08-08 — Wage model

**Decision:** Wage pressure is part of optimization, not merely a display metric.

Foreign-player wage surcharge and nonlinear high-skill wage growth must be represented.

**Reason:** Training one primary skill indefinitely can become financially unsustainable.

---

## 2026-08-08 — Match contribution model

**Decision:** Future squad-strength calculations must use position/order-specific player contributions rather than raw skill totals.

**Reason:** Normal, defensive, offensive, towards-wing and other orders change the usefulness of each skill.

---

## 2026-08-08 — Tactical neutrality

**Decision:** The application must support different tactical philosophies.

The initial user prefers possession-oriented 3-5-2 / 4-5-1 play, but this must not be hard-coded as universally optimal.

---

## 2026-08-08 — Transfer valuation

**Decision:** Do not build an unauthorized transfer-market crawler.

Initially support unknown or user-assisted valuations.

**Reason:** Market-value modelling must remain within CHPP restrictions.

---

## 2026-08-08 — Milestone 1

**Decision:** First implementation milestone is only:

CHPP authentication/integration foundation → own senior squad import → normalization → player/snapshot persistence → squad display.

Do not implement training optimization yet.

**Reason:** Reliable data ingestion must exist before simulation and optimization.

---

## 2026-08-08 - Mock-first CHPP development

**Decision:** Use a `CHPPClient` boundary with mock and OAuth 1.0a implementations. Local development defaults to a fictional XML fixture; live downloads occur only from the manual sync action.

**Reason:** Milestone 1 must be testable without credentials, while production-shaped ingestion must remain isolated behind an adapter and comply with CHPP restrictions.

**Revisit:** Update the configured players XML version only after validating the current approved CHPP interface.

---

## 2026-08-08 - Snapshot append semantics

**Decision:** A successful sync upserts stable player identity fields and always inserts a new `PlayerSnapshot` for every observed player. The latest-squad view orders observations by `observed_at`, then `sync_run_id`, then snapshot `id`, all descending.

**Reason:** Repeated manual imports must preserve history for later subskill and wage analysis. Source fetch timestamps alone cannot identify separate observations when replaying fixtures.

---

## 2026-08-08 - Development schema and credentials

**Decision:** Use SQLAlchemy's portable types and `DATABASE_URL`, with direct schema creation for Milestone 1. In live local mode, the OAuth access token is stored in the ignored SQLite database.

**Reason:** This keeps local setup small and allows future PostgreSQL use without coupling domain code to SQLite.

**Status:** The direct-schema portion is superseded by the managed-schema decision below. Appropriate encryption or an external secret store is still required before any hosted or multi-user release; plaintext OAuth-token storage is acceptable only for local development.

---

## 2026-08-08 - Managed schema evolution

**Decision:** Alembic owns application schema evolution. FastAPI startup does not create tables. The initial migration represents the complete schema through Milestone 1.1 and can adopt the prior unversioned local SQLite schema.

**Reason:** Explicit, reviewable migrations are required for reliable SQLite development and future PostgreSQL deployment. Direct metadata creation remains only as a disposable test helper.

---

## 2026-08-08 - CHPP player field ownership

**Decision:** Stamina, form, experience, loyalty, injury level, cards, wage, and TSI are append-only snapshot observations. Specialty, nationality, and the mother-club bonus flag are identity metadata. Do not populate the existing mother-club team ID without a player-details response.

**Reason:** The current `players` XML exposes the observation values and `MotherClubBonus`, but not the mother club's identity. Separating mutable observations prevents syncs from overwriting history and avoids invented data.

---

## 2026-08-08 - Pinned senior training behavior

**Decision:** The Milestone 2 engine follows Hattrick Organizer commit `31622ccd42e104e21a853122ffd269bd9e98dc88`. It preserves exact Hattrick age-days for progression but uses integer years in the formula, matching HO. Direct, partial, osmosis, and Set Pieces bonus exposure remain explicit components.

**Reason:** A pinned implementation and named components make community-formula assumptions traceable and testable. Age-day interpolation or silently blending osmosis would invent behavior not present in the reference.

**Revisit:** Revalidate the pinned formula and representative golden cases against a current HO installation and official Hattrick behavior before Milestone 3 optimization work.

The 2026-08-08 direct source audit found one HO-internal discrepancy for Winger/Crossing: the active match-sector list excludes goalkeeper from osmosis, while an older position-ID array includes it. Follow the sector list used by `Player.calculateWeeklyTraining`; goalkeeper therefore receives no Winger osmosis. This supersedes the initial generalized mapping that treated every non-winger/non-wingback position as osmosis-eligible.

---

## 2026-08-09 - Reproducible manual-plan starting state

**Decision:** A training plan captures the latest completed sync plus an explicit mapping from each starting player to the exact factual `PlayerSnapshot` used. Later CHPP syncs do not alter existing plan inputs.

**Reason:** Manual simulations must remain reproducible and must never silently move to newer factual observations. A future refresh action must be explicit and may clone or deliberately rebase the plan.

---

## 2026-08-09 - Estimated subskills and projected-data boundary

**Decision:** Visible CHPP skills start simulations at `.00` unless the plan contains a same-visible-level manual override. Projected states remain in memory/API output and are never stored as factual `PlayerSnapshot` rows. Plans record the training-engine reference version.

**Reason:** CHPP does not reveal fractional subskills. Treating `.00` and projected results as estimates preserves the factual/hypothetical distinction while leaving an extension point for later inference.

**Revisit:** Define migration/recalculation policy before changing the pinned training formula or adding automatic subskill estimates.

---

## 2026-08-09 - Conservative two-match capacity validation

**Decision:** Validate manual assignments against aggregate minutes for two normal 90-minute lineups: position maxima, five-player defender/midfielder line maxima, eleven players per match, and 180 appearance minutes per player. Keep this capacity model separate from eligibility and training-speed calculations.

**Reason:** It rejects obvious impossible plans such as seven full IM trainees while supporting substitutions and mixed appearances without building a future-match simulator.

**Revisit:** Aggregate feasibility does not prove that every unusual mixed-minute allocation can be scheduled into two concrete lineups. Add an explicit lineup scheduler only if a later milestone requires it.

---

## 2026-08-09 - Wage estimates must expose low confidence

**Decision:** Treat imported CHPP wages as factual and hold them until a simulated
birthday. After a birthday, use a versioned community-derived approximation labeled
`approximate-low-confidence`; never present it as Hattrick's exact formula.

**Reason:** The current official rules expose only broad mechanics and surcharges. HO has
no forward wage predictor, while Foxtrick provides a reverse estimator with an explicit
goalkeeper placeholder. Manufacturing precision would be more harmful than a transparent
scenario estimate.

**Revisit:** Replace or recalibrate only after a complete current formula or a validated
live-data corpus is available. Verify birthday ordering, goalkeeper behavior, age discount,
and secondary-skill weights before optimization uses wage pressure.

---

## 2026-08-09 - Finance facts are plan-bound and append-only

**Decision:** A plan references the finance snapshot from the same completed sync as its
player snapshots. Economy, arena, and fixture imports append observations; user finance
assumptions live in a separate one-to-one scenario record.

**Reason:** Later syncs must not silently rewrite an existing scenario, and assumptions
must never be mistaken for CHPP facts.

---

## 2026-08-09 - Unknown future revenue remains an assumption

**Decision:** Do not infer attendance or future sponsor changes. Home-match revenue is
excluded until entered by the user. Beyond an explicit season boundary, sponsor income is
either user-supplied or excluded with a warning. Capital cash flow remains zero in this
milestone.

**Reason:** The imported current-week economy and fixture schedule do not establish future
attendance or next-season sponsor values. Explicit omissions preserve traceability and
keep operating sustainability separate from transfers.

Current `IncomeFinancial` and `CostsFinancial` observations are also excluded from future
weeks because balance-dependent interest is not a normal fixed recurring amount. Staff,
youth, and arena maintenance remain recurring until explicitly overridden.

---

## 2026-08-09 - Attendance is a traceable community scenario, not an exact formula

**Decision:** Use the eleven sourced community arena-demand rows as a versioned,
low-confidence seat-level baseline. Keep weather in a separate, explicit assumption table;
cap every section independently without substitution; and return four scenarios when
weather is unknown. Use official Manual prices and revenue-sharing rules.

**Reason:** No audited source publishes exact current attendance or weather coefficients.
Several tools output precise values, but that precision does not establish accuracy. The
separated tables are internally consistent, testable, and reusable for later stadium work.

**Revisit:** Calibrate only after importing a sufficient set of post-match `matchdetails`
observations, and preserve the original model version for reproducibility.

---

## 2026-08-09 - Individual contribution is a pre-team domain boundary

**Decision:** Pin the seven-sector individual contribution primitive to Hattrick Organizer
commit `b58f36e2eecc98ba14d88be49c3042c575698134`. Return raw match-start vectors with
explicit modifiers and model metadata. Keep all lineup/team
composition, displayed-sector conversion, tactics, ranking, and recommendation logic out
of Milestone 5.

**Reason:** HO's Schum implementation mixes individually attributable contributions with
a later team layer. Separating them makes current-versus-projected player comparisons
deterministic and reusable without accidentally creating an optimizer. The source audit
uncovered team scale factors and nonlinear conversion, but implementing those now would
cross the milestone boundary.

**Revisit:** Before Milestone 6, audit the full ordering of overcrowding, team spirit,
home/attitude/coach/tactics factors, stamina, and nonlinear sector conversion.

The follow-up call-path audit established that HO applies
`calcMatchAverageStaminaFactor` after `calcPlayerRating` has performed its nonlinear
`pow(..., 1.2) / 4` conversion. Applying that factor to every raw sector is not
mathematically equivalent, so Milestone 5 no longer exposes a raw match-average vector.

---

## 2026-08-10 - Recommendations use a bounded receding horizon

**Decision:** Optimize the same nine objective dimensions through versioned Team-first,
Balanced, and Profit-first weight profiles. Search every modeled training type using
bounded, pop-informed duration candidates and deterministic beam search. Recommend only
the immediate block; label later blocks projected/conditional and never claim global
optimality.

**Reason:** A fixed training cycle or exhaustive forever-plan would ignore squad shape,
depth, capacity, finances, wages, and new factual information. A bounded search is
inspectable, fast enough for interactive use, and honest about uncertainty.

**Revisit:** Recalibrate objective presets and search bounds only with versioned evidence.
Persist completed optimizer runs separately if recommendation-history comparison becomes a
product requirement; never persist intermediate trees or rewrite factual snapshots.

---

## 2026-08-10 - Transfer seasonality remains qualitative

**Decision:** Classify broad 16-week market windows with the versioned
`community-seasonality-v1` model, roll projected dates across seasons, and generate sale
events around pops, block ends, birthdays, stronger windows, and liquidity needs. Do not
apply automatic numeric price multipliers.

**Reason:** Community reports support broad timing effects but not a defensible exact
formula. Manager-supplied low/base/high values remain the monetary source of truth, while
training capacity, wages, capital, and competitive evidence can still make an immediate
sale preferable in a weak window.

**Revisit:** Add configurable timing multipliers only when backed by an explicit user model
or a traceable empirical dataset. Hour/day/deadline/list-price execution remains out of
scope.

---

## 2026-08-10 - Roster transitions compete inside bounded plan evaluation

**Decision:** Fully evaluated training finalists also compete against a small set of
Milestone 7 roster scenarios: top evidence-backed single sales, priced acquisitions only
for meaningful capacity gaps, and at most one top sale-plus-acquisition. Evaluate current
and block-boundary timing without real-market search or exhaustive combinatorics.

Static projected transfer values are sale evidence only. Until a defensible
training-path-sensitive resale model exists, remove transfer value from plan ranking and
renormalize the remaining weights. Switch timing uses an equal-horizon
continue-one-week versus switch-now marginal comparison, and all durations are additional
weeks after the factual `current_block_weeks_completed` state.

**Reason:** Post-hoc transfers could not change the chosen training plan, while a constant
transfer component gave Profit-first false discriminatory precision. The bounded joint
comparison fixes both errors without turning the milestone into a transfer optimizer.
