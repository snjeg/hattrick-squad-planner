# Hattrick Squad Development Planner — Project Specification

## Status

Draft v0.1.

This document defines the intended product direction and should be treated as the primary product specification for implementation decisions.

---

# 1. Product vision

Hattrick Squad Development Planner is a decision-support tool for managers of Hattrick.org.

Its main purpose is to answer:

**Given the squad, finances, training setup and development goals I have today, what should I train next, for approximately how long, which players should I keep or sell, which players should I acquire later, and what will those decisions do to my future team strength and wage bill?**

The product is not primarily a lineup planner and is not primarily a training-speed calculator.

The long-term goal is a flexible, multi-season squad-development planner.

---

# 2. Core product philosophy

There is no universal optimal Hattrick training cycle.

The best decision depends on:

* current squad;
* player ages and subskills;
* training type;
* training-slot availability;
* finances;
* player wages;
* nationality;
* specialties;
* long-term player roles;
* formation preferences;
* tactical style;
* resale opportunities;
* planning horizon;
* financial risk tolerance.

The system should therefore use a **rolling planning horizon**.

It should periodically re-evaluate the squad and recommend the next useful training block rather than hard-code a complete multi-season cycle in advance.

Example:

Current recommendation:

* Continue Playmaking for approximately 8–11 weeks.

Likely next block:

* Passing.

Reason:

* core midfielders still gain valuable PM;
* future wingers receive partial PM;
* sale trainees remain economically useful;
* projected wages remain sustainable;
* Passing becomes more attractive once enough relevant players are ready.

The switching point should emerge from the model rather than from a fixed rule such as “train PM until level 14”.

---

# 3. Target users

Initial users:

* the developer/user and friends who recently started Hattrick;
* managers who want to build a competitive team over multiple seasons;
* managers interested in efficient training cycles rather than isolated single-skill training;
* managers who want to combine sporting performance with trainee resale and financial sustainability.

The architecture should remain general enough to support different club strategies later.

---

# 4. Strategic modes

The long-term planner should support different optimization goals.

Possible modes:

## Team-first

Prioritize long-term squad strength.

## Profit-first

Prioritize transfer-value creation from training slots.

## Balanced

Balance long-term team development, wage sustainability and trainee resale.

These modes should modify optimization weights rather than create completely different engines.

---

# 5. Player classifications

Users should be able to classify players as:

* **Keep**
* **Maybe**
* **Sell**

The optimizer should treat these differently.

## Keep

Long-term core players.

Training plans should deliberately build useful multiskill profiles around them.

## Maybe

Players for whom the tool should compare alternative scenarios.

Example:

* keep academy prospect and develop him;
* sell academy prospect now;
* sell after another training block.

## Sell

Profit trainees or players not intended for the final squad.

They may still remain in the squad for additional useful training before sale.

A player marked Sell should not automatically be sold when a training block ends.

The tool should compare:

* selling now;
* retaining for the next compatible training block;
* wages during that period;
* opportunity cost of occupying the training slot;
* estimated change in sale value.

---

# 6. Training-cycle concept

Training cycles are central to the product.

Different training types can affect overlapping groups of players.

Examples:

## Playmaking

Typical usable slots:

* 6 full IM trainees;
* 4 partial winger trainees.

## Short Passing

Can train:

* 6 inner midfielders;
* 4 wingers;
* 6 forwards.

Approximately 16 useful players per training week.

## Scoring

Approximately:

* 6 full forward trainees.

## Defending

Approximately:

* 10 full defending-position trainees.

Core midfielders or wingers may temporarily play defensive positions during a defending block if developing DEF is useful to their eventual role.

## Winger

Full winger training plus partial wingback training.

The tool must not assume every training slot belongs to a long-term player.

Unused slots should be considered potential **profit-training slots**.

Example:

During a defending block:

* 3 core IMs;
* 3 future CDs;
* 2 future WBs;
* 2 profit trainees.

---

# 7. Player acquisition timing

Long-term players do not necessarily need to be purchased at the start of a development cycle.

The planner should eventually reason about **when a future player should enter the squad**.

Example:

If a future striker will receive no useful training during a long Playmaking phase, purchasing him at age 17 and leaving him idle may be inefficient.

However, he should ideally be acquired before a Passing block if Passing is part of his intended multiskill development.

General principle:

**Acquire a core player shortly before the first training phase that materially benefits him.**

---

# 8. Training engine

Training calculations should use researched Hattrick training formulas, with Hattrick Organizer / Schum implementations used as a primary reference.

Training should operate on fractional skill values.

Example:

PM 8.43 → PM 8.61

rather than simply:

PM 8 → 9 in X weeks.

The engine must support:

* exact age;
* age in days;
* current fractional skill;
* training type;
* current skill level;
* coach level;
* assistant coaches;
* training intensity;
* stamina share;
* training minutes;
* full training;
* partial training;
* training-position eligibility;
* birthdays during simulation.

Simulation should proceed week-by-week.

The next week's gain must use the player's updated fractional skill and age.

---

# 9. Subskill estimation

CHPP visible skills are integer levels.

The application should maintain its own player snapshots and eventually estimate fractional subskills from:

* previous snapshots;
* training history;
* known skill-ups;
* training minutes;
* training formula.

A newly connected player may initially have uncertain subskills.

The UI should distinguish:

* visible skill;
* estimated subskill;
* confidence level where useful.

Example:

Visible PM: 8

Estimated PM: 8.63

---

# 10. CHPP integration

The application should integrate directly with Hattrick CHPP.

CHPP should provide current factual club data where permitted.

Examples include:

* players;
* team information;
* training configuration;
* economy;
* stadium;
* fixtures;
* matches;
* relevant historical information allowed by CHPP.

Important design rule:

**The planner must consume normalized internal data rather than depend directly on raw CHPP responses.**

CHPP is an adapter/input source.

This allows development and testing using mock XML fixtures.

---

# 11. CHPP restrictions

The application must respect Hattrick CHPP rules.

Hard rules include:

* CHPP XML interfaces only;
* never scrape Hattrick HTML;
* never ask for or store Hattrick passwords;
* OAuth credentials/secrets must not be committed;
* user data downloads should be explicitly initiated where required by CHPP;
* no unauthorized scheduled/background syncing;
* no transfer bidding/listing automation;
* no opponent-player history tracking;
* no building prohibited scouting or spying databases;
* only use features/endpoints permitted for the approved CHPP application.

When uncertain, CHPP rules and approved application permissions take precedence over convenience.

---

# 12. Player snapshots

Player identity and player observations must be separate.

Core entities:

## Player

Stable identity information.

Examples:

* Hattrick player ID;
* team ID;
* name;
* nationality;
* mother club;
* specialty.

## PlayerSnapshot

Time-specific information.

Examples:

* fetched date;
* exact age;
* visible skills;
* estimated fractional skills;
* TSI;
* wage;
* form;
* experience;
* loyalty;
* injury/status where available.

Historical snapshots must never be overwritten.

They will later be used for:

* training-history reconstruction;
* subskill estimation;
* wage-history analysis;
* development tracking.

---

# 13. Wage model

Wages are a major optimization constraint.

Important considerations:

* wage growth is nonlinear at high skills;
* high single-skill players can become extremely expensive;
* foreign players have a 20% wage surcharge;
* wages change based on Hattrick's wage-update mechanics;
* multiskilling may provide better team utility per wage than pushing one primary skill indefinitely.

The planner should not use a simple fixed rule such as:

“Never train PM above 14.”

Instead it should compare marginal benefit against marginal future wage cost.

Example:

PM 15 → 16 may still be valuable.

PM 16 → 17 may provide too little extra team contribution relative to:

* training time;
* future wages;
* alternative Passing/Defending development.

---

# 14. Financial model

The application should distinguish:

## Operating cash flow

Recurring club economics excluding transfers.

Possible components:

Income:

* sponsor income;
* expected match income.

Costs:

* player wages;
* staff;
* youth;
* arena maintenance.

## Total cash flow

Operating cash flow plus:

* player purchases;
* player sales;
* arena expansion;
* extraordinary income/costs.

The purpose is to distinguish:

* financially sustainable squad;
* squad sustained primarily through trainee sales.

---

# 15. Fixed and dynamic finances

For short/medium-term projections, several financial components can be treated as relatively fixed until explicitly changed.

Examples:

* staff costs;
* youth costs;
* arena maintenance;
* sponsor income within the relevant period.

Arena maintenance changes if arena configuration changes.

Sponsor assumptions may be refreshed at season boundaries.

The major dynamic variables for the planner are:

* player wages;
* match income;
* player transfers.

---

# 16. Stadium and attendance

CHPP stadium data should be used to obtain:

* total capacity;
* seat types;
* arena maintenance;
* planned expansions where available.

Fixtures can be used to project future home-match revenue.

Attendance projections may initially use conservative/simple assumptions.

Later they can learn from the club's historical attendance.

Financial forecasts should clearly distinguish:

* known;
* estimated;
* projected.

---

# 17. Financial sustainability

The application should eventually estimate a sustainable wage range rather than require the user to manually define one.

Example:

Recurring revenue
minus
fixed non-player expenses
=========================

approximate recurring player-wage capacity.

The user should still be able to choose financial attitude, such as:

* Conservative;
* Balanced;
* Aggressive / invest from reserves.

The planner may allow temporary operating losses if sufficient cash reserves exist.

---

# 18. Transfer-value uncertainty

The application should not assume that it can perfectly predict player market value.

CHPP restrictions must be respected.

V1 should not scrape Transfer Compare or create an unauthorized market database.

The application should initially support user-assisted valuation.

For a player, show possible exit points:

* sell now;
* after current training block;
* after next compatible training block.

Example:

Now:
PM 8 / PAS 5

After PM:
PM 11 / PAS 5

After Passing:
PM 11 / PAS 8

The planner should calculate exact/modelled factors such as:

* age;
* projected skills;
* wage;
* training weeks consumed;
* opportunity cost.

Market value may initially be:

* manually entered;
* unknown;
* estimated later from compliant data.

---

# 19. Academy prospects

Youth-academy prospects should be treated as possible long-term core players or sale opportunities.

The planner should allow scenario comparison.

Example:

Prospect reaches senior team with PM 8.

Scenario A:
Keep and incorporate into long-term PM/Passing/Defending development.

Scenario B:
Sell immediately.

Scenario C:
Train through another compatible development block and sell later.

Long-term mother-club/loyalty effects should be accounted for in match contribution where applicable.

---

# 20. Player contribution engine

Raw skill totals are not sufficient.

Different skills contribute differently depending on:

* position;
* individual order;
* side;
* formation.

The application should eventually implement the Hattrick skill-contribution model.

Player performance should be represented as contributions to team sectors:

* left defence;
* central defence;
* right defence;
* midfield;
* left attack;
* central attack;
* right attack.

The same player can produce different contribution vectors depending on role.

Example inner midfielder roles:

* Normal;
* Defensive;
* Offensive;
* Towards Wing.

Other roles include, where applicable:

* offensive/defensive/towards-middle wingbacks;
* winger normal/defensive/offensive/towards-middle;
* central defender normal/offensive/towards-wing;
* forwards normal/defensive/towards-wing.

Contribution coefficients should be sourced from documented Hattrick/community references and cross-checked with Hattrick Organizer where possible.

---

# 21. Formation effects

The match-contribution engine must eventually account for formation/overcrowding effects.

It must not simply calculate each player's contribution independently and add them together.

Formation effects and positional penalties/modifiers must be applied after individual contributions where appropriate.

---

# 22. Preferred tactical style must remain configurable

The product must not hard-code a single football philosophy.

The initial developer/user prefers a possession-oriented approach and commonly uses:

* 3-5-2;
* 4-5-1.

However, the application must remain useful for other styles.

Tactical styles may include:

* Normal;
* Attack in the Middle;
* Attack on Wings;
* Counter Attacks;
* Pressing;
* Play Creatively;
* Long Shots.

Different tactical styles change the usefulness of certain skill combinations.

Example:

Passing on defenders may have little direct normal defensive contribution, but may become valuable for Counter Attacks or other tactical contexts.

---

# 23. Possession-style planning

A possession-focused squad will usually place high value on Playmaking.

However, the planner should avoid producing extremely expensive single-skilled midfielders by default.

It should compare alternatives such as:

PM-heavy midfielder

versus

multiskill midfielder with lower PM but higher:

* Passing;
* Defending;
* Winger;
* Scoring.

Example conceptual comparison:

PM 17 / PAS 6 / DEF 5

versus

PM 14 / PAS 11 / DEF 10.

The correct answer must come from projected match contribution, wages and training cost, not from a fixed preference.

---

# 24. Tactics

Tactics should later modify lineup/squad evaluation.

Examples:

## Attack in the Middle

Passing across relevant outfield players contributes to tactical strength.

## Attack on Wings

Passing and wing attack structure become strategically important.

## Counter Attacks

Defender Passing becomes significantly more valuable.

## Pressing

Defending/stamina profiles matter.

## Play Creatively

Specialties become especially relevant.

## Long Shots

Scoring and Set Pieces profiles become important.

Tactics are not part of Milestone 1 but the architecture should not prevent them later.

---

# 25. Specialty

Player specialty should be stored from the beginning.

Specialties may influence:

* player valuation;
* tactical flexibility;
* special events;
* eventual lineup optimization.

The first milestone only needs to persist/display specialty.

---

# 26. Optimization philosophy

The final optimizer should not simply maximize:

* total skills;
* team rating;
* transfer value.

A future objective may combine:

Team contribution
+
future player value
-------------------

## wage cost

## capital usage

wasted training capacity.

Conceptually:

Score =
TeamStrength

* α × TransferValue
  − β × WageCost
  − γ × CapitalUsed
  − δ × WastedTraining.

Weights should vary by strategy mode.

---

# 27. Training-slot efficiency

Every available training slot should eventually be classified as:

* core-player training;
* future-team training;
* profit training;
* wasted training.

A useful metric may be:

Useful training received
divided by
available training capacity.

The planner should identify inefficient phases where many training slots have no useful recipient.

---

# 28. Rolling optimizer

The final planner should repeatedly answer:

* What should I train next?
* How long should I approximately continue?
* Which players should stay?
* Which players can be sold?
* Which players should I buy before the next block?
* What happens to wages?
* What happens to operating cash flow?
* What happens to team performance?
* Which alternative plan is close in quality?

The recommendation should include reasoning.

Example:

Recommended:
Continue PM approximately 8–11 weeks.

Why:

* three core IMs still receive high-value PM;
* two long-term wingers receive useful partial training;
* sale trainees remain worth retaining;
* wage trajectory remains safe.

Likely next:
Passing.

Preparation:
Acquire 2–3 forward prospects shortly before switching.

---

# 29. Scenario comparison

The application should eventually compare plans rather than expose only one answer.

Example:

## Team-first

PM → Passing → Defending

Higher final team strength.

## Balanced

PM → Passing → partial sale → Defending

Slightly weaker squad but better cash position.

## Profit-first

Longer PM trainee turnover.

Higher cash generation but slower first-team development.

---

# 30. MVP / Milestone 1

The first implementation milestone should NOT implement the optimizer.

Milestone 1 should establish reliable data ingestion and storage.

Required:

1. React + TypeScript frontend.
2. FastAPI backend.
3. SQLAlchemy persistence.
4. SQLite development database with easy future PostgreSQL migration.
5. CHPP OAuth client abstraction.
6. Mock CHPP XML fixtures.
7. Import authenticated user's own senior squad.
8. Normalize player data.
9. Persist player identities.
10. Persist historical player snapshots.
11. Manual user-triggered CHPP Sync action.
12. Squad table.

Squad table should include:

* player;
* exact age;
* GK;
* DEF;
* PM;
* WING;
* PAS;
* SC;
* SP;
* TSI;
* wage;
* foreign status;
* specialty.

Display age like:

18y 43d.

Use numeric Hattrick skills internally.

---

# 31. Later milestones

## Milestone 2 — Training engine

Implement and verify Hattrick Organizer / Schum-based training calculations.

## Milestone 3 — Manual training planner

Allow users to create training blocks and simulate future skills.

## Milestone 4 — Wage and finance projection

Add future wages, recurring finances, stadium and fixtures.

## Milestone 5 — Player contribution engine

Implement position/order/sector contribution calculations.

## Milestone 6 — Scenario tools

Keep / Maybe / Sell comparisons and player-entry timing.

## Milestone 7 — Rolling optimizer

Recommend training blocks and squad-development actions.

## Milestone 8 — Advanced tactics / lineup evaluation

Evaluate squad flexibility across formations, orders and tactics.

---

# 32. Non-goals

The application should not:

* submit lineups automatically;
* bid on players;
* list players automatically;
* scrape Hattrick;
* track prohibited opponent-player history;
* promise exact match-result prediction;
* pretend player market value is known when it is not;
* assume one universal training cycle is optimal.

---

# 33. Implementation principle

Keep these engines separate:

1. CHPP data ingestion.
2. Player/snapshot storage.
3. Training simulation.
4. Wage calculation.
5. Financial projection.
6. Player contribution.
7. Formation/tactics evaluation.
8. Transfer-value estimation.
9. Optimization.

They may interact through normalized domain objects but should not be tightly coupled.

This is important because several formulas will evolve independently and need separate validation.

---

# 34. Validation principle

Whenever possible, calculations should be tested against established external references.

Examples:

* Hattrick Organizer training outputs;
* documented Hattrick skill contribution tables;
* current Hattrick CHPP XML;
* known current wage examples.

Never silently invent formulas when the exact behavior is uncertain.

Unknowns should be documented in DECISIONS.md or research notes.
