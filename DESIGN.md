# Design philosophy

The aesthetic is **simple and mono**: an engineering tool, not a consumer
app. Flat surfaces, square corners, a monospace voice for anything that
reads like data, one accent colour, and no decoration that doesn't carry
information. When in doubt, remove it.

The single source of truth for visual decisions is the **design-token
block at the top of `src/index.css`** (`:root`). Component CSS reads from
those variables; nothing else should hardcode a colour, radius, or font
stack. This document explains the intent behind the tokens — the tokens
themselves are authoritative.

---

## 1. Corners are square. Only buttons are rounded.

This is the rule most likely to be violated by new code, so it comes
first.

- **Boxes are square.** Cards, panels, sections, inputs, selects,
  textareas, modals, table wrappers, the map frame, badges, chips — every
  rectangular container has `border-radius: 0`.
- **Buttons are the sole exception.** Action buttons use
  `var(--radius-button)` (4px). Nothing else may use it.
- **Circles and pills are shapes, not corners.** `50%` (status dots,
  spinners, toggle knobs) and `999px` (pills, step indicators) are left
  alone — they're intentional geometry, not rounded boxes.

Tokens:

```
--radius-button  4px   buttons ONLY
--radius         0     every box (inputs, cards, panels, modals, badges)
--radius-lg      0     alias of --radius — do not reuse in new code
```

`--radius` / `--radius-lg` are kept at `0` so existing `var(--radius*)`
references stay flat without a sweep. New box CSS should simply omit
`border-radius` (it defaults correctly) or set `0` explicitly.

Why: rounded corners read as "friendly product." A square grid of square
panels reads as an instrument. Mixing the two (a rounded validation box
next to square analytics cards) is the inconsistency this rule eliminates.

---

## 2. One accent colour: teal.

```
--brand         #0f766e   active / focus / primary CTA
--brand-strong  #0b5d56   pressed / emphasis
--brand-soft    #f0fdfa   tint backgrounds
--accent        #0f766e   (= --brand)
```

- There is **no blue**. Stray `#2563eb` / `#1d4ed8` and ad-hoc
  `rgba(37,99,235,...)` tints have been folded to teal. Don't reintroduce
  them.
- Semantic colours are reserved for meaning, never decoration:
  `--danger #dc2626` (errors), `--warn #f59e0b` (warnings),
  `--warm #f97316` (transformers on the map). `--ok` is an alias of
  `--brand` — success is teal, not a separate green.
- Status text is **neutral by default** (`--text`), coloured only when the
  colour _is_ the signal (an error count, a danger pill). A large coloured
  headline for "all clear" is decoration — keep it neutral.

Backgrounds step lightest → containers: `--bg #f8fafc`, then
`--surface` / `--panel` (`#fff`). Lines are 1px: `--border #e2e8f0`,
`--border-strong #cbd5e1`. `--shadow` is `none` by default; elevation is
reserved for true overlays (modals) only.

---

## 3. Typography: sans for prose, mono for data.

```
--font-sans   IBM Plex Sans  — body, labels, descriptions, headings
--font-mono   JetBrains Mono — numbers, IDs, counts, filenames, chips,
                               badges, code-like values, settings keys
```

Use mono wherever the content is a value the user reads precisely
(counts, MW/kV figures, snapshot timestamps, component names in chips).
Use sans for everything that is read as language.

Base size is `13px`. Sizes are drawn from a small rem scale — `0.68 /
0.72 / 0.78 / 0.82 / 1.0 / 1.05 rem` and up — rather than arbitrary
values. Don't invent new sizes; reuse a rung. Numeric columns use
`font-variant-numeric: tabular-nums`.

---

## 4. Spacing.

Inline literals are fine, drawn from: **4 / 6 / 8 / 12 / 14 / 18 / 24 px**.
Pick a rung; don't introduce `13px` or `17px` gaps.

---

## 5. Tables fit their content.

Data-grid columns are **sized to their content**, not a fixed width. The
grid measures the header plus a sample of cell values and clamps the
result (`COL_MIN_WIDTH` … `COL_MAX_WIDTH` in
`src/features/input/grid/DataGrid.tsx`). A column of short codes is narrow;
a column of long names is wide. Fixed uniform widths waste space and bury
content — avoid them.

---

## 6. CSS hygiene.

`src/index.css` is large and has accumulated late "patch" overrides over
time. Rules:

- **One canonical rule per selector.** When you need to change a value,
  edit the existing rule — do not append a second `.foo { ... }` later in
  the file that silently overrides it. Late top-level duplicates are the
  main source of "I changed it and nothing happened" bugs.
- Responsive overrides belong **inside** their `@media` / `@container`
  block — that's a legitimate second definition; a second _top-level_
  definition is not.
- New visual constants go in the `:root` token block, not inline.

---

## Quick checklist for new UI

- [ ] No `border-radius` on boxes (only buttons get `var(--radius-button)`).
- [ ] No blue; accent is `var(--brand)`.
- [ ] Colour used only to carry meaning, not to decorate.
- [ ] Numbers / IDs / chips in `var(--font-mono)`.
- [ ] Font size is a rung on the existing scale.
- [ ] No second top-level definition of an existing selector.
- [ ] Table columns sized to content, not fixed.
