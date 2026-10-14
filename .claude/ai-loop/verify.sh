#!/usr/bin/env bash
# ai-loop の検証コマンド（ai_loop_init.py が生成）
# カレントディレクトリのリポジトリを検査する（$0 を基準にしない．commander の worktree での検証のため）
cd "$(git rev-parse --show-toplevel)" || { echo "verify: not a git repository, 1 failed"; echo "VERIFY FAILED"; exit 1; }
if {
  python3 -m pytest
}; then
  echo "verify: test command exit 0, 0 failed"
  echo "VERIFY PASSED"; exit 0
else
  rc=$?
  echo "verify: test command exit $rc, 1 failed"
  echo "VERIFY FAILED"; exit 1
fi
