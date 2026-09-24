# Browser UI Contract

The Template provides an optional Playwright contract for development and
release-candidate verification. Playwright is never a published-site runtime.

## Configuration

`config/project.yaml` defines the test root and browser policy:

```yaml
paths:
  publication_root: site
  generated_root: build
  local_test_root: site

verification:
  browser:
    enabled: true
    route_source: auto
    block_external_requests: true
    viewports:
      - width: 1920
        height: 1080
      - width: 390
        height: 844
```

`local_test_root` must stay inside the repository. The browser runner starts a
temporary local HTTP server and does not inspect or modify production systems.

## UI profiles

Page Registry entries may declare:

- `shared-shell`: header, footer, display controls, and responsive contract.
- `standalone`: title, viewport, and navigation contract without shared controls.
- `pwa`: application-specific contract such as the Timer Demo.

Generated pages declare their profile with `data-ui-profile`. HTML Master pages
should declare it in the Page Registry. A route without a supported profile is
reported as `REVIEW_REQUIRED`; it is never silently omitted.

## Running the contract

```text
pip install -r tools/core/requirements.txt
pip install -r tests/requirements-ui.txt
python -m playwright install chromium
python tests/test_browser_ui.py
```

To test an isolated candidate instead of the configured publication root:

```text
python tools/core/browser_contract.py --root . --test-root build
```

The contract checks page loading, fatal console errors, profile landmarks,
desktop/mobile viewports, horizontal overflow, external-link safety,
background-image resolution, and Display State persistence after navigation.

External requests are blocked by default. A project may add project-owned tests,
but must not weaken the Template Core fallback or silently permit external
runtime dependencies.

## Ownership boundary

Template browser infrastructure belongs to `tools/core/`, the root
`tests/test_browser_ui.py` entry point, and `tests/requirements-ui.txt`. A
consuming project may keep semantic or visual extensions under
`tests/project/` and must classify them as project-owned in its local operating
documentation. Hada.Biz branding, copy, Play Mode effects,
background assignments, and business navigation are not Template Core.

## Promotion workflow

Release and Upgrade workflows should use an isolated candidate:

```text
python tools/core/build_site.py --root . --candidate-root build --mode build-safe
python tools/core/validate_framework.py --root .
python tests/test_browser_ui.py
python tools/core/promote_build.py --root . --candidate-root build --format both
python tools/core/promote_build.py --root . --candidate-root build --apply
```

The promotion command updates only Template-owned or generated paths. Project-owned
paths are preserved. Unknown or ambiguous changes produce `REVIEW_REQUIRED` and
cannot be applied automatically.
