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

The goal is to avoid merge conflicts. They come from long-lived branches and from several people editing the same files.

1. **Use one branch per task and keep it short.** Branch from fresh `main` (`git pull --rebase` first), merge back as soon as it works (aim for under an hour), then delete the branch. No PR review is needed unless you touch someone else's area. Never force-push `main`.
2. **Stay in your own directory.** Only edit files under the area you own (see below). If you need a change in someone else's area, ask their human instead of making it yourself.
3. **Change shared files in small, separate commits.** For dependency manifests, the router or entry point, shared types or config: make the minimal edit in its own commit and push it right away. Don't bundle it with feature work.
4. **Agree on the interface first.** Write API shapes and data types in the Contracts section below before building against them. If a contract needs to change, update this file in the same commit.
5. **Give each agent its own worktree.** If one person runs several agents, put each in its own git worktree (`git worktree add ../otium-<task> -b <task>`). Never run two agents in the same folder.
6. **Commit small and often, with clear messages.** Each commit becomes an Entire checkpoint. Write one line saying what changed and why.
7. **Resolve conflicts using intent.** Run `entire why <file>:<line>` on both sides to see what each change was for, then keep both behaviours. Ask a human if the two can't both be kept.
8. **Ask a human before broad refactors**, renaming shared files, or reformatting the whole repo.
9. **Don't add a dependency** if a few lines of code would do. Never commit secrets; put them in `.env`, which must be gitignored.

## Kickoff (when the theme drops)

One person's agent builds the skeleton first: folder layout, dependency manifest, entry point, shared types, and the areas and contracts below. It pushes that before anyone else starts building.

## Areas / owners

_TBD, for example: `frontend/` → Ana, `api/` → Ben._

## Contracts

_TBD: API endpoints and shared data shapes._
