# Otium — hackathon repo

Several people, each with their own coding agent, work in this repo at once. **The hackathon theme is not known yet.** Until a human fills in the Project section below, don't scaffold an app, choose a stack, or add dependencies.

## Project

- **Theme:** TBD
- **Idea:** TBD
- **Stack:** TBD
- **Run:** TBD

## Entire (session tracking)

This repo uses [Entire](https://docs.entire.io). Git hooks attach each agent session to a commit as a **checkpoint** (stored in git refs, synced to `origin` on push). That lets everyone see why code exists and what other agents already tried.

- **Set this up once per clone:** `entire enable --agent <claude-code|codex|cursor|...>`. Git hooks are not cloned, so `entire status` shows "Enabled" even when nothing is being recorded. Check that `.git/hooks/post-commit` exists. If it doesn't, commits won't create checkpoints.
- For exact commands and flags, run `entire agent-help`; don't guess.
- **Before starting work**, see what others did: `entire checkpoint list`, `entire recap`, and `entire search "<topic>"`.
- **Before changing code you didn't write**, run `entire why <file>:<line>` or `entire checkpoint explain <sha>`.
- Don't commit `.entire/{tmp,metadata,logs}`; they are already gitignored. Don't edit `.claude/settings.json` hooks by hand.

## Coordination rules

1. **Work small and commit often.** Each commit becomes a checkpoint, so many small commits give teammates' agents more context than one big one.
2. **Pull before you start, and rebase before you push** (`git pull --rebase`). Never force-push `main`.
3. **Stay inside your area.** Once the theme is known, list the areas and their owners here. Ask a human before making broad refactors, renaming shared files, or reformatting the whole repo.
4. **Write useful commit messages:** what changed and why, in a single line.
5. **Keep shared decisions in this file.** When a human decides something that affects everyone (stack, folder layout, API contract), add it here in the same commit.
6. **Don't add a dependency** if a few lines of code would do. Never commit secrets; put them in `.env`, which must be gitignored.

## Areas / owners

_TBD once the theme is announced._
