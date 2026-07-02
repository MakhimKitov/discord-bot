# Copilot instructions — discord-bot

This repo is a small utility Discord bot maintained by an **autonomous AI developer**
through PRs; a human gives the final review and merge. You are the independent
post-PR check between them. Be specific, cite lines, prioritize real defects over
style. Flag scope creep even when the extra code is good.

## Repo shape

- `bot/commands/<module>.py` — pure logic functions + thin `@app_commands.command`
  wrappers + a `register(tree)`; wired via `register_all` in `bot/commands/__init__.py`.
- `tests/` — offline unit tests of the pure logic; no Discord connection, no network.
- Python 3.12, discord.py, slash commands only, default intents (no message content).
- The linked issue is the contract: it carries `FR-n` functional requirements,
  acceptance evidence per FR, and scope boundaries (including forbidden changes).

## Review checklist, in priority order

1. **Contract**: the PR maps to exactly one issue (`Closes #n`); the diff stays inside
   the issue's scope boundaries and touches nothing listed under "Forbidden changes".
2. **FR coverage**: every `FR-n` in the issue has matching implementation *and* matching
   evidence in the PR body; the evidence is real — tests exist and actually assert it.
3. **Correctness**: interaction handlers respond exactly once; user-facing failures
   reply ephemeral; pure logic validates bounds and empty input.
4. **Tests**: pure functions tested offline (seeded RNG where behavior is random);
   the registry test covers new commands; existing tests untouched unless the issue
   says otherwise.
5. **Security / containment**: no secrets, tokens, `.env*` values, or `private/`
   content anywhere in the diff; no new dependencies and no CI/workflow changes unless
   the issue explicitly allows them.
6. **Conventions**: conventional-commit PR title (`feat:`, `fix:`, …); PR template
   sections filled — Summary, Evidence (per FR), Release notes, Rollback.
