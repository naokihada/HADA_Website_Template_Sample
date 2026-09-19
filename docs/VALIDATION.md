# Public Validation Documentation

Public validation and test runbook for `HADA_Website_Template` (v0.2.0).

This document is **not** a Master Implementation Specification. The complete master
specification exists in the development repository only (`HADA_Website_Template_Dev`) and
is not shipped with this public template.

**Runtime authority:** `tools/core/validate_framework.py` (core-validator v0.2) and the
test modules under `tests/`. This document explains how to run and interpret them.

---

## 1. Purpose

The core validator provides **deterministic, read-only pre-validation** of the repository
before task execution, commit, or release preparation.

It checks:

- Repository structure (STRUCT)
- Configuration (CFG)
- Environment definitions (ENV)
- Reference registry (REF)
- Plugin manifests when present (PLUGIN)
- Locale content layout (I18N)
- Security and publication safety (SEC)

It does **not**:

- Judge content, translation, or design quality
- Perform AI or semantic analysis
- Approve or reject production release
- Modify any file
- Require network access or external services
- Replace human approval for STAGING / PRODUCTION operations

---

## 2. Test execution

Install dependencies from the repository root:

```text
pip install -r tools/core/requirements.txt
```

Run the test suite:

```text
python tests/test_validate_framework.py
python tests/test_translation.py
python tests/test_upgrade_from_release.py
python tests/test_pwa_timer.py
python tests/test_template_base.py
python tests/test_file_transaction.py
python tests/test_legacy_workspace.py
```

Record actual results for all available tests. `TEMPLATE_BASE.md` is checked only when
present; an absent Base supports legacy detection. Build styled Sample output in an
isolated copy.

Tests use Python stdlib `unittest`. PyYAML and `markdown` are required for code under test.

---

## 3. Validator CLI

Script: `tools/core/validate_framework.py`

```text
python tools/core/validate_framework.py [--root PATH] [--format text|json|both] [--task-id ID] [--include-local] [--strict]
```

| Option | Default | Description |
|---|---|---|
| `--root` | `.` | Repository root (directory containing `AGENTS.md`) |
| `--format` | `both` | `text`, `json`, or `both` (human text, then `---JSON---`, then JSON) |
| `--task-id` | null | Optional correlation ID included in JSON output |
| `--include-local` | off | If set, emit SEC-006 INFO when `config/local.yaml` exists |
| `--strict` | off | Treat WARNING findings as ERROR (exit 1) |

**Requirements:** Python 3.10+; PyYAML `>=6.0`. If PyYAML is missing, exit code is `2`
with finding `VALIDATOR-DEP`.

---

## 4. Severity and exit codes

### Severity

| Severity | Meaning | Default exit impact |
|---|---|---|
| ERROR | Baseline contract violated | Fail |
| WARNING | Non-blocking issue or incomplete configuration | Pass (unless `--strict`) |
| INFO | Informational; no action required | Pass |

### Exit codes

| Exit code | Meaning |
|---|---|
| `0` | No ERROR (WARNING/INFO allowed unless `--strict`) |
| `1` | One or more ERROR, or WARNING with `--strict` |
| `2` | Validator internal failure (missing PyYAML, unreadable root, missing `AGENTS.md`, I/O error) |

### Overall `status` (JSON)

| status | Condition |
|---|---|
| `PASS` | Zero ERROR |
| `FAIL` | One or more ERROR |
| `ERROR` | Validator could not complete (maps to exit 2) |

With `--strict`, any WARNING causes `FAIL` and exit `1`.

---

## 5. Rule catalog

Rule IDs help interpret validator output. Findings are sorted by `(rule_id, file, field)`.

### STRUCT-* (repository structure)

| rule_id | Severity | Condition / purpose |
|---|---|---|
| STRUCT-001 | ERROR | `AGENTS.md` exists at repository root |
| STRUCT-002 | ERROR | `README.md` exists |
| STRUCT-003 | ERROR | `.gitignore` exists |
| STRUCT-004 | ERROR | `AI/` directory exists |
| STRUCT-005 | ERROR | `content/en/` exists |
| STRUCT-006 | ERROR | `content/jp/` exists |
| STRUCT-007 | ERROR | `site/` exists |
| STRUCT-008 | ERROR | `site/README.md` exists |
| STRUCT-009 | ERROR | `site/en/` exists |
| STRUCT-010 | ERROR | `site/jp/` exists |
| STRUCT-011 | ERROR | `site/assets/` exists |
| STRUCT-012 | ERROR | `references/registry/` exists |
| STRUCT-013 | ERROR | `references/cache/` exists |
| STRUCT-014 | ERROR | `references/reports/` exists |
| STRUCT-015 | ERROR | `environments/` exists |
| STRUCT-016 | ERROR | `tools/core/` exists |
| STRUCT-017 | ERROR | `tools/plugins/` exists |
| STRUCT-018 | ERROR | `tests/` exists |
| STRUCT-019 | ERROR | `docs/` exists |
| STRUCT-020 | ERROR | `config/` exists |
| STRUCT-023 | ERROR | `paths.publication_root` from `config/project.yaml` resolves to an existing directory |

### CFG-* (configuration)

| rule_id | Severity | Condition / purpose |
|---|---|---|
| CFG-001 | ERROR | `config/project.yaml` valid YAML |
| CFG-002 | ERROR | `project.id`, `name`, `version`, `mode` present |
| CFG-003 | ERROR | `project.mode` is NEW, RECOVERY, MIGRATION, or MAINTENANCE |
| CFG-004 | ERROR | `paths.publication_root`, `content_master`, `tools_core`, `tools_plugins` present |
| CFG-005 | ERROR | `locales.default` is listed in `locales.supported` |
| CFG-006 | ERROR | Each supported locale is a valid locale code such as `en`, `jp`, or `de` |
| CFG-007 | ERROR | `paths.publication_root` resolves to existing directory |
| CFG-008 | ERROR | `paths.content_master` resolves to existing directory |
| CFG-009 | ERROR | `config/site.example.yaml` valid YAML |
| CFG-010 | WARNING | `config/site.yaml` missing |
| CFG-011 | ERROR | If `config/site.yaml` present: valid YAML; `site.publication_root` matches project publication root |
| CFG-012 | ERROR | If present: `publication.deploy_target` equals project publication root, or `site` / `site/` |
| CFG-013 | ERROR | If present: each `publication.locales.*` path stays under publication root with no forbidden segments |
| CFG-014 | ERROR | If present: each `plugins.enabled[].state` is a valid plugin lifecycle state |
| CFG-015 | ERROR | If present: `rss.default_state` is FULL, PARTIAL, or NO_CONTENT |

### ENV-* (environments)

Applied to `environments/environments.example.yaml` and `environments/environments.yaml` if present.

| rule_id | Severity | Condition / purpose |
|---|---|---|
| ENV-001 | ERROR | File valid YAML |
| ENV-002 | ERROR | Top-level `environments` key exists |
| ENV-003 | ERROR | LOCAL, STAGING, PRODUCTION defined |
| ENV-004 | ERROR | Each environment has `description`, `approval_required`, `publication_root` |
| ENV-005 | ERROR | PRODUCTION.approval_required is true |
| ENV-006 | ERROR | STAGING.approval_required is true |
| ENV-007 | WARNING | LOCAL.approval_required should be false |
| ENV-008 | ERROR | `publication_root` inside repository; no forbidden path segments |
| ENV-009 | INFO | `web.hostname` is null |

### REF-* (references registry)

Applied to each `references/registry/*.yaml` file.

| rule_id | Severity | Condition / purpose |
|---|---|---|
| REF-001 | ERROR | File exists and parses as valid YAML |
| REF-002 | ERROR | Top-level `version` field present |
| REF-003 | ERROR | `references` key is a list |
| REF-004 | ERROR | Each entry has `id`, `type`, `description`, `readonly` |
| REF-005 | ERROR | Reference `id` values unique within file |
| REF-006 | ERROR | Reference `id` matches `^[a-z0-9][a-z0-9-]*$` |
| REF-007 | WARNING | Entry `path` matches private local path patterns |
| REF-008 | WARNING | Entry `url` contains embedded credentials |
| REF-009 | ERROR | If `adapter: wordpress-com`, then `type` must be `external_content_source` |

### PLUGIN-* (plugin manifests)

Applied per `tools/plugins/<plugin-id>/manifest.yaml` when present.

| rule_id | Severity | Condition / purpose |
|---|---|---|
| PLUGIN-001 | ERROR | Manifest valid YAML |
| PLUGIN-002 | ERROR | `plugin.id`, `version`, `status`, `spec_version` present |
| PLUGIN-003 | ERROR | `plugin.id` equals directory name |
| PLUGIN-004 | ERROR | `plugin.status` is valid lifecycle state |
| PLUGIN-005 | ERROR | `plugin.spec_version` is semver-like (MAJOR.MINOR or MAJOR.MINOR.PATCH) |
| PLUGIN-006 | WARNING | `dependencies` missing when status is ENABLED |
| PLUGIN-007 | ERROR | `ownership.maintainer` required when status is ENABLED or INSTALLED |
| PLUGIN-008 | WARNING | `changed_files` missing when status is INSTALLING or INSTALLED |
| PLUGIN-009 | INFO | `reversibility.uninstall_supported` is boolean |
| PLUGIN-010 | ERROR | `plugin.id` must not equal reserved name `core-validator` |

Zero plugin directories with manifests is expected in v0.1.0.

### I18N-* (internationalization)

| rule_id | Severity | Condition / purpose |
|---|---|---|
| I18N-001 | ERROR | `content/{locale}/` exists for each supported locale |
| I18N-002 | WARNING | Each `content/en/` file has same basename in `content/jp/` |
| I18N-003 | WARNING | Each `content/jp/` file has same basename in `content/en/` |
| I18N-004 | INFO | No content master files in either locale (ignores `.gitkeep`) |

Content master files are immediate children of locale directories only (no recursive scan).

The built-in master i18n pipeline also supports `content/pages/*_master.md` sources and
locale snapshots such as `*_JP.md`, `*_EN.md`, and `*_DE.md`. Fenced code is protected by
default; `i18n-comments` translates comments only.

### SEC-* (security / publication safety)

Pattern-based checks on committed YAML under `config/`, `environments/`, `references/registry/`.

| rule_id | Severity | Condition / purpose |
|---|---|---|
| SEC-001 | ERROR | Secret-like `password:` / `api_key:` assignments with non-placeholder values |
| SEC-002 | ERROR | AWS key pattern `AKIA[0-9A-Z]{16}` |
| SEC-003 | WARNING | Private local absolute paths in committed YAML |
| SEC-004 | ERROR | Forbidden path segments in publication paths |
| SEC-005 | WARNING | `.env` or `config/local.yaml` tracked by Git |
| SEC-006 | INFO | `config/local.yaml` exists locally (with `--include-local`) |

**Forbidden path segments (case insensitive):** `AI`, `Cursor`, `content`, `tools`, `config`, `references`, `docs`, `.cursor`

**Safe placeholder values (SEC-001):** empty, `null`, `none`, `~`, `""`, `''`, `<secret>`, `redacted`, `example`

### Validator dependency

| rule_id | Severity | Condition / purpose |
|---|---|---|
| VALIDATOR-DEP | ERROR | PyYAML not installed; validator cannot run |

---

## 6. Output format

### Text output

```text
Validator: core-validator v0.1
Root: <path>
Status: PASS | FAIL | ERROR
Checked: N  Failed: N  Errors: N  Warnings: N  Info: N

[SEVERITY] RULE_ID  message
  file: <path>
  field: <field>

Next action: none | Fix reported ERROR items... | Review WARNING items... | Validator internal error.
```

### JSON output

Single JSON object (UTF-8). With `--format both`, text output first, then line `---JSON---`,
then JSON body.

| Field | Required | Notes |
|---|---|---|
| `schema_version` | Yes | `"0.1"` |
| `task_id` | No | From `--task-id` or null |
| `validator` | Yes | `"core-validator"` |
| `validator_version` | Yes | `"0.1"` |
| `timestamp` | Yes | ISO 8601 UTC with `Z` suffix |
| `root` | Yes | Path used for validation |
| `status` | Yes | `PASS`, `FAIL`, or `ERROR` |
| `exit_code` | Yes | `0`, `1`, or `2` |
| `summary` | Yes | `{checked, failed_checks, errors, warnings, info}` |
| `findings` | Yes | All findings |
| `errors` | Yes | Subset with severity ERROR |
| `warnings` | Yes | Subset with severity WARNING |
| `next_action` | Yes | See section 7 |
| `duration_ms` | Yes | Execution time in milliseconds |

Matched secret values are **not** repeated in output (rule_id and field path only).

---

## 7. next_action

| Value | When |
|---|---|
| `none` | PASS (exit 0) |
| `fix_errors` | One or more ERROR (exit 1) |
| `review_warnings` | WARNING only with `--strict` (exit 1) |
| `validator_error` | Exit 2 (PyYAML missing, unreadable root, internal error) |

---

## 8. Known clean-template baseline

A fresh public template clone with no site-specific configuration is expected to **PASS**
(exit 0) without `--strict`.

Typical findings on the clean template:

| rule_id | Severity | Why it appears | Why it is expected | Becomes a problem when |
|---|---|---|---|---|
| CFG-010 | WARNING | `config/site.yaml` is not committed | Site project not configured yet | You need site-specific config and the file is still missing after setup |
| ENV-009 | INFO | `web.hostname` is null in environment example | Hostnames not configured in template | You deploy without setting hostname in your environment config |
| I18N-004 | INFO | No Markdown files in `content/en/` or `content/jp/` | Clean template ships empty content directories | You add content to one locale only (also triggers I18N-002/003) |

These are **not ERROR**. Status remains **PASS** unless `--strict` is used (CFG-010 WARNING
then causes FAIL).

---

## 9. Test suite

| Module | Count | Purpose |
|---|---|---|
| `tests/test_validate_framework.py` | 15 | Validator CLI, JSON output, rule behavior, I18N checks |
| `tests/test_translation.py` | 13 | Term dictionary, mock translation, build pipeline, locale validation |

**Validator tests** cover: baseline PASS, JSON validity, `--strict`, missing root, config
errors, secret non-echo, forbidden deploy paths, plugin absence, I18N basename rules.

**Translation tests** cover: dictionary lookup, mock provider, build output, validator
integration on minimal project copies, EN review preservation, single dictionary file policy.

---

## 10. Test execution model

Tests invoke `tools/core/validate_framework.py` and `tools/core/build_site.py` via
**subprocess** from the repository root, with `--root` pointing at a **temporary copy** of
project data.

Temporary copies include directory skeletons and config/content files only — not a second
copy of `tools/core/*.py`. This isolates tests from accidental edits to the live repository.

---

## 11. Fixtures

| Path | Role |
|---|---|
| `tests/fixtures/term_dictionary.yaml` | Dictionary entries for translation unit tests |
| `tests/fixtures/content/jp/*.md` | Sample Japanese content for build/integration tests |

Fixtures use fictional names for testing. Changing fixtures may change test expectations;
run the full suite after fixture edits.

Production dictionary: `config/term_dictionary.yaml` (copy from `config/term_dictionary.example.yaml`).

---

## 12. Validation workflow

Suggested flow for public template users and AI agents:

```text
Modify content or configuration
  ↓
Run tests (28/28 PASS)
  ↓
Run validator (PASS; review WARNING/INFO)
  ↓
Review findings — use rule catalog above
  ↓
Review git diff
  ↓
Human review when required (see AGENTS.md)
```

For validator and build commands, see also `tools/README.md` and `README.md`.
