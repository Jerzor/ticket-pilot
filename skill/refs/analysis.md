# ticket-pilot - Step 2: analysis of a new / changed issue, questions to the backend

Part of the ticket-pilot skill. The ground rules from SKILL.md apply.

## Step 2 - analysis (always 2 independent agents)

Gather the context yourself first: description, history, attachments/mockups, parent issue, linked issues (1 level). Frontend sub-issues often have an empty description - the requirements live in the parent.
Then start **2 independent agents in parallel** (same brief: issue context + repo path, `model: "{{WORKER_MODEL}}"`). Neither sees the other's result. Each returns:

- frontend / backend split; whether it needs backend work, a consultation or business questions;
- **release vs backend:** explicitly "frontend can ship without backend: yes / no" + why (what would break in production if the frontend went first). Find the backend issue (sibling sub-issue, links) - number, status, assignee - and check the backend mirror for a branch / merge. Save `beTask`, `waitingForBe`, and for "no" a `releaseWhen` condition in `state.json`;
- a numbered, concrete "to do" list;
- what we reuse from the repo (files/components);
- risks / questions;
- an estimate in hours (half-hour steps, mid-level developer; specs only where `specs: true`);
- **relations to other issues** (same parent / user story / linked / anything in `state.json`): `independent` / `shared files` (which) / `code-dependent` (what exactly) / `shared questions`. Save as `issues.<nr>.related`;
- **an implementation plan** - for every "to do" item: which files change, the approach, what to reuse, i18n texts, specs. The code is later written by ONE agent, so the "how" is agreed here.

**Agreement ≥ 75%** when all hold:
- estimates: `min/max ≥ 0.75`,
- scope: ≥ 75% of the "to do" items (union of both lists) match,
- plan: ≥ 75% of the items use the same files and approach.

Below 75% → a **3rd agent (arbiter)** gets both results + the context and produces one resolved version. No resolution → show the user both versions and the differences.

The agreed version (scope + plan + estimate) goes to `{{DATA}}/analyses/<nr>.md`.

**Already estimated issue:** if the tracker already has an estimate (someone else made it), **never change it**. The agents' estimate is only a sanity check - add one warning line only when it is clearly higher (tracker < 0.75 × agents).

Also check branches for the issue number **and** the parent number (`git branch -a`, `git worktree list`, `git ls-remote --heads origin`).

## Questions to the backend

**API docs first.** When the backend issue reaches QA, check the contract yourself in the project's `apiDocs` (read-only; never "Try it out"). Compare with the frontend branch: endpoints, field names, types, limits, error codes. Mismatch → fix the frontend (implementer + review).

Only when neither the docs nor the backend code answer it, prepare a short message to the backend developer (casual, bullet points, with the issue number). **Never send it yourself** - the user sends it and pastes the answer back; then adapt the code and save the answer in `state.json → beAnswers`.
