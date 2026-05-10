"""
PyPI Publishing Instructions for ai-context-manager-mcp
========================================================

This project is configured to automatically publish to PyPI when you push a version tag.

## Prerequisites

1. **PyPI Account**: Create an account at https://pypi.org if you don't have one
2. **Trusted Publisher Setup** (Recommended - More Secure):
   - Go to https://pypi.org/manage/account/publishing/
   - Click "Add a new pending publisher"
   - Repository name: `mcp-standard-ai` (or your fork)
   - Repository owner: `dannybombastic` (or your GitHub username)
   - Workflow name: `publish-to-pypi.yml`
   - Environment name: Leave blank (we use OIDC without explicit environment)
   - Click "Add"

3. **Alternative: API Token** (Legacy - Less Secure):
   - Create a token at https://pypi.org/manage/account/tokens/
   - Go to your GitHub repo Settings → Secrets and variables → Actions
   - Create a new secret named `PYPI_API_TOKEN`
   - Paste your token as the value

## Publishing a Release

### Step 1: Update version in pyproject.toml
```bash
# Current version
version = "0.1.0"

# Update to
version = "0.2.0"
```

### Step 2: Create a git tag
```bash
git tag -a v0.2.0 -m "Release version 0.2.0"
git push origin v0.2.0
```

### Step 3: Watch the workflow
- Go to your repository → Actions tab
- Click on "Publish to PyPI" workflow run
- Monitor the build and publish steps

### Step 4: Verify on PyPI
```bash
pip install --upgrade ai-context-manager-mcp
# or visit https://pypi.org/project/ai-context-manager-mcp/
```

## Version Tagging Convention

Follow semantic versioning:
- **v0.1.0** - Initial release (major.minor.patch)
- **v0.1.1** - Bug fix
- **v0.2.0** - New feature
- **v1.0.0** - Breaking changes

Format: `v<MAJOR>.<MINOR>.<PATCH>`

## What Gets Published

The workflow builds and publishes:
- Source distribution (`.tar.gz`)
- Wheel distribution (`.whl`)
- Metadata and documentation

## Troubleshooting

### Build fails with "Package already exists"
- This can happen if you publish the same version twice
- Use a new version number and tag
- Or enable `skip-existing: true` in the workflow

### Publish fails with authentication error
- If using OIDC: Ensure the trusted publisher is configured
- If using API token: Verify the token in GitHub secrets

### Package not appearing on PyPI immediately
- PyPI can take 5-10 minutes to index new packages
- PyPI CDN caching can take longer for pip search results

## Example: Complete Release Workflow

```bash
# 1. Update version in pyproject.toml
sed -i 's/version = "0.1.0"/version = "0.2.0"/' pyproject.toml

# 2. Commit changes
git add pyproject.toml
git commit -m "chore: bump version to 0.2.0"

# 3. Create and push tag
git tag -a v0.2.0 -m "Release version 0.2.0 - Add sync agent feature"
git push origin main
git push origin v0.2.0

# 4. Monitor workflow on GitHub
# Actions → Publish to PyPI → (watch progress)

# 5. Install and test
pip install --upgrade ai-context-manager-mcp==0.2.0
ai-context-manager --version
```

## Notes

- Tags must follow pattern `v*.*.*` to trigger the workflow
- The workflow uses Python 3.11 (same as pyproject.toml requirement)
- OIDC is more secure than API tokens (no token storage needed)
- Workflow runs on Ubuntu latest for consistency

For more details, see:
- https://packaging.python.org/
- https://hatch.pypa.io/latest/
- https://docs.github.com/en/actions
"""
