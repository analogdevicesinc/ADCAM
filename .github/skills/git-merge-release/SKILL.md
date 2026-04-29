---
name: git-merge-release
description: 'Merge release branches into main for libaditof and ADCAM repositories. Use when: updating main with release branch changes, creating PR branches for release merges, rebasing release branches, handling git branch operations for releases (rel-*.*.*, dev-*.*.*), syncing development with release branches.'
user-invocable: true
---

# Git Release Branch Merge

Automate the process of merging release branches (e.g., `rel-7.0.0-a.1`) into the main branch for the ADCAM Camera Kit project. This skill handles both the main ADCAM repository and the libaditof submodule.

## When to Use

- Update main branch with changes from a release branch
- Create a PR branch for merging release changes
- Rebase a release branch onto main
- Sync development branches with release branches
- Handle merge conflicts during release integration

## Key Concepts

### Repository Structure
- **ADCAM (main repo)**: `/media/analog/.../Workspace/ADCAM/`
- **libaditof (submodule)**: `/media/analog/.../Workspace/ADCAM/libaditof/`

Most development work happens in the libaditof submodule.

### Branch Naming Conventions
- **Release branches**: `rel-X.Y.Z-a.N` (e.g., `rel-7.0.0-a.1`, `rel-6.2.0-a.1`)
- **Development branches**: `dev-X.Y.Z-a-N` (e.g., `dev-7.0.0-a-1`)
- **Main branch**: `main`

## Procedures

### 1. Update Main with Release Branch Changes

**Goal**: Merge release branch commits into main via a PR branch.

**Steps**:

1. **Determine target repository**
   - Ask user which repository: main ADCAM or libaditof submodule
   - Default to libaditof if context suggests SDK/driver work

2. **Clean local state**
   ```bash
   cd <repository-path>
   git fetch --all
   git checkout main
   git reset --hard origin/main
   git clean -fd
   ```

3. **Reset release branch to remote state**
   ```bash
   git checkout main
   git branch -D <release-branch>
   git checkout -b <release-branch> origin/<release-branch>
   git checkout main
   ```

4. **Check for new commits**
   ```bash
   git log main..<release-branch> --oneline
   ```
   - If no commits, inform user that main is already up to date
   - If commits exist, proceed to merge

5. **Create PR branch and merge**
   ```bash
   git checkout -b merge-<release-branch>-to-main-pr
   git merge <release-branch> --no-ff -m "Merge <release-branch> into main"
   ```

6. **Push PR branch**
   ```bash
   git push -u origin merge-<release-branch>-to-main-pr
   ```

7. **Clean up local main**
   ```bash
   git checkout main
   git reset --hard origin/main
   ```

8. **Report results**
   - Show files changed
   - Show commit summary
   - Provide GitHub PR creation URL
   - Confirm local main is clean

### 2. Rebase Release Branch onto Main

**Goal**: Rebase a release branch to include latest main changes.

**Steps**:

1. **Clean and prepare**
   ```bash
   cd <repository-path>
   git fetch --all
   git checkout <release-branch>
   git reset --hard origin/<release-branch>
   ```

2. **Perform rebase**
   ```bash
   git rebase main
   ```

3. **Handle conflicts** (if any)
   - Report conflict files
   - Provide guidance on resolution
   - After user resolves: `git rebase --continue`
   - If user wants to abort: `git rebase --abort`

4. **Verify result**
   ```bash
   git log --oneline --graph -10
   git status
   ```

5. **Note force push requirement**
   - Inform user: local branch is ahead of remote
   - Suggest: `git push --force-with-lease origin <release-branch>`
   - Do NOT automatically force push without confirmation

### 3. Quick Sync (Clean and Pull)

**Goal**: Reset repository to clean remote state.

**Steps**:

1. **Fetch all remotes**
   ```bash
   cd <repository-path>
   git fetch --all
   ```

2. **Reset current branch**
   ```bash
   git reset --hard origin/$(git branch --show-current)
   git clean -fd
   ```

3. **Reset other key branches**
   ```bash
   git checkout main
   git reset --hard origin/main
   
   # If release branch exists
   git branch -D <release-branch>
   git checkout -b <release-branch> origin/<release-branch>
   git checkout main
   ```

## Safety Checks

Before performing any operation:

1. **Check for uncommitted changes**
   - Run `git status` first
   - If changes exist, ask user:
     - Commit changes?
     - Stash changes?
     - Discard changes?
     - Abort operation?

2. **Verify branch exists**
   - Check both local and remote branches: `git branch -a`
   - If branch doesn't exist, report and suggest alternatives

3. **Confirm destructive operations**
   - Force pushes
   - Hard resets
   - Branch deletions
   - Always inform user before executing

4. **Submodule awareness**
   - If in main ADCAM repo, check if operation should apply to libaditof submodule
   - Submodule commits create "dirty" state in parent repo

## Common Issues

### Issue: Branch doesn't exist
**Symptom**: `git branch -a | grep <branch-name>` returns nothing
**Solution**: 
- Run `git fetch --all` to update remote tracking
- List all branches to show available options
- Suggest similar branch names

### Issue: Merge conflicts
**Symptom**: `git merge` stops with CONFLICT messages
**Solution**:
- List conflict files: `git diff --name-only --diff-filter=U`
- Provide conflict resolution guidance
- Show conflict markers in files
- Suggest tools: `git mergetool`, VS Code diff view

### Issue: Detached HEAD in submodule
**Symptom**: Submodule shows "new commits" in parent repo
**Solution**:
- This is normal after submodule branch changes
- To update parent: `git add libaditof && git commit -m "Update libaditof"`
- Or ignore if not ready to commit submodule state

### Issue: Already up-to-date
**Symptom**: `git merge` says "Already up to date"
**Solution**:
- Confirm with `git log main..<release-branch>`
- If truly up-to-date, inform user no action needed
- May indicate release was already merged previously

## Examples

### Example 1: Merge rel-7.0.0-a.1 into main (libaditof)

```bash
cd /media/analog/.../ADCAM/libaditof
git fetch --all
git checkout main
git reset --hard origin/main

# Check for new commits
git log main..rel-7.0.0-a.1 --oneline
# Output: 62a7b39c fix(sdk): sync runtime config with buffer allocation arrays

# Create PR branch
git checkout -b merge-rel-7.0.0-a.1-to-main-pr
git merge rel-7.0.0-a.1 --no-ff -m "Merge rel-7.0.0-a.1 into main"
# Auto-merging files...

# Push PR branch
git push -u origin merge-rel-7.0.0-a.1-to-main-pr
# PR URL: https://github.com/analogdevicesinc/libaditof/pull/new/merge-rel-7.0.0-a.1-to-main-pr

# Clean local main
git checkout main
git reset --hard origin/main
```

### Example 2: Rebase release onto main

```bash
cd /media/analog/.../ADCAM/libaditof
git fetch --all
git checkout rel-7.0.0-a.1
git reset --hard origin/rel-7.0.0-a.1
git rebase main
# Successfully rebased and updated refs/heads/rel-7.0.0-a.1

# Note: Branch is now ahead of origin/rel-7.0.0-a.1
# To push: git push --force-with-lease origin rel-7.0.0-a.1
```

## Best Practices

1. **Always create PR branches** for merging into main - never directly commit to main
2. **Use --no-ff** for merge commits to preserve branch history
3. **Use --force-with-lease** instead of --force for safer force pushes
4. **Reset local main** after creating PR branch to avoid accidental pushes
5. **Fetch before operations** to ensure remote tracking is current
6. **Check log differences** before merging to understand what's being integrated
7. **Keep PR branch names descriptive**: `merge-<source>-to-<target>-pr`

## Tool Integration

This skill uses the following git commands:
- `git fetch --all` - Update all remote tracking branches
- `git reset --hard` - Discard local changes and match target
- `git clean -fd` - Remove untracked files and directories
- `git merge --no-ff` - Create explicit merge commit
- `git rebase` - Replay commits on top of target branch
- `git log --oneline --graph` - Visualize commit history
- `git push -u origin` - Push branch with upstream tracking

## References

- [Git Branching Workflow](https://git-scm.com/book/en/v2/Git-Branching-Branching-Workflows)
- [Git Merge vs Rebase](https://git-scm.com/book/en/v2/Git-Branching-Rebasing)
- [Force Push Best Practices](https://git-scm.com/docs/git-push#Documentation/git-push.txt---force-with-leaseltrefnamegt)
