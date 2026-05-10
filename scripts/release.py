#!/usr/bin/env python3
"""
Release helper script for ai-context-manager-mcp

Usage:
  python scripts/release.py --version 0.2.0 --message "Release version 0.2.0 - Add new features"
  python scripts/release.py --version 0.2.0  # Uses auto-generated message

The script will:
1. Validate the version format
2. Update pyproject.toml with the new version
3. Commit the change
4. Create and push a git tag
5. Display next steps
"""

import argparse
import re
import subprocess
from pathlib import Path


def validate_version(version: str) -> bool:
    """Validate semantic version format."""
    pattern = r'^\d+\.\d+\.\d+$'
    return bool(re.match(pattern, version))


def read_pyproject() -> tuple[Path, str]:
    """Read pyproject.toml and return path and content."""
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    content = pyproject_path.read_text(encoding="utf-8")
    return pyproject_path, content


def update_version_in_pyproject(content: str, new_version: str) -> str:
    """Update version in pyproject.toml content."""
    pattern = r'version = "[^"]+"'
    replacement = f'version = "{new_version}"'
    return re.sub(pattern, replacement, content, count=1)


def run_command(cmd: list[str], check: bool = True) -> str:
    """Run a shell command and return output."""
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, check=check)
    if result.stdout:
        print(f"    {result.stdout.strip()}")
    if result.returncode != 0 and result.stderr:
        print(f"    ERROR: {result.stderr.strip()}")
    return result.stdout


def main():
    parser = argparse.ArgumentParser(
        description="Release helper for ai-context-manager-mcp",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --version 0.2.0
  %(prog)s --version 0.2.0 --message "Release with new features"
        """,
    )
    parser.add_argument("--version", required=True, help="New version (e.g., 0.2.0)")
    parser.add_argument(
        "--message",
        default=None,
        help="Release message (default: auto-generated from version)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )

    args = parser.parse_args()

    # Validate version
    if not validate_version(args.version):
        print(f"❌ Invalid version format: {args.version}")
        print("   Use semantic versioning: X.Y.Z (e.g., 0.2.0)")
        return 1

    version = args.version
    tag = f"v{version}"
    message = args.message or f"Release version {version}"

    print(f"\n🚀 Releasing ai-context-manager-mcp v{version}")
    print("=" * 60)

    # Read pyproject.toml
    pyproject_path, pyproject_content = read_pyproject()

    # Update version
    updated_content = update_version_in_pyproject(pyproject_content, version)
    if updated_content == pyproject_content:
        print(f"❌ Could not find version line in {pyproject_path}")
        return 1

    if args.dry_run:
        print(f"\n📋 DRY RUN - What would happen:\n")
        print(f"1. Update {pyproject_path.relative_to(pyproject_path.parent.parent)}")
        print(f"   version = \"{version}\"")
        print(f"\n2. Commit: 'chore: bump version to {version}'")
        print(f"\n3. Tag: {tag}")
        print(f"   Message: {message}")
        print(f"\n4. Push to origin")
        print(f"\n✨ To proceed, run without --dry-run")
        return 0

    # Write updated pyproject.toml
    print(f"\n1️⃣  Updating {pyproject_path.name}...")
    pyproject_path.write_text(updated_content, encoding="utf-8")
    print(f"   ✓ Version updated to {version}")

    # Git add and commit
    print(f"\n2️⃣  Committing version bump...")
    run_command(["git", "add", str(pyproject_path)])
    run_command(["git", "commit", "-m", f"chore: bump version to {version}"])
    print(f"   ✓ Committed")

    # Create and push tag
    print(f"\n3️⃣  Creating git tag...")
    run_command(["git", "tag", "-a", tag, "-m", message])
    print(f"   ✓ Tag created: {tag}")

    print(f"\n4️⃣  Pushing to origin...")
    run_command(["git", "push", "origin", "main"])
    run_command(["git", "push", "origin", tag])
    print(f"   ✓ Pushed to origin")

    print(f"\n{'=' * 60}")
    print(f"✅ Release {version} complete!\n")
    print(f"📦 Watch the PyPI publishing workflow:")
    print(f"   https://github.com/dannybombastic/mcp-standard-ai/actions")
    print(f"\n🔍 View on PyPI (after workflow completes):")
    print(f"   https://pypi.org/project/ai-context-manager-mcp/{version}/\n")

    return 0


if __name__ == "__main__":
    exit(main())
