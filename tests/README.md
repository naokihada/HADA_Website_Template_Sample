# Tests

Automated test definitions for framework tools.

Record results in `AI/reports/TEST.md`.

## Test files

| File | Tests | Scope |
|---|---|---|
| `test_validate_framework.py` | 15 | Framework validator |
| `test_translation.py` | 13 | Translation pipeline and build |
| `test_upgrade_from_release.py` | 20 | Template Upgrade engine (offline-safe) |
| `test_pwa_timer.py` | 5 | PWA Timer install contract and manifest icons |
| `test_template_base.py` | 8 | Adoption metadata and mismatch safety |
| `test_file_transaction.py` | 3 | Hash-bound backup and conflict safety |
| `test_legacy_workspace.py` | 2 | Retired workspace migration safety |
| `test_release_prepare.py` | 4 | Allowlisted sibling, internal evidence, and release fixture boundaries |
| `test_navigation.py` | 5 | Static hierarchy, breadcrumb, localization markup, and responsive CSS contract |

The suite includes the framework, translation, upgrade, PWA Timer, asset,
gallery, safe HTML Master, navigation, release snapshot, Site Contract, and display policy
regressions. Run every `test_*.py` module for the current total.

`test_site_link_policy.py` verifies root-relative URLs and treats an apex host
and its `www` alias as one site. `test_external_javascript_policy.py` verifies
the default prohibition and the explicit optional client-only declaration path.

The optional browser contract is provided by `tests/test_browser_ui.py`. It uses
`tests/requirements-ui.txt`, starts a local static server rooted at the configured
`paths.local_test_root`, blocks external requests by default, and discovers routes
from the publication tree and Page Registry. A missing Playwright runtime or
browser is `REVIEW_REQUIRED` for release verification.

## Run

From repository root:

```text
pip install -r tools/core/requirements.txt
pip install -r tests/requirements-ui.txt
python tests/test_validate_framework.py
python tests/test_translation.py
python tests/test_upgrade_from_release.py
python tests/test_pwa_timer.py
python tests/test_browser_ui.py
```

Install the Chromium runtime once when the browser contract is enabled:

```text
python -m playwright install chromium
```

Upgrade tests are **offline-safe** by default (mocked GitHub API). Live GitHub Release
integration validation is a separate Maintainer step after Public Release (see `docs/RELEASE.md`).

## Manual PWA install checks

Use an HTTPS deployment and confirm:

1. A supported browser fires `beforeinstallprompt`; **Install this timer** appears and opens the browser install prompt.
2. After installation, `appinstalled` or standalone display hides the button.
3. On iPhone/iPad, the fallback says Safari Share → Add to Home Screen; other browsers receive a browser-menu hint.
4. Install the app, go offline, reopen it, and confirm the timer page and countdown still work.

## Fixtures

`tests/fixtures/` — shared fixtures for validator and translation tests.
