---
{
  "source_file": "content/pages/demo_master.md",
  "source_hash": "sha256:f95bbec40bb176ed7e4a34a5ba6fc40153f9321bf0d426b23ab6f2a76969ed55",
  "source_locale": "mixed",
  "target_locale": "JP",
  "translation_status": "SOURCE"
}
---

---
title: "Sample i18n Demo"
description: "HADA Website Template media feature demonstration"
logical_page: demo
page_id: demo
source_locale: mixed
role: page
---

# HADA Website Template Demo

This page demonstrates localized output and the JSON media catalog.

## Media Catalog

Page visuals are resolved from the shared JSON page binding.

<!-- i18n: no-translate -->
HADA Website Template
Human-AI Development Architecture
<!-- i18n: end -->

```python i18n-comments
# Build the site from the structural master.
def build_site():
    return True
```
