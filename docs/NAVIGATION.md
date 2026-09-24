# Static Navigation and Breadcrumbs

Use ordinary HTML links for site navigation. This pattern is static, keyboard
operable, and usable when JavaScript is disabled. It does not require a database,
client-side routing, or external scripts.

## Authoring model

Maintain the navigation and breadcrumb markup in each localized HTML Master.
Keep each locale's labels translated and destinations aligned with the same
logical pages. The template does not generate these elements from the Page
Registry or rewrite existing HTML Masters. When a route changes, update and
review the affected locale masters together.

## Primary and section navigation

The primary navigation may include a non-link group label. Put that group's
pages in a second navigation landmark. The group label is not a fabricated page
link. Mark the current page on its actual link with `aria-current="page"`.

```html
<div class="site-nav-stack">
  <nav class="site-nav-primary" aria-label="Primary navigation">
    <a href="/en/">Home</a>
    <a href="/en/services/">Services</a>
    <span class="site-nav-group" aria-current="true">About</span>
    <a href="/en/gallery/">Gallery</a>
  </nav>
  <nav class="site-nav-secondary" aria-label="About navigation">
    <a href="/en/about/">Company</a>
    <a href="/en/about/naoki.html">Naoki</a>
    <a href="/en/about/tour.html">Website Tour</a>
    <a href="/en/about/sitemap.html">Site Map</a>
  </nav>
</div>
```

On pages outside the section, use the same stack and reserve an empty secondary
row on wide screens. It must not be focusable or exposed to assistive technology.
Core CSS removes that empty row on narrow screens. Navigation links remain
visible and wrap naturally; do not add a JavaScript hamburger or collapse menu.

```html
<div class="site-nav-stack">
  <nav class="site-nav-primary" aria-label="Primary navigation">
    <!-- This localized page's primary links and group label. -->
  </nav>
  <div class="site-nav-empty-secondary" aria-hidden="true"></div>
</div>
```

## Breadcrumbs

Breadcrumbs describe the logical page hierarchy, not necessarily the directory
tree. Use an ordered list inside a separately named navigation landmark. Link
actual ancestor pages to their existing root-relative routes; render group labels
without a page route as text. Identify the current page with
`aria-current="page"`. The home page has no breadcrumb.

```html
<nav class="site-breadcrumbs" aria-label="Breadcrumb">
  <ol>
    <li><a href="/en/">Home</a></li>
    <li>About</li>
    <li><a href="/en/about/">Company</a></li>
    <li aria-current="page">Notice</li>
  </ol>
</nav>
```

A site map may link to a page without becoming its breadcrumb parent. For
example, a notice page can be linked from both Company and the Site Map while
its single logical parent remains Company. Declare the appropriate hierarchy in
the page's HTML Master; never infer it only from a path such as `/notice/`.

## Localization and verification

Translate navigation and breadcrumb labels for each supported locale. Preserve
the existing route for every logical page and use root-relative internal links.
When adding or changing a page, check every locale for:

- The same logical parent, order, and destination for equivalent pages.
- Correct localized labels and current-page indication.
- A complete breadcrumb path, with the current page as its final item.
- Keyboard access and visible focus for every link.
- No external JavaScript dependency.
- Natural wrapping on narrow screens and no empty secondary-row gap there.
