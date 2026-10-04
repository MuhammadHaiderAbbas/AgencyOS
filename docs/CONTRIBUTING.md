# Contributing

1. `cd backend && python -m unittest discover -s tests -t tests` must pass.
2. For UI changes: `cd frontend && npm run build && npm run typecheck`, then run `tests/e2e_browser.py`.
3. Every UI state must map to real backend state. No placeholder activity, no dead buttons. If an integration is missing, show "not configured".
4. New agents follow the contract in docs/AGENTS.md and get the minimum permissions they need.
5. Never commit secrets. `data/` is git-ignored.
