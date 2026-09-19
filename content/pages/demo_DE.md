---
title: Sample i18n Demo
description: Three-locale i18n demonstration
logical_page: demo
source_locale: mixed
role: page
visual:
  background_fade:
    image_id: restaurant-background-001
source_file: content/pages/demo_master.md
source_hash: sha256:a0e9272d05d8b68c1348c3b8ec7638c7194b03d083e11fd5e4a78c92d8af9872
target_locale: DE
translation_status: TRANSLATED
---

[de]# Sample i18n Demo
[/de][de]This page demonstrates a shared structure for Japanese, English, and German output.
[/de]HADA Website Template
Human-AI Development Architecture
```python i18n-comments
[de]# Build the site from the structural master.[/de]
def build_site():
    return True
```
