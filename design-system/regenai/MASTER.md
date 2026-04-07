# Design System Master File

> **LOGIC:** When building a specific page, first check `design-system/pages/[page-name].md`.
> If that file exists, its rules **override** this Master file.
> If not, strictly follow the rules below.

---

**Project:** RegenAI
**Generated:** 2026-04-02 20:16:54
**Category:** Agriculture/Farm Tech

---

## Global Rules

### Color Palette

| Role | Hex | CSS Variable | Usage |
|------|-----|--------------|-------|
| Primary | `#15803D` | `--color-primary` | Headers, nav, primary buttons, links |
| On Primary | `#FFFFFF` | `--color-on-primary` | Text on primary surfaces |
| Secondary | `#22C55E` | `--color-secondary` | Success states, progress, active fields |
| On Secondary | `#0F172A` | `--color-on-secondary` | Text on secondary surfaces |
| Accent | `#A16207` | `--color-accent` | Harvest gold — CTAs, badges, highlights |
| On Accent | `#FFFFFF` | `--color-on-accent` | Text on accent surfaces |
| Background | `#F0FDF4` | `--color-background` | Page background (light green tint) |
| Foreground | `#14532D` | `--color-foreground` | Primary text |
| Card | `#FFFFFF` | `--color-card` | Card backgrounds |
| Card Foreground | `#14532D` | `--color-card-foreground` | Text on cards |
| Muted | `#E8F0F1` | `--color-muted` | Disabled, secondary backgrounds |
| Muted Foreground | `#64748B` | `--color-muted-foreground` | Secondary text, placeholders |
| Border | `#BBF7D0` | `--color-border` | Borders, dividers |
| Destructive | `#DC2626` | `--color-destructive` | Errors, delete actions |
| On Destructive | `#FFFFFF` | `--color-on-destructive` | Text on destructive |
| Ring | `#15803D` | `--color-ring` | Focus rings |

**Color Notes:** Earth green (#15803D) + harvest gold (#A16207). Agriculture/Farm Tech palette. Green conveys growth and trust in farming context. Gold accent for CTAs stands out against green without competing.

### Typography

- **Heading Font:** Lexend
- **Body Font:** Source Sans 3
- **Mood:** trustworthy, accessible, readable, professional, clean
- **Best For:** Enterprise, government, healthcare, agriculture — accessibility-focused
- **Google Fonts:** [Lexend + Source Sans 3](https://fonts.google.com/share?selection.family=Lexend:wght@300;400;500;600;700|Source+Sans+3:wght@300;400;500;600;700)
- **Tailwind Config:** `fontFamily: { heading: ['Lexend', 'sans-serif'], body: ['Source Sans 3', 'sans-serif'] }`

**Why Lexend:** Designed specifically to improve reading proficiency. Wide letter spacing reduces cognitive load — ideal for farmers scanning recommendations quickly on a phone in the field.

**CSS Import:**
```css
@import url('https://fonts.googleapis.com/css2?family=Lexend:wght@300;400;500;600;700&family=Source+Sans+3:wght@300;400;500;600;700&display=swap');
```

**Type Scale (mobile-first):**
| Token | Size | Weight | Usage |
|-------|------|--------|-------|
| `heading-1` | 28px / 1.75rem | 700 | Page titles |
| `heading-2` | 22px / 1.375rem | 600 | Section titles |
| `heading-3` | 18px / 1.125rem | 600 | Card titles |
| `body` | 16px / 1rem | 400 | Body text (minimum for mobile) |
| `body-lg` | 18px / 1.125rem | 400 | Recommendation text, important reads |
| `label` | 14px / 0.875rem | 500 | Form labels, metadata |
| `caption` | 12px / 0.75rem | 400 | Timestamps, fine print only |

### Spacing Variables

| Token | Value | Usage |
|-------|-------|-------|
| `--space-xs` | `4px` / `0.25rem` | Tight gaps |
| `--space-sm` | `8px` / `0.5rem` | Icon gaps, inline spacing |
| `--space-md` | `16px` / `1rem` | Standard padding |
| `--space-lg` | `24px` / `1.5rem` | Section padding |
| `--space-xl` | `32px` / `2rem` | Large gaps |
| `--space-2xl` | `48px` / `3rem` | Section margins |
| `--space-3xl` | `64px` / `4rem` | Hero padding |

### Shadow Depths

| Level | Value | Usage |
|-------|-------|-------|
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.05)` | Subtle lift |
| `--shadow-md` | `0 4px 6px rgba(0,0,0,0.1)` | Cards, buttons |
| `--shadow-lg` | `0 10px 15px rgba(0,0,0,0.1)` | Modals, dropdowns |
| `--shadow-xl` | `0 20px 25px rgba(0,0,0,0.15)` | Hero images, featured cards |

---

## Component Specs

### Buttons

```css
/* Primary Button — harvest gold CTA */
.btn-primary {
  background: #A16207;
  color: white;
  padding: 14px 28px;        /* Extra-large for work-glove taps */
  border-radius: 12px;
  font-weight: 600;
  font-size: 16px;
  min-height: 48px;           /* Meets 48dp Material touch target */
  transition: all 200ms ease;
  cursor: pointer;
}

.btn-primary:hover {
  background: #854d0e;
  transform: translateY(-1px);
}

/* Secondary Button — earth green outline */
.btn-secondary {
  background: transparent;
  color: #15803D;
  border: 2px solid #15803D;
  padding: 14px 28px;
  border-radius: 12px;
  font-weight: 600;
  font-size: 16px;
  min-height: 48px;
  transition: all 200ms ease;
  cursor: pointer;
}

/* Green filled button (for positive actions like "Mark as Done") */
.btn-success {
  background: #15803D;
  color: white;
  padding: 14px 28px;
  border-radius: 12px;
  font-weight: 600;
  font-size: 16px;
  min-height: 48px;
  transition: all 200ms ease;
  cursor: pointer;
}
```

### Farmer-Specific UI Rules

```
CRITICAL — These override general UX patterns for this product:

1. TOUCH TARGETS: Min 48x48px everywhere. Farmers wear work gloves.
2. FONT SIZE: Never below 16px for any interactive or readable text.
3. LANGUAGE: Plain English only. "Your soil needs more cover" not "SOC sequestration suboptimal."
4. PROGRESSIVE DISCLOSURE: Show the #1 action first. Details behind a tap.
5. NEXT ACTION: Every screen must answer "What do I do next?" with a visible CTA.
6. LOADING: Always show skeleton/spinner. Farmers on rural cellular (3G/4G).
7. OFFLINE TOLERANCE: Cache last-known data. Show "Last updated: [date]" when stale.
8. FIELD WIDTH: Max 375px for all critical flows (iPhone SE baseline).
9. NO JARGON: Avoid "EQIP" without "(cost-share program)" on first use per page.
10. ONE COLUMN: Mobile forms are single-column only. No side-by-side inputs.
```

### Cards

```css
.card {
  background: #F8FAFC;
  border-radius: 12px;
  padding: 24px;
  box-shadow: var(--shadow-md);
  transition: all 200ms ease;
  cursor: pointer;
}

.card:hover {
  box-shadow: var(--shadow-lg);
  transform: translateY(-2px);
}
```

### Inputs

```css
.input {
  padding: 12px 16px;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  font-size: 16px;
  transition: border-color 200ms ease;
}

.input:focus {
  border-color: #15803D;
  outline: none;
  box-shadow: 0 0 0 3px rgba(21, 128, 61, 0.15);
}
```

### Modals

```css
.modal-overlay {
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
}

.modal {
  background: white;
  border-radius: 16px;
  padding: 32px;
  box-shadow: var(--shadow-xl);
  max-width: 500px;
  width: 90%;
}
```

---

## Style Guidelines

**Style:** Organic Biophilic

**Keywords:** Nature, organic shapes, green, sustainable, rounded, flowing, wellness, earthy, natural textures

**Best For:** Wellness apps, sustainability brands, eco products, health apps, meditation, organic food brands

**Key Effects:** Rounded corners (16-24px), organic curves (border-radius variations), natural shadows, flowing SVG shapes

### Page Pattern

**Pattern Name:** Real-Time / Operations Landing

- **Conversion Strategy:** For ops/security/iot products. Demo or sandbox link. Trust signals.
- **CTA Placement:** Primary CTA in nav + After metrics
- **Section Order:** 1. Hero (product + live preview or status), 2. Key metrics/indicators, 3. How it works, 4. CTA (Start trial / Contact)

---

## Anti-Patterns (Do NOT Use)

- ❌ Generic design
- ❌ Ignored accessibility
- ❌ AI purple/pink gradients

### Additional Forbidden Patterns

- ❌ **Emojis as icons** — Use SVG icons (Heroicons, Lucide, Simple Icons)
- ❌ **Missing cursor:pointer** — All clickable elements must have cursor:pointer
- ❌ **Layout-shifting hovers** — Avoid scale transforms that shift layout
- ❌ **Low contrast text** — Maintain 4.5:1 minimum contrast ratio
- ❌ **Instant state changes** — Always use transitions (150-300ms)
- ❌ **Invisible focus states** — Focus states must be visible for a11y

---

## Pre-Delivery Checklist

Before delivering any UI code, verify:

- [ ] No emojis used as icons (use SVG instead)
- [ ] All icons from consistent icon set (Heroicons/Lucide)
- [ ] `cursor-pointer` on all clickable elements
- [ ] Hover states with smooth transitions (150-300ms)
- [ ] Light mode: text contrast 4.5:1 minimum
- [ ] Focus states visible for keyboard navigation
- [ ] `prefers-reduced-motion` respected
- [ ] Responsive: 375px, 768px, 1024px, 1440px
- [ ] No content hidden behind fixed navbars
- [ ] No horizontal scroll on mobile
