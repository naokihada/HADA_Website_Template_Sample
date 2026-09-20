# Core Display Extensions

The Template Core is designed for long-lived static Web publication.

## Durable baseline

- Semantic HTML contains the information and ordinary links.
- CSS improves layout, theme, typography, and accessibility presentation.
- Local JavaScript is optional enhancement only.
- External JavaScript, CDN runtime, external UI framework, and external theme
  service are not required or permitted for Core rendering.
- If JavaScript fails or is disabled, the page remains readable and navigable.

## Current v0.3.2 foundation

Generated Markdown pages include local Core display assets and independent
state attributes:

```html
<body data-theme="light" data-text-size="standard" data-mode="standard">
```

The optional controls provide Light/Dark theme and Standard/Large/Extra Large
text size. Persistence is disabled by default. The standard fallback is Light,
Standard, Standard mode, and no sound.

## Project extensions

Projects may add local JavaScript and custom modes, but must preserve ordinary
HTML navigation and content. Play Mode, sound, experimental motion, and brand
effects are Project or Sample responsibilities, not Core requirements.

Use `python tools/core/external_dependency_scan.py site` before release to
check the publication tree for external runtime references.
