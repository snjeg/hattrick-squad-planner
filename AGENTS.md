# AGENTS.md

## Purpose

This repository is being developed with coding agents.

Agents should work autonomously while respecting PROJECT_SPEC.md and Hattrick CHPP restrictions.

## Authority

Before making product decisions, read:

1. PROJECT_SPEC.md
2. DECISIONS.md
3. relevant source code/tests

PROJECT_SPEC.md defines intended product behavior.

DECISIONS.md records implementation/product decisions already made.

Do not silently redefine the product.

## Autonomy

Make reasonable implementation decisions without asking the user.

Do not ask about:

* naming;
* folder structure;
* ordinary UI styling;
* test organization;
* library choices where alternatives are equivalent;
* minor refactors;
* implementation details with low user-facing impact.

Record meaningful assumptions in DECISIONS.md.

## Ask the user only when

* credentials or external access are required;
* a CHPP permission blocks progress;
* there are materially different product behaviors;
* an action could destroy or overwrite user data;
* security/privacy implications require explicit approval;
* required factual Hattrick behavior cannot be established reliably.

## Hattrick rules

Never:

* scrape Hattrick HTML;
* ask for Hattrick passwords;
* commit OAuth credentials;
* automate transfer bidding/listing;
* implement prohibited opponent-player tracking;
* invent CHPP permissions;
* use undocumented live endpoints without validation.

Prefer mock fixtures whenever live CHPP access is unnecessary.

## Engineering principles

* Python type annotations.
* TypeScript strict mode where practical.
* Domain logic separated from UI.
* External integrations isolated behind adapters.
* Hattrick formulas implemented as separately testable modules.
* Historical snapshots are append-only.
* Unknown values remain nullable instead of being invented.
* No magic constants without a source/comment.
* Formula coefficients should include source references in code or nearby documentation.
* Unit tests for important Hattrick domain rules.

## Scope discipline

Only implement the milestone currently requested.

Do not opportunistically build later optimizer features.

Future phases belong in PROJECT_SPEC.md until explicitly started.

## Verification

Before marking work complete:

* run backend tests;
* run frontend tests where configured;
* run linting/type checking;
* report failures honestly;
* update documentation if commands or architecture changed.

## Decision log

When making a meaningful assumption, add an entry to DECISIONS.md containing:

* date;
* decision;
* reason;
* alternatives if relevant;
* whether it may need revisiting.

Do not use DECISIONS.md as a verbose activity log.

## Communication

At completion of a task, provide:

1. concise summary;
2. files/features changed;
3. tests/checks run;
4. unresolved issues;
5. external input needed from the user.

Avoid asking follow-up questions when reasonable assumptions allow progress.
