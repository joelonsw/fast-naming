---
description: How to commit and push code changes
---

# Git Commit & Push AI Agent Workflow

This workflow explicitly defines how AI Agents should commit and push code for this project.

## Requirements
1. **Understand Git**: Be familiar with standard Git operations (`git add`, `git commit`, `git push`).
2. **Review Changes**: ALWAYS review the changes carefully using `git status` and `git diff` before blindly staging everything, unless instructed otherwise.
3. **Write Meaningful Commits**: Write clear, descriptive commit messages following the Conventional Commits format (e.g., `feat:`, `fix:`, `docs:`, `chore:`).
4. **No Force Pushing**: **NEVER** use `git push -f` or `--force`. If there are conflicts, pull the latest changes, resolve them, and then push.

## Step-by-Step Instructions

1. **Check Status**: Run `git status` to see what files were modified.
// turbo
2. **Stage Changes**: Run `git add <files>` to stage specific files, or `git add .` to stage all modifications.
// turbo
3. **Commit**: Run `git commit -m "<type>: <brief description>"` to commit the changes.
// turbo
4. **Push**: Run `git push` to upload the changes to the remote repository.

*Example command sequence:*
```bash
git add .
git commit -m "feat: update LLM models and refine naming prompt"
git push
```
