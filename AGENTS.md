# LabLoop repository instructions

- Read `docs/mvp-spec.md`, `docs/contracts.md`, and the assigned ticket fully.
- Edit only files listed under the ticket's **Owned files** section. If a required
  change falls outside that list, document it in the handoff instead of editing it.
- Treat `src/labloop/contracts.py`, `docs/contracts.md`, and `pyproject.toml` as
  frozen integration contracts.
- Use Python's standard library unless the frozen `pyproject.toml` already contains
  the dependency. Do not add dependencies in ticket branches.
- Keep raw observations append-only. Corrections create new events that reference
  the superseded event; they never overwrite scientific records.
- Validate all external data: VoiceOS tool arguments, protocol JSON, Slack responses,
  environment variables, and dashboard query parameters.
- The MVP may clarify an approved protocol, but must not invent protocol changes,
  diagnose results, or autonomously buy laboratory materials.
- Never commit secrets, tokens, recordings, generated databases, or researcher data.
- Add one focused `unittest` file for non-trivial behavior and run the ticket's
  verification commands before handoff.
- Preserve unrelated work and keep the diff within the assigned ticket boundary.
