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
| `test_navigation.py` | 5 | Static hierarchy, breadcrumb, localization markup, and responsive CSS contract |
| `test_manifest_schema.py` | 5 | Specialized manifest and HADA Base compatibility metadata |
| `test_record_why.py` | 10 | Append-only, owner-stated WHY lifecycle |
| `test_import_conversation.py` | 5 | Opt-in, copy-only conversation archive imports |
| `test_media_library.py` | 16 | Media catalog, recursive sets, static viewer markup, and image-saving deterrence |
| `test_media_viewer_browser.py` | 1 | Real-browser fit/actual sizing, image-saving deterrence, viewer interaction, and no-JavaScript fallback |

The suite includes the framework, translation, upgrade, PWA Timer, asset,
gallery, safe HTML Master, navigation, release snapshot, Site Contract, and display policy
regressions. Run every `test_*.py` module for the current total.

`test_site_link_policy.py` verifies root-relative URLs and treats an apex host
and its `www` alias as one site, and checks canonical plus `hreflang` metadata
against the configured canonical host. `test_external_javascript_policy.py` verifies
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
