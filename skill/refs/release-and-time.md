# ticket-pilot - release queue, time log, handing over to QA

Part of the ticket-pilot skill. The ground rules from SKILL.md apply.

## Release queue

When the user writes "release <nr>" **or** the issue passed code review without a dispute:

1. **Backend condition:** if the frontend needs the backend, it goes to QA only when the backend is **actually released** (merged to `main` in the mirror, the backend issue in QA or later, or confirmed by the user). A backend issue still "in progress" does not block if the code is merged. A frontend that does not need the backend ships on its own.
   **Automatic release:** the issue waited for the backend, the backend shipped and the API docs match the frontend → release without asking and report after the fact. Mismatch → fix, review, release.
2. **Git (in the worktree):** `git fetch origin`, `git merge origin/main` (merge, not rebase - no force-push). Resolve conflicts yourself. A non-trivial conflict (anything beyond imports, side-by-side translations, formatting) → a **separate review of the resolution only** (`git show --remerge-diff HEAD`) with the same thresholds as code review. Then checks again. Push.
3. **GitLab** (no CLI → push options or the browser). If a draft MR → `devel` exists, do not open a new one: "Mark as ready", check title/description, then:
   - MR branch → `devel`, "Delete source branch" **unticked**. Merge. Wait for a green `devel` pipeline.
   - **`direct` projects:** right after, MR branch → `main` with "Delete source branch" **ticked**. Merge. Wait for the whole `main` pipeline.
   - **`two-stage` projects:** (1) at release only `devel` → green pipeline → QA; the branch stays. (2) When the issue comes back "Ready to Deploy" assigned to me: merge `origin/main`, push, MR → `main` (delete branch ticked), Merge, wait for the first stages, then run the **manual deploy job** (and nothing else), wait for green. Only then "Resolved" + assign the person from the parent issue.
   - **Conflict on MR → `devel`:** **never merge `devel` into the issue branch** - `devel` carries other people's untested code that would then leak to `main`. Instead: create `devel-merge/<branch>` from the issue branch, merge `origin/devel` there, resolve, MR the copy → `devel` (delete branch ticked), merge, green pipeline. The issue branch stays clean (`release.develVia` in state).
   - Before every Merge verify the target branch and the delete-branch checkbox. After opening an MR wait a few seconds and reload - never click auto-merge.
   - Commits: one sentence in the style of `git log`, no co-authors, no body, only what changed in the app. MR title = exactly the branch name, empty description, assigned to me.
   - Red pipeline or an unsolvable conflict → stop and ask the user.
4. Add the issue to `releaseQueue`: `{ id, estimate, logged, entries: [] }`, where `logged` = the tracker's current spent time (the user may have logged part of it already). FIFO.

## Time log

- Time is logged per the **accepted estimate**, on working days (Mon-Fri, without public holidays), activity and comment per team convention.
- Never ahead of the clock: today's total may not exceed `min(workday.hours, hours since workday.start)` including the user's own entries (read the tracker's time entries for today), rounded down to 0.5 h.
- **Queue:** finished issues (review resolved, released - release never waits for hours) go to `releaseQueue` in order of completion; only the first one gets hours until its whole estimate is logged.
- `rest = estimate - spent time read from the tracker right before the entry` (≤ 0 → log nothing).
- **Fits** (`rest ≤ free now`) → one entry dated today and straight to QA (if the backend condition holds).
- **Does not fit** → no fragments during the day; at `schedule.timeLogAt` fill the day up to `workday.hours` and leave the rest for the next working day.
- **Done but waiting** (pushed after review, waits only for answers or the backend) → at `timeLogAt` log `estimate - reserve` (`reserve = max(0.5, 15% of the estimate rounded up to 0.5)`); the reserve is logged at release. Save `issues.<nr>.partialLogged`.
- After every entry update `issues.<nr>.spent`.
- **Day marker:** after the afternoon time log set `hoursFilledFor: "YYYY-MM-DD"`. The evening run (`evening-time-log.sh`) only does today's entries when the marker is missing.
- Never ask the user how to split hours - the rules above decide. Report what was logged, what is left, and when QA is expected.
- Log time in the issue edit form (time + activity), submit with a real mouse click and verify the success flash and the entry in the history. **Never write comments in tracker issues.**

## Handing over to QA

Only when `logged == estimate`, the backend condition holds and the pipelines are green: set the Branch field, status → "Ready for QA", assign the project's `tester` (unless a comment names another tester) - all in one form submission. Remove from `releaseQueue`.
