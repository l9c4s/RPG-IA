#!/usr/bin/env bash
# Recursion guard — prevents infinite loop when this script calls claude CLI
[ -n "$CLAUDE_TEST_GEN" ] && exit 0
export CLAUDE_TEST_GEN=1

# Find files changed since last commit (staged + unstaged + untracked src files)
CHANGED=$(git diff --name-only HEAD 2>/dev/null; git diff --name-only 2>/dev/null; git ls-files --others --exclude-standard 2>/dev/null)

if [ -z "$CHANGED" ]; then
  exit 0
fi

# Filter out infrastructure files — only process source code
FILTERED=$(echo "$CHANGED" | grep -v -E \
  '(Dockerfile|requirements\.txt|nginx\.conf|\.env|\.sql|docker-compose|\.md|scripts/|\.claude/|package-lock\.json|debug_entrypoint\.sh)' \
  | grep -E '\.(py|ts|tsx)$' \
  | sort -u)

if [ -z "$FILTERED" ]; then
  exit 0
fi

FILE_LIST=$(echo "$FILTERED" | tr '\n' ' ')

claude --dangerously-skip-permissions -p "You are a test generation specialist for the RPG-IA project (FastAPI backend + React TypeScript frontend).

The following source files were recently modified:
$FILE_LIST

For each file listed, generate tests:

## Python services (services/*/)

**Unit tests** → \`services/{service}/tests/test_{module}.py\`
- Use pytest + pytest-asyncio
- Mock external dependencies (httpx calls, DB) with unittest.mock
- Test each function/endpoint in isolation
- Cover: happy path, edge cases, error conditions

**Integration tests** → \`services/{service}/tests/test_{module}_integration.py\`
- Use FastAPI TestClient (httpx)
- Test full request/response cycle
- Use a real or in-memory DB when feasible
- Test auth, validation errors, 404s

## Frontend (frontend/src/)

**Unit tests** → co-located \`{filename}.test.tsx\` or \`frontend/src/__tests__/\`
- Use Vitest + React Testing Library
- Test component rendering, user interactions, state changes
- Mock API calls with vi.mock('../api/client')

## Rules
- Only generate tests for the files listed above
- If a test file already exists for a changed file, update it to cover new behavior
- Add a \`conftest.py\` in each service's tests/ dir if it doesn't exist
- Keep tests focused and fast — no real API calls, no real DB unless integration test
- Write tests in the same language as the source (Python for .py, TypeScript for .ts/.tsx)" 2>/dev/null

exit 0
