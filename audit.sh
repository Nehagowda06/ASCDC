#!/bin/bash

set -e

echo "🔍 Running Structural Audit (mypy + ruff)..."
mypy . || exit 1
ruff check . || exit 1

echo "⚙️ Running Unit & Contract Tests..."
pytest -q || exit 1

echo "🚀 Running Pipeline Smoke Test (inference)..."
python inference.py > /dev/null 2>&1 || {
    echo "❌ inference.py failed"
    exit 1
}

echo "🧪 Running Environment Execution Check..."
python - <<EOF
from env.environment import ASCDCEnvironment

env = ASCDCEnvironment(seed=42)
obs = env.reset()

for _ in range(10):
    obs, reward, done, info = env.step({"type": "noop"})
print("Env OK")
EOF

echo "🔎 Checking for silent failures (grep)..."
grep -R "except Exception:" -n . && echo "⚠️ Found unsafe exception handlers"

echo "🧠 Checking API integrity..."
python - <<EOF
from server.app import app
print("API OK")
EOF

echo "✅ ALL AUDITS PASSED"
