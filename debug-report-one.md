# DEBUG ROOM — AGENT 1 (UI Forensics)

## What I did
- Opened the live Nexray tab in browser automation and identified it:
  - `https://web-production-6206c.up.railway.app/`
  - Reproduced login using `admin / admin`.
- Captured layout metrics after dashboard render.
- Located and patched `static/style.css` in repo.

## Root cause (with evidence)
**Cause:** CSS grid row placement for `.sidebar/.header/.main` is under-constrained and leads to implicit auto-placement behavior that leaves the sidebar at only the first row height instead of spanning both rows.

Evidence from live page after login (before fix):
- `document.querySelector('.app').getComputedStyle(...).gridTemplateRows` => `"0px 62px 800px"`
- Sidebar box: `height: 62px`
- Header box: `height: 62px`
- Main box: `height: 800px`
- So sidebar content area is effectively collapsed to header-height while main content receives remainder of viewport.

The side effect is the observed:
- Tiny visible sidebar strip
- Large blank/white main-region area behavior

## Patch (diff-ready)
File: `static/style.css`

- **Line 114** change:
```diff
-  grid-row: 1 / -1;
+  grid-row: 1 / 3;
```
- **Line 194** add explicit row placement:
```diff
 .header {
   grid-column: 2;
+  grid-row: 1;
   background: var(--color-surface);
```
- **Line 226** add explicit row placement:
```diff
 .main {
   grid-column: 2;
+  grid-row: 2;
   overflow-y: auto;
```

This makes the grid placement deterministic and prevents header/sidebar row ambiguity.

## Verification
- Live tab (manual injection + measurement before final file save):
  - After applying the same row placements (`sidebar 1 / 3`, `header 1`, `main 2`) in-browser, measured:
    - Sidebar height became `862px` (full viewport height)
    - Header height remained `62px`
    - Main remained `800px` (viewport remainder)
  - Previously, sidebar was only `62px`.

- Local static validation (Python HTTP server serving repo files):
  - Added temporary debug style in-browser with the exact same rules and confirmed:
    - Sidebar -> full height (862px) instead of 62px.

## Why this is minimal / safe
- No JS behavior changes.
- Only layout rules in one CSS section.
- Preserves existing responsive/mobile rules while making desktop desktop-grid placement explicit.

## Remaining risks
- Browser-specific/grid engine behavior with this auto-height setup should now be stable, but verify on very old/legacy Chromium builds.
- If a future refactor changes `.app` to add more explicit rows, these explicit assignments (1/2) may need revisiting.