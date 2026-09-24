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
source_hash: sha256:555b4c0de6d897c1326fdd4245ee3b314a57edaa6358a24f3c935d568f48840b
target_locale: DE
translation_status: TRANSLATED
---

[de]# Sample i18n Demo
[/de][de]This page demonstrates a shared structure for Japanese, English, and German output.
[/de][de]## Sample Artwork
[/de][de]The same logical-page artwork is reused across all three locales.
[/de]HADA Website Template
Human-AI Development Architecture
```python i18n-comments
[de]# Build the site from the structural master.[/de]
def build_site():
    return True
```
