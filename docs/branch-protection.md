# Branch and Tag Protection

## Recommended settings for `main`

1. **Require a pull request before merging** (1 approval minimum)
2. **Require status checks to pass**: `CI Status`
3. **Dismiss stale pull request approvals when new commits are pushed**
4. **Do not allow bypassing the above settings**

## Tag protection

Create tag protection rules for:
- `v*` (workspace-wide releases)
- `*/v*` (per-package releases)

Settings → Rules → Add rule → Tag pattern.

## Signed commits/tags (recommended)

Enable signed commits:
```bash
git config --global gpg.format ssh
git config --global user.signingkey ~/.ssh/id_ed25519.pub
git config --global commit.gpgsign true
git config --global tag.gpgsign true
```
