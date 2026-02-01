#!/bin/bash

# Giscus Configuration Fetcher
# Uses GitHub CLI to automatically retrieve repo-id and category-id

set -e

echo "🔍 Fetching Giscus configuration..."

# Get current repo (assumes you're in a git repo)
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
echo "📦 Repository: $REPO"

# Fetch repo ID
REPO_ID=$(gh api graphql -f query='
  query($owner: String!, $name: String!) {
    repository(owner: $owner, name: $name) {
      id
    }
  }
' -f owner="${REPO%/*}" -f name="${REPO#*/}" --jq '.data.repository.id')

echo "🆔 Repo ID: $REPO_ID"

# Fetch discussion categories
echo "📂 Available discussion categories:"
CATEGORIES=$(gh api graphql -f query='
  query($owner: String!, $name: String!) {
    repository(owner: $owner, name: $name) {
      discussionCategories(first: 10) {
        nodes {
          id
          name
        }
      }
    }
  }
' -f owner="${REPO%/*}" -f name="${REPO#*/}")

echo "$CATEGORIES" | jq -r '.data.repository.discussionCategories.nodes[] | "\(.name): \(.id)"'

# Prompt user to select category
echo ""
echo "📝 Enter the category name for Giscus (e.g., General, Announcements):"
read CATEGORY_NAME

CATEGORY_ID=$(echo "$CATEGORIES" | jq -r --arg name "$CATEGORY_NAME" '.data.repository.discussionCategories.nodes[] | select(.name == $name) | .id')

if [ -z "$CATEGORY_ID" ]; then
  echo "❌ Category not found. Please check the name and try again."
  exit 1
fi

echo ""
echo "✅ Giscus configuration ready!"
echo ""
echo "Add this to your _quarto.yml:"
echo ""
echo "comments:"
echo "  giscus:"
echo "    repo: $REPO"
echo "    repo-id: \"$REPO_ID\""
echo "    category: \"$CATEGORY_NAME\""
echo "    category-id: \"$CATEGORY_ID\""
echo "    mapping: \"pathname\""
echo "    reactions-enabled: true"
echo "    loading: lazy"
echo "    input-position: \"bottom\""
echo "    theme: \"preferred_color_scheme\""
