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
target_locale: JP
translation_status: SOURCE
---

# Sample i18n Demo

This page demonstrates a shared structure for Japanese, English, and German output.

## Sample Artwork

The same logical-page artwork is reused across all three locales.

<!-- i18n: no-translate -->
HADA Website Template
Human-AI Development Architecture
<!-- i18n: end -->

```python i18n-comments
# Build the site from the structural master.
def build_site():
    return True
```
