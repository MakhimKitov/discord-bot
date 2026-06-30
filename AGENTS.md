# Agent roles (Discord bot repo)

This product repo is maintained by an autonomous AI developer (a separate platform in its own repo) under the rules in
`CLAUDE.md`. This file describes the roles that
operate *on this repo*. Work flows through GitHub issues and pull requests.

## Autonomous developer — implementer

The dev agent that maintains the bot. Runs in a container on a clone of this repo.

Allowed:
- edit bot code, add tests
- run checks and the product toolchain in its container
- open pull requests
- comment on issues / PRs (status, blocked reasons)

Forbidden:
- merging a PR or deploying to production (a human merges; CI deploys)
- editing secrets or `private/`
- destructive data operations
- changing this policy

## Code review — two independent stages

1. **Codex — pre-PR (in-container).** The dev runs Codex on its own diff before opening
   the PR and addresses the findings. Checks correctness, missing tests/edge cases,
   security risks, and whether the issue is actually solved.
2. **GitHub Copilot — post-PR (on the PR).** Configured as an automatic reviewer on this
   repo; reviews the opened PR and posts findings for the human.

Both are read-only checks by a model *different from the implementer*. The human owner
gives the final review and merge.

## Codex — spec reviewer

On every PRD and architecture / stack spec before it becomes authoritative:
- find missing or ambiguous functional requirements
- find missing or unmeasurable acceptance criteria
- surface contradictions, hidden assumptions, and unstated dependencies
- identify abuse / security vectors not addressed (esp. for user-supplied input)
- challenge scope decisions and load-bearing "out of scope" items
- sanity-check scale, latency, and reliability targets against the architecture they imply
- name decisions deferred without an owner

A spec is not authoritative until this review has run and findings are addressed in the
spec or explicitly accepted by the human owner with rationale. Codex does not modify code
or specs unless explicitly asked.

## Human owner

Owns product decisions, approves issues (`ready`) and specs, reviews and **merges** PRs —
the only actor allowed to cause a production deploy.
