#!/usr/bin/env bash

# This script automates the final steps of a release:
# 1. Creates a Git tag based on the latest version in CHANGELOG.md.
# 2. Pushes the current branch and all tags to the 'origin' remote.

set -e # Exit immediately if a command exits with a non-zero status.

# Ensure we are at the project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

# --- Step 1: Create the release tag from CHANGELOG.md ---
echo ">>> Finding latest version in CHANGELOG.md to create tag..."

CHANGELOG_FILE="CHANGELOG.md"

if [ ! -f "$CHANGELOG_FILE" ]; then
    echo "Error: $CHANGELOG_FILE not found."
    exit 1
fi

# Extract the latest version tag (e.g., v1.2.3) from the changelog.
# It looks for the first line starting with "## v" and extracts the version string.
LATEST_VERSION=$(grep -m 1 '^## v[0-9]\+\.[0-9]\+\.[0-9]\+' "$CHANGELOG_FILE" | sed -E 's/## (v[0-9]+\.[0-9]+\.[0-9]+).*/\1/')

if [ -z "$LATEST_VERSION" ]; then
    echo "Error: Could not find a version string like '## vX.Y.Z' in $CHANGELOG_FILE."
    exit 1
fi

echo "Found latest version in changelog: $LATEST_VERSION"

# Check if the tag already exists
if git rev-parse "$LATEST_VERSION" >/dev/null 2>&1; then
    echo "Error: Tag '$LATEST_VERSION' already exists."
    echo "A release for this version may have already been attempted."
    echo "To re-attempt, delete the tag locally and remotely:"
    echo "  git tag -d $LATEST_VERSION"
    echo "  git push origin --delete $LATEST_VERSION"
    echo "Then, run this script again."
    echo "Alternatively, update CHANGELOG.md with a new version and commit."
    exit 1
fi

echo "Creating new Git tag: $LATEST_VERSION"
git tag "$LATEST_VERSION"
echo "Successfully created tag '$LATEST_VERSION'."

# --- Step 2: Push commits and tags ---
echo ""
echo ">>> Pushing changes and tags to upstream..."
git push origin main --tags

echo ""
echo "✅ Successfully pushed to origin."
echo "The 'Create and Publish Release' workflow should now be triggered on GitHub."

exit 0