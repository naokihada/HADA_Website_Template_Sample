# Core Validator — Specification v0.1

Specification for the first deterministic validator in `tools/core/`.

**Status:** IMPLEMENTED (v0.1)  
**Canonical contract:** `AGENTS.md`  
**Implementation:** `tools/core/validate_framework.py`

### Runtime dependencies

- Python 3.10+
- PyYAML >= 6.0 (`tools/core/requirements.txt`)

If PyYAML is missing, the validator exits with code `2` and does not run validation rules.

---

## 1. Purpose

Provide **mechanical, deterministic pre-validation** of the HADA Website Operations Framework
repository before task execution, commit, release candidate preparation, or plugin install
preflight.

The validator answers: *Does this repository meet the structural, configuration, and
publication-safety baseline defined by Architecture v0.1 and Foundation scaffolding?*

It does **not** judge content quality, design, legal compliance, or production release approval.

---

## 2. Scope

### In scope

| Area | Checks |
|---|---|
| A. Repository structure | Required directories and files exist |
| B. Configuration | YAML syntax, required keys, allowed enum values, cross-reference consistency |
| C. Environment | LOCAL / STAGING / PRODUCTION definitions and safety flags |
| D. References | Registry syntax and required fields; no private paths in committed config |
| E. Plugin manifest | Schema validation when `manifest.yaml` exists under `tools/plugins/` |
| F. Security / publication safety | Secret-like values, private paths, unsafe deploy targets |

### Repository root

Validation runs against the **project repository root** (directory containing `AGENTS.md`).
Default: current working directory when invoked; overridable via `--root`.

### Configuration files validated (when present)

| File | Required at ERROR if missing |
|---|---|
| `config/project.yaml` | Yes |
| `environments/environments.example.yaml` | Yes |
| `references/registry/references.example.yaml` | Yes |
| `config/site.yaml` | No (optional; validate if present) |
| `config/site.example.yaml` | Yes (Foundation baseline) |
| `config/local.yaml` | No (gitignored; validate syntax only if `--include-local`) |

---

## 3. Non-Goals

The validator must **not**:

- Judge content, translation, or design quality
- Perform semantic / AI-based analysis
- Assess legal or policy compliance
- Approve or reject production release
- Call external services (WordPress.com, FTP, n8n, GitHub, etc.)
- Modify any file
- Require network access
- Scan entire site content trees or external reference repositories
- Replace human approval for STAGING / PRODUCTION operations

---

## 4. Inputs

### Command-line (planned)

| Input | Required | Description |
|---|---|---|
| `--root PATH` | No | Repository root (default: `.`) |
| `--format text\|json\|both` | No | Output format (default: `both`) |
| `--task-id ID` | No | Correlates result with agent task or CI job |
| `--include-local` | No | Also validate `config/local.yaml` if present |
| `--strict` | No | Treat WARNING as ERROR (exit 1) |

### Files read (read-only)

- Repository tree (existence checks only; no deep content traversal beyond configured paths)
- `AGENTS.md` (existence only)
- `.cursor/rules/*.md` (count and existence; no semantic review)
- YAML files listed in Scope
- `tools/plugins/*/manifest.yaml` (each present plugin directory only; no recursion into plugin code bodies beyond manifest)

### Environment variables

None required. The validator must not depend on secrets or GitHub credentials.

---

## 5. Validation Rules

Each rule has a stable `rule_id` for machine-readable output.

### A. Repository Structure (`STRUCT-*`)

| rule_id | Severity | Condition |
|---|---|---|
| `STRUCT-001` | ERROR | `AGENTS.md` exists at repository root |
| `STRUCT-002` | ERROR | `README.md` exists at repository root |
| `STRUCT-003` | ERROR | `.gitignore` exists at repository root |
| `STRUCT-004` | ERROR | Directory `Cursor/` exists |
| `STRUCT-005` | ERROR | Directory `content/en/` exists |
| `STRUCT-006` | ERROR | Directory `content/jp/` exists |
| `STRUCT-007` | ERROR | Directory `site/` exists |
| `STRUCT-008` | ERROR | File `site/README.md` exists |
| `STRUCT-009` | ERROR | Directory `site/en/` exists |
| `STRUCT-010` | ERROR | Directory `site/jp/` exists |
| `STRUCT-011` | ERROR | Directory `site/assets/` exists |
| `STRUCT-012` | ERROR | Directory `references/registry/` exists |
| `STRUCT-013` | ERROR | Directory `references/cache/` exists |
| `STRUCT-014` | ERROR | Directory `references/reports/` exists |
| `STRUCT-015` | ERROR | Directory `environments/` exists |
| `STRUCT-016` | ERROR | Directory `tools/core/` exists |
| `STRUCT-017` | ERROR | Directory `tools/plugins/` exists |
| `STRUCT-018` | ERROR | Directory `tests/` exists |
| `STRUCT-019` | ERROR | Directory `docs/` exists |
| `STRUCT-020` | ERROR | Directory `config/` exists |
| `STRUCT-021` | ERROR | Directory `.cursor/rules/` exists |
| `STRUCT-022` | WARNING | Fewer than 8 files in `.cursor/rules/` (Foundation defines 8 adapter rules) |
| `STRUCT-023` | ERROR | `paths.publication_root` directory from `config/project.yaml` exists |

### B. Configuration (`CFG-*`)

| rule_id | Severity | Condition |
|---|---|---|
| `CFG-001` | ERROR | `config/project.yaml` parses as valid YAML |
| `CFG-002` | ERROR | `project.id`, `project.name`, `project.version`, `project.mode` present |
| `CFG-003` | ERROR | `project.mode` is one of: `NEW`, `RECOVERY`, `MIGRATION`, `MAINTENANCE` |
| `CFG-004` | ERROR | `paths.publication_root`, `paths.content_master`, `paths.tools_core`, `paths.tools_plugins` present |
| `CFG-005` | ERROR | `locales.default` is listed in `locales.supported` |
| `CFG-006` | ERROR | Each locale in `locales.supported` is exactly `en` or `jp` (Foundation baseline) |
| `CFG-007` | ERROR | `paths.publication_root` value resolves to existing directory |
| `CFG-008` | ERROR | `paths.content_master` value resolves to existing directory |
| `CFG-009` | ERROR | `config/site.example.yaml` parses as valid YAML |
| `CFG-010` | WARNING | `config/site.yaml` missing (expected until site project configured) |
| `CFG-011` | ERROR | If `config/site.yaml` present: `site.publication_root` matches or is subdirectory policy of `config/project.yaml` `paths.publication_root` |
| `CFG-012` | ERROR | If `config/site.yaml` present: `publication.deploy_target` must equal `site/` or value of `paths.publication_root` |
| `CFG-013` | ERROR | `publication.locales.*` paths must stay under publication root (prefix check) |
| `CFG-014` | ERROR | `plugins.enabled[].state` when present must be valid lifecycle state: `SPECIFIED`, `INSTALLING`, `INSTALLED`, `ENABLED`, `DISABLED`, `UNINSTALLING`, `UNINSTALLED`, `FAILED` |
| `CFG-015` | ERROR | `rss.default_state` when present must be `FULL`, `PARTIAL`, or `NO_CONTENT` |

### C. Environment (`ENV-*`)

| rule_id | Severity | Condition |
|---|---|---|
| `ENV-001` | ERROR | `environments/environments.example.yaml` parses as valid YAML |
| `ENV-002` | ERROR | Top-level key `environments` exists |
| `ENV-003` | ERROR | Keys `LOCAL`, `STAGING`, `PRODUCTION` each exist under `environments` |
| `ENV-004` | ERROR | Each environment has `description`, `approval_required`, `publication_root` |
| `ENV-005` | ERROR | `PRODUCTION.approval_required` is `true` |
| `ENV-006` | ERROR | `STAGING.approval_required` is `true` |
| `ENV-007` | WARNING | `LOCAL.approval_required` is not `false` |
| `ENV-008` | ERROR | No environment `publication_root` points outside repository or to forbidden paths (`Cursor/`, `content/`, `tools/`, `config/`, `references/`, `docs/`, `.cursor/`) |
| `ENV-009` | INFO | `web.hostname` is null (informational until configured) |

If `environments/environments.yaml` exists (future non-example file), apply the same rules at ERROR.

### D. References (`REF-*`)

| rule_id | Severity | Condition |
|---|---|---|
| `REF-001` | ERROR | `references/registry/references.example.yaml` parses as valid YAML |
| `REF-002` | ERROR | `version` field present |
| `REF-003` | ERROR | `references` is a list |
| `REF-004` | ERROR | Each reference entry has `id`, `type`, `description`, `readonly` |
| `REF-005` | ERROR | Reference `id` values are unique |
| `REF-006` | ERROR | Reference `id` matches pattern `^[a-z0-9][a-z0-9-]*$` |
| `REF-007` | WARNING | Committed registry entry contains `path:` with absolute Windows or Unix home path |
| `REF-008` | WARNING | Committed registry entry contains `url:` with embedded credentials (`user:pass@`) |
| `REF-009` | ERROR | If `adapter: wordpress-com` present, `type` must be `external_content_source` |

Committed registry files = any `references/registry/*.yaml` tracked by Git except `*.example.yaml` is still validated if present; example file is always validated.

### E. Plugin Manifest (`PLUGIN-*`)

Applied only when `tools/plugins/<plugin-id>/manifest.yaml` exists.

| rule_id | Severity | Condition |
|---|---|---|
| `PLUGIN-001` | ERROR | Manifest parses as valid YAML |
| `PLUGIN-002` | ERROR | Required keys: `plugin.id`, `plugin.version`, `plugin.status`, `plugin.spec_version` |
| `PLUGIN-003` | ERROR | `plugin.id` matches directory name `<plugin-id>` |
| `PLUGIN-004` | ERROR | `plugin.status` is valid lifecycle state (see CFG-014) |
| `PLUGIN-005` | ERROR | `plugin.spec_version` is semver-like (`MAJOR.MINOR` or `MAJOR.MINOR.PATCH`) |
| `PLUGIN-006` | WARNING | `dependencies` missing when status is `ENABLED` |
| `PLUGIN-007` | ERROR | `ownership.maintainer` present when status is `ENABLED` or `INSTALLED` |
| `PLUGIN-008` | WARNING | `changed_files` missing when status is `INSTALLING` or `INSTALLED` |
| `PLUGIN-009` | INFO | `reversibility.uninstall_supported` documented (boolean) |
| `PLUGIN-010` | ERROR | `plugin.id` must not equal reserved core name: `core-validator` |

Foundation phase: zero plugin directories expected — no ERROR if `tools/plugins/` contains only `.gitkeep`.

#### Manifest schema (normative minimum)

```yaml
plugin:
  id: example-plugin
  version: "0.1.0"
  spec_version: "0.1"
  status: SPECIFIED   # lifecycle state
dependencies: []      # list of plugin ids or package refs
ownership:
  maintainer: string
changed_files: []     # paths relative to repo root
reversibility:
  uninstall_supported: true
```

Foundation phase: zero plugin directories expected — no ERROR if `tools/plugins/` contains only `.gitkeep`.

### F. Security / Publication Safety (`SEC-*`)

Pattern-based only. Not a full secret scanner.

| rule_id | Severity | Condition |
|---|---|---|
| `SEC-001` | ERROR | Committed YAML/text under `config/`, `environments/`, `references/registry/` matches password assignment pattern (e.g. `password:`, `passwd:`, `api_key:` with non-null non-placeholder value) |
| `SEC-002` | ERROR | Value matches `AKIA[0-9A-Z]{16}` (AWS key pattern) in committed config |
| `SEC-003` | WARNING | Absolute path `C:\Users\` or `D:\_dev\` in committed YAML (private local path) |
| `SEC-004` | ERROR | `deploy_target`, `publication_root`, or locale publish path includes forbidden segment: `Cursor`, `content`, `tools`, `config`, `references`, `docs`, `.cursor` |
| `SEC-005` | WARNING | `.env` or `config/local.yaml` tracked by Git (should be gitignored) |
| `SEC-006` | INFO | `config/local.yaml` exists locally (not an error; informational when `--include-local`) |

Placeholder values considered safe (do not ERROR): `null`, empty string, `""`, `"<secret>"`, `"REDACTED"`, example comments.

### G. Internationalization (`I18N-*`)

Deterministic basename matching between `content/en/` and `content/jp/`. No semantic matching.

| rule_id | Severity | Condition |
|---|---|---|
| `I18N-001` | ERROR | Each locale in `config/project.yaml` `locales.supported` has `content/{locale}/` directory |
| `I18N-002` | WARNING | For each file in `content/en/`, same basename exists in `content/jp/` |
| `I18N-003` | WARNING | For each file in `content/jp/`, same basename exists in `content/en/` |
| `I18N-004` | INFO | Both locale directories have no content master files (excluding `.gitkeep`) |

Content master files are immediate children of locale directories only (no recursive scan in v0.1).

---

## 6. Severity

| Level | Meaning | Default exit impact |
|---|---|---|
| `ERROR` | Baseline contract violated; do not proceed with dependent automation | Fail |
| `WARNING` | Non-blocking issue or incomplete configuration | Pass (unless `--strict`) |
| `INFO` | Informational; no action required | Pass |

---

## 7. Exit Status / Result

| Exit code | Meaning |
|---|---|
| `0` | No ERROR (WARNING/INFO allowed unless `--strict`) |
| `1` | One or more ERROR, or WARNING with `--strict` |
| `2` | Validator internal failure (unreadable root, IO error, bug) |

Overall result `status`:

| status | Condition |
|---|---|
| `PASS` | Zero ERROR |
| `FAIL` | One or more ERROR |
| `ERROR` | Validator could not complete (maps to exit 2) |

---

## 8. Output Format

### Human-readable (stdout)

Short summary table:

```text
Validator: core-validator v0.1
Root: D:/_dev/github/HADA_Website_Template_Dev
Status: PASS | FAIL
Checked: 42  Failed: 0  Errors: 0  Warnings: 1  Info: 2

[ERROR] SEC-004  publication.deploy_target must not include forbidden path segment 'tools'
  file: config/site.yaml
  field: publication.deploy_target

Next action: Fix reported ERROR items before release or plugin install.
```

### Machine-readable (stdout or `--format json`)

Single JSON object (UTF-8, no trailing noise). Written to stdout when `--format json`; when
`both`, human text first then JSON delimiter line `---JSON---` then JSON body.

---

## 9. Machine-Readable Result

```yaml
# Conceptual schema — JSON equivalent required at implementation
schema_version: "0.1"
task_id: null              # from --task-id or null
validator: core-validator
validator_version: "0.1"
timestamp: "2026-09-06T23:00:00Z"   # ISO 8601 UTC
root: "."
status: PASS                 # PASS | FAIL | ERROR
exit_code: 0
summary:
  checked: 42
  failed_checks: 0
  errors: 0
  warnings: 1
  info: 2
findings:
  - rule_id: ENV-009
    severity: INFO
    message: "web.hostname is null"
    file: environments/environments.example.yaml
    field: environments.LOCAL.web.hostname
errors: []                   # subset of findings where severity=ERROR
warnings: []                 # subset severity=WARNING
next_action: "none"          # short machine-usable hint
duration_ms: 120
```

JSON field requirements:

| Field | Required | Notes |
|---|---|---|
| `schema_version` | Yes | Spec version for consumers |
| `task_id` | No | Agent / CI correlation |
| `validator` | Yes | Constant: `core-validator` |
| `validator_version` | Yes | Implementation version |
| `timestamp` | Yes | ISO 8601 UTC |
| `root` | Yes | Absolute or relative path used |
| `status` | Yes | `PASS`, `FAIL`, `ERROR` |
| `exit_code` | Yes | 0, 1, or 2 |
| `summary` | Yes | Counts only |
| `findings` | Yes | All items |
| `errors` | Yes | Filtered list (may be empty) |
| `warnings` | Yes | Filtered list (may be empty) |
| `next_action` | Yes | e.g. `fix_errors`, `review_warnings`, `none`, `validator_error` |
| `duration_ms` | Yes | Execution time |

---

## 10. Human-Readable Result

Same run produces the summary in Section 8. Agents should append full JSON path or paste
into `Cursor/reports/TEST.md` when validation is part of a task gate.

Label facts only — do not infer causes not present in findings.

---

## 11. Safety Rules

1. **Read-only** — never write, delete, or rename repository files.
2. **No network** — no fetch, push, or external API calls.
3. **No secret echo** — when a pattern matches, report rule_id and field path; do not repeat matched secret value in output.
4. **No production side effects** — validation does not deploy or enable plugins.
5. **Scope limit** — do not scan `site/` HTML bodies, `content/` bodies, or `references/cache/` file contents (existence-only for cache dir).
6. **Deterministic** — same repository state produces same findings ordering (sort by `rule_id`, then `file`).
7. **AGENTS.md authority** — if this spec and `AGENTS.md` conflict, `AGENTS.md` wins; report spec issue, do not auto-fix architecture.

---

## 12. Future Extensibility

| Extension | Mechanism |
|---|---|
| New rules | Add `rule_id` with category prefix; bump `validator_version` minor |
| Site-specific config | Optional `config/site.yaml` rules remain optional until file exists |
| Active environment file | `environments/environments.yaml` same schema as example |
| Plugin manifests | `PLUGIN-*` rules apply per `tools/plugins/*/manifest.yaml` |
| Strict CI mode | `--strict` promotes WARNING to ERROR |
| Rule packs | Future `config/validator.yaml` may disable INFO or elevate selected WARNING (out of v0.1 scope) |
| Report output | Optional `--report PATH` writing JSON to `Cursor/reports/` (implementation phase) |

Do not add plugin implementations in validator v0.1 — manifest validation is schema-only.

---

## 13. Example Validation Result

### Example A — PASS (Foundation baseline, no plugins)

```json
{
  "schema_version": "0.1",
  "task_id": "foundation-verify-001",
  "validator": "core-validator",
  "validator_version": "0.1",
  "timestamp": "2026-09-06T23:05:00Z",
  "root": "D:/_dev/github/HADA_Website_Template_Dev",
  "status": "PASS",
  "exit_code": 0,
  "summary": {
    "checked": 38,
    "failed_checks": 0,
    "errors": 0,
    "warnings": 2,
    "info": 1
  },
  "findings": [
    {
      "rule_id": "CFG-010",
      "severity": "WARNING",
      "message": "config/site.yaml missing",
      "file": "config/site.yaml",
      "field": null
    },
    {
      "rule_id": "ENV-009",
      "severity": "INFO",
      "message": "web.hostname is null",
      "file": "environments/environments.example.yaml",
      "field": "environments.LOCAL.web.hostname"
    }
  ],
  "errors": [],
  "warnings": [
    {
      "rule_id": "CFG-010",
      "severity": "WARNING",
      "message": "config/site.yaml missing",
      "file": "config/site.yaml",
      "field": null
    }
  ],
  "next_action": "none",
  "duration_ms": 95
}
```

### Example B — FAIL (unsafe deploy target)

```json
{
  "schema_version": "0.1",
  "task_id": null,
  "validator": "core-validator",
  "validator_version": "0.1",
  "timestamp": "2026-09-06T23:06:00Z",
  "root": ".",
  "status": "FAIL",
  "exit_code": 1,
  "summary": {
    "checked": 40,
    "failed_checks": 1,
    "errors": 1,
    "warnings": 0,
    "info": 0
  },
  "findings": [
    {
      "rule_id": "SEC-004",
      "severity": "ERROR",
      "message": "deploy path must not include forbidden segment 'tools'",
      "file": "config/site.yaml",
      "field": "publication.deploy_target"
    }
  ],
  "errors": [
    {
      "rule_id": "SEC-004",
      "severity": "ERROR",
      "message": "deploy path must not include forbidden segment 'tools'",
      "file": "config/site.yaml",
      "field": "publication.deploy_target"
    }
  ],
  "warnings": [],
  "next_action": "fix_errors",
  "duration_ms": 88
}
```

---

## Alignment Notes

- Publication Root default `site/` — per `AGENTS.md` and `site/README.md`
- Plugin lifecycle states — per `AGENTS.md` Plugin Rules
- RSS states — per Architecture v0.1 (`FULL`, `PARTIAL`, `NO_CONTENT`)
- Locales `en` / `jp` — per Foundation `config/project.yaml`
- WordPress.com adapter naming — per Architecture v0.1 (`wordpress-com` separate from `wordpress`)

**Known Foundation baseline:** `config/site.yaml` is not committed; `CFG-010` WARNING is expected until site configuration is created.
