# Template Upgrade Guide

Upgrade an existing site project from a **GitHub stable Release** of
[HADA_Website_Template](https://github.com/naokihada/HADA_Website_Template).

This guide is the **Public Upgrade Contract**. It is not the Master Implementation Specification.

`TEMPLATE_BASE.md` records the current adopted Template Base after successful verification.
It contains Template ID, Template Name, Version, Release, and Repository only. Absence is
supported for legacy projects; unknown or manifest-inconsistent metadata requires review.
Dry-run and failed upgrades do not advance the Base.

---

## 1. Prerequisites

- Python 3.10+
- PyYAML (`pip install -r tools/core/requirements.txt`)
- Network access to `api.github.com` and GitHub
- Backup or Git working tree review before upgrading

---

## 2. Template version vs project version

| Field | Location | Meaning |
|---|---|---|
| Template version | `config/template.manifest.yaml` → `template.version` | HADA Website Template Release |
| Project version | `config/project.yaml` → `project.version` | Your site project metadata |

Do not use `project.version` as the template version.

---

## 3. Check current template version

1. If `config/template.manifest.yaml` exists → read `template.version` (**detected**)
2. Else legacy v0.1.1 sites may match release fingerprint (mechanical identification)
3. If unknown → upgrade stops with **BLOCKED** unless you pass `--assume-version` explicitly

---

## 4. Target release

| Mode | Behavior |
|---|---|
| Default | Latest **non-prerelease** GitHub Release |
| Explicit | `--version v0.2.0` |

Not used as upgrade source: `main`, branch HEAD, unreleased commits, prereleases (as stable default).

---

## 5. Run upgrade

From your site project root:

```text
pip install -r tools/core/requirements.txt
python tools/core/upgrade_from_release.py --root .
```

Explicit version:

```text
python tools/core/upgrade_from_release.py --root . --version v0.2.0
```

Legacy site without manifest (v0.1.1):

```text
python tools/core/upgrade_from_release.py --root . --assume-version v0.1.1
```

Dry run (plan only):

```text
python tools/core/upgrade_from_release.py --root . --dry-run
```

---

## 6. What is preserved (user-owned)

Never automatically overwritten:

- `content/` (Content Master)
- `config/term_dictionary.yaml`, `config/site.yaml`, `config/local.yaml`
- `site/assets/` (except template scaffold), `site/en/`, `site/jp/` HTML
- User-filled `AI/reports/`, `AI/tasks/`
- `references/registry/` (non-example), `references/cache/`

See `config/template.manifest.yaml` for the authoritative list.

---

## 7. Automatic updates

The engine compares **Previous Template**, **Current Site**, and **New Template**:

| Situation | Result |
|---|---|
| Template-only change | Automatic update |
| User-only change | Preserved |
| Both changed | **REVIEW_REQUIRED** |
| Unchanged | Skipped |

`config/project.yaml` uses safe key-level merge (preserves `project.name`, `project.mode`).

Generated HTML/content may require review if manually edited.

---

## 8. Exit status

| Code | Status | Meaning |
|---|---|---|
| 0 | SUCCESS | Safe changes applied |
| 1 | REVIEW_REQUIRED | Conflicts need human review |
| 2 | BLOCKED | Preflight failed; no safe migration |
| 3 | FAILED | Internal error |

---

## 9. Temporary clone

The tool fetches the Release to a temp directory (e.g. `%TEMP%\hada-template-upgrade-<uuid>\`).
**The temp clone is retained** for inspection. The report includes the absolute path.

---

## 10. Git safety

The upgrade tool does **not** create branches, commit, push, tag, merge, or reset your site repository.
Review `git diff` after upgrade before committing.

## 10.1 Legacy agent workspace migration

During a Template Upgrade, inspect the target project for the retired `.cursor/` and
`Cursor/` locations. This step applies to the existing consumer project being upgraded;
it does not modify any other repository.

Before removal:

1. Preserve the current `SPEC.md`, template manifest, relevant reports, and affected
   files under the target project's retained upgrade or handoff history.
2. Classify the legacy contents. Move useful project-wide rules into the target's
   agent-independent documentation, and move useful reports, tasks, and history into
   `AI/history/`.
3. Record the migrated paths and discarded obsolete adapter instructions in the final
   upgrade report.
4. Remove `.cursor/` and `Cursor/` after the inventory and migration plan are complete.
5. Create or update `AI/`, then run ReSPEC, tests, validator, build, and diff review.

Do not delete either location blindly. If ownership, meaning, or data preservation is
unclear, stop with `REVIEW_REQUIRED` and preserve the legacy location until a human
decides.

---

## 11. Post-upgrade validation

```text
python tests/test_validate_framework.py
python tests/test_translation.py
python tools/core/validate_framework.py --root .
python tools/core/build_site.py --root .
```

See `docs/VALIDATION.md` for validator rules and baseline.

---

## 12. v0.1.1 → v0.1.2

First automated migration path. Adds:

- `config/template.manifest.yaml`
- `tools/core/upgrade_from_release.py`
- `docs/UPGRADE.md`, `CHANGELOG.md`

v0.1.1 sites without manifest: use fingerprint detection or `--assume-version v0.1.1`.

---

## 13. v0.1.2 → v0.1.3

Adds the client-only PWA Timer Demo at `site/timer.html`, including Beep audio,
Service Worker notifications, and an offline app-shell cache. Notification delivery
after complete PWA termination is best-effort and not guaranteed.

## 14. v0.1.3 → v0.2.0

Migrates the agent-operation workspace from the retired `.cursor/` and `Cursor/`
locations to the agent-neutral `AI/` workspace. Before applying removal:

1. Preserve the current `SPEC.md`, template manifest, relevant reports, and affected files.
2. Inventory and classify both legacy locations.
3. Move useful reports, tasks, and historical evidence to `AI/history/`.
4. Move reusable project-wide guidance into agent-independent documentation; do not activate obsolete adapter rules.
5. Record the migration plan before removing either legacy directory.
6. If ownership, meaning, or data preservation is unclear, stop with `REVIEW_REQUIRED`.
7. After migration, run ReSPEC, tests, validator, build, security check, and read-only diff review.

## 15. Troubleshooting

| Issue | Action |
|---|---|
| BLOCKED: network | Check connectivity to GitHub |
| BLOCKED: unknown version | Add manifest or use `--assume-version` |
| REVIEW_REQUIRED | Inspect listed paths; merge manually |
| Large unexpected diff | Stop; restore from backup if needed |

---

## 15. Not included

- Web deployment / FTP / production publish
- Automatic Git commit or push
- Using `main` branch as upgrade source
