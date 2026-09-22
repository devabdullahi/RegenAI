# Design System Master File

> **LOGIC:** When building a specific page, first check `design-system/pages/[page-name].md`.
> If that file exists, its rules **override** this Master file.
> If not, strictly follow the rules below.

---

**Project:** RegenAI
**System:** Field Record (replaces the 2026-04 "Agriculture/Farm Tech" card system)
**Revised:** 2026-09-18
**Implemented in:** `frontend/src/app/globals.css` (tokens + component classes),
`frontend/src/components/shared/record.tsx` (Sheet, RuleHead, LedgerRow, Stamp, EdgeNote)

---

## 1. The idea

RegenAI stands in for paperwork a farmer already keeps: NRCS conservation plan
sheets, county extension bulletins, elevator scale tickets, seed tags, plat
books. The interface borrows those conventions instead of SaaS conventions.

What that means in practice:

- The page is a **record sheet**, not a feed of cards.
- Structure comes from **hairline rules and small-caps section heads**, not from
  boxes with shadows.
- Every number is a **figure with a unit**, set in mono, aligned in a column.
- Program codes are **stamped** (`CPS 340`, `FY2026`, `19169`), because that is
  how they appear on the forms the farmer files.
- Color is **structural**: green marks the farm's own record, red-orange marks
  something with a deadline. Nothing is colored for cheer.

## 2. Hard rules

**Never:**
- shadows, gradients, glassmorphism, blur, glows
- rounded cards as the default container (radius is 2px, everything)
- an icon next to every heading — an icon must carry information the words do
  not (weather condition, nav target, severity)
- a pill-shaped badge — status is a stamp or a left edge bar
- equal visual weight for every section — see §6
- emoji, decorative blobs, illustrations, 3D objects
- a figure printed without its unit

**Always:**
- 48px minimum touch target; 16px minimum input font (set in `globals.css` base)
- plain language: "How much CSP could pay you", not "Optimize your program ROI"
- both themes defined from tokens; never a literal color in a component
- `font-mono` + `tabular-nums` for acres, bushels, dollars, points, dates, codes

## 3. Color

Tokens live in `globals.css` as OKLCH. Hex is the design reference.

| Role | Light | Dark | Usage |
|------|-------|------|-------|
| `--background` | `#F2EDE1` manila | `#16170F` | Page ground |
| `--card` | `#FCFAF4` | `#1F2017` | Record sheets, inputs, nav |
| `--foreground` | `#191C17` ink | `#E8E3D2` | Text |
| `--muted-foreground` | `#5A5F52` pencil | `#9C9885` | Labels, captions, leaders |
| `--border` / `--rule` | `#CFC7B3` | `#37382B` | Hairlines, ledger leaders |
| `--rule-strong` | `#191C17` | `#E8E3D2` | Heavy rule under a page title |
| `--primary` | `#2E5E32` field green | `#83A874` | The farm's own record, primary actions |
| `--accent` | `#B4441F` implement red | `#DE7A4E` | Deadlines, "act now", one per screen |
| `--success` | `#3A6B3A` | `#83A874` | Met thresholds, completed steps |
| `--warning` | `#97701A` grain amber | `#C89A3E` | Approaching cutoffs |
| `--destructive` | `#9B2C17` barn red | `#C9563A` | Errors, restricted-use flags |
| `--info` | `#2C4A6B` plat blue | `#71A0C4` | Neutral program notes |
| `--soil` | `#7A5B3A` | `#B08A5E` | Soil data |
| `--weather` | `#3A6076` slate | slate lifted | Weather data |

Charts use `--chart-1..5` in that order: green, amber, soil, slate, red-orange.
No neon, no series that only differ by lightness.

## 4. Typography

| Role | Face | Variable | Notes |
|------|------|----------|-------|
| UI + headings | **Archivo** | `--font-ui` | 600 for headings, tracking -0.015em |
| Reading matter | **Source Serif 4** | `--font-reading` | `.reading`, 17px/1.6 — program rules, rationale |
| Figures + codes | **IBM Plex Mono** | `--font-data` | labels, stamps, every number |

Serif is not decoration: the app's job is explaining USDA rules, and that text
is read, not scanned. Chrome (buttons, nav, labels) stays sans; figures stay
mono. Do not set an entire page in serif.

| Token | Size | Weight | Usage |
|-------|------|--------|-------|
| Page title | 28–32px | 600 Archivo | One per page, above a strong rule |
| Section head | 11px | 500 mono, `.rule-head` / `RuleHead` | Uppercase, 0.14em tracking |
| Card/record title | 16px | 600 Archivo | |
| Body | 16px | 400 Archivo | UI copy |
| Reading | 17px | 400 Source Serif | `.reading`, max ~62ch |
| Figure | 14–28px | 500 mono | Always with unit |
| Caption | 12px | 400 | Sources, as-of dates |

## 5. Components

**Sheet** — `<Sheet>`: 1px border, `bg-card`, 2px radius, no shadow. Holds a
section. Sections are separated by space and rules, not by stacked boxes.

**RuleHead** — `<RuleHead label="Resource concerns" action={…}/>`: small-caps
mono label, hairline to the end of the measure, optional action past the rule.
This replaces most card headers.

**LedgerRow** — `<LedgerRow label="Total acres" value="480.0 ac" />`: label,
dotted leader, mono figure. The default way to present any label/value pair.
Stack them; do not put each in its own box.

**Stamp** — `<Stamp>CPS 340</Stamp>`: boxed mono code. For practice codes,
fiscal years, FIPS, document types.

**EdgeNote** — `<EdgeNote tone="warning" title="Sign-up closes Mar 21">`: 3px
left bar in the tone color on ordinary paper. Replaces tinted alert cards.

**Buttons** — square (2px), sans, medium. `default` = green (do the farm's
work), `accent` = red-orange (deadline-bound), `outline` = secondary,
`ghost` = tertiary, `link` = inline. Sizes: `lg` 48px for primary page actions,
`default` 44px, `sm` 36px for inline actions. One primary per view.

**Inputs** — ruled box on `bg-card`, 48px tall, 2px radius. Labels are mono
small caps above the blank. Helper text sits under the input at 12px.

## 6. Density and hierarchy

Not every section is equal, and the page should show it.

- **Decisions get room**: "What to do this week", recommendation rationale —
  serif, generous leading, wide measure.
- **Records get density**: activity log, yield history, resource concerns,
  payment lines — tight rows, mono figures, hairline dividers, no padding
  inflation. A farmer comparing 8 concerns wants them in one glance.
- **One page title, one primary action, one accent** per screen. If everything
  is emphasized, nothing is.

## 7. Accessibility

- 48px targets, 16px inputs (enforced in base layer).
- Text contrast ≥ 4.5:1 on paper in both themes; `--warning` and `--accent` are
  dark enough for body text on light paper, and are lifted in dark.
- Focus: 2px ring in `--ring` with 2px offset. Never remove it.
- Status never relies on color alone: the word is always present next to the
  bar or stamp.
- Respect `prefers-reduced-motion` (handled globally). Transitions are color
  only; nothing floats, fades in on scroll, or animates on load.
