---
title: Sample i18n Demo
description: Three-locale i18n demonstration
logical_page: demo
source_locale: mixed
role: page
source_file: content/pages/demo_master.md
source_hash: sha256:2eaebe20fe693036634c4dfd310b4b490e9b50854c9750994d4afa315e8c8ff3
target_locale: JP
translation_status: SOURCE
---

# Sample i18n Demo

This page demonstrates a shared structure for Japanese, English, and German output.

<!-- i18n: no-translate -->
HADA Website Template
Human-AI Development Architecture
<!-- i18n: end -->

```python i18n-comments
# Build the site from the structural master.
def build_site():
    return True
```
