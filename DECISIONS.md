# Decision Log

This file records product and architectural decisions that materially affect future development.

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
