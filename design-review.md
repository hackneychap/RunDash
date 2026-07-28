# Design Review — RunDash Dashboard

**URL:** http://172.31.32.1:8000/
**Review Date:** 2026-06-11
**Reference Template:** Sentry (data-dense dashboard)
**Reviewer:** Bea (design perspective)
**Note:** Chart.js CDN blocked by headless browser — charts render as empty containers. Review covers layout, cards, hierarchy, colour, and spacing only.

---

## Executive Summary

- **Total issues:** 5 (Critical: 0, High: 1, Medium: 2, Low: 2)
- **Overall visual quality:** Good — clean dark theme, strong colour system, clear hierarchy
- **Key wins:** Colour consistency across comparison cards and all-time stats, clear section titles, good responsive grid
- **Key concerns:** Missing Elevation in all-time totals, comparison cards could use more visual weight

---

## Issues Found

### 1. Missing Elevation in All Time Totals
- **Severity:** High
- **Category:** Layout / Data Completeness
- **Section:** All Time Totals
- **Description:** The "This Week vs Last Week" section shows all 4 measures (Distance, Elevation, Duration, TSS), but "All Time Totals" only shows 3 (Distance, Duration, Avg TSS). Elevation is missing.
- **Expected:** All Time Totals should include Total Elevation alongside the other 3 measures, or the section title should clarify it's a subset.
- **Impact:** Inconsistent data story — the comparison cards promise 4 measures, the totals show 3.

### 2. Comparison Cards Lack Visual Weight
- **Severity:** Medium
- **Category:** Visual Hierarchy
- **Section:** This Week vs Last Week
- **Description:** The comparison cards have a thin coloured left border and a small label, but the large number dominates. The "Last week: X · ±Y%" subtext is quite small and low-contrast (text-base-content/50). For a section that's the most important training signal, the cards feel a bit lightweight.
- **Expected:** Consider making the card label (Distance, Elevation, etc.) slightly larger or bolder, and the percentage indicator more prominent. The Sentry reference uses uppercase labels with letter-spacing for metric names.
- **Suggestion:** Add `text-transform: uppercase` and `letter-spacing: 0.05em` to the card labels to match the all-time stat titles.

### 3. Section Title Spacing
- **Severity:** Medium
- **Category:** Spacing
- **Section:** Between "This Week vs Last Week" and "All Time Totals"
- **Description:** The section titles (`h2`) have consistent styling but the gap between the comparison cards and the "All Time Totals" heading feels tight. The Sentry reference uses generous vertical spacing (64–80px) between sections.
- **Expected:** Increase `mb-4` to `mb-6` or `mb-8` on the section headings for more breathing room.

### 4. TSS Card Missing Unit
- **Severity:** Low
- **Category:** Typography / Labels
- **Section:** This Week vs Last Week → TSS card
- **Description:** The TSS comparison card shows `166.9` with no unit label. Distance has "km", Elevation has "m", Duration has "hrs", but TSS has nothing. The all-time TSS stat also has no unit.
- **Expected:** TSS is a unitless score, but adding a small "(score)" or just leaving it is fine — the inconsistency with the other 3 cards having units is the issue.

### 5. Monthly Trends Section Feels Isolated
- **Severity:** Low
- **Category:** Layout
- **Section:** Monthly Trends
- **Description:** The monthly section has a single chart in a half-width card, which leaves a lot of empty space on the right. This creates an asymmetric, slightly orphaned feel.
- **Expected:** Consider either making the monthly chart full-width, or adding a second monthly chart (e.g., monthly TSS or monthly elevation) to fill the row.

---

## What's Working Well

- **Colour system is solid.** Blue = distance, emerald = duration, purple = TSS, amber = elevation. Consistent across comparison cards, all-time stats, and (from the code) the charts. This is exactly how Sentry handles colour — each metric has a signature colour.
- **Section titles are clear.** "This Week vs Last Week", "All Time Totals", "Weekly Trends", "Monthly Trends" — the hierarchy is immediately scannable.
- **Dark theme is clean.** The DaisyUI/Tailwind dark theme works well. Cards have subtle borders and shadows without being heavy.
- **Comparison card layout is responsive.** 4 cards in a row on desktop, 2x2 on tablet, stacked on mobile — the grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 is a good pattern.
- **Percentage indicator is honest.** Plain text, no colour coding, just the number. Matches the "no judgement" requirement.

---

## Recommendations (Priority Order)

1. **Add Elevation to All Time Totals** — either as a 4th stat card or clarify the section is a subset. This is the most visible gap.
2. **Uppercase the card labels** — `text-transform: uppercase; letter-spacing: 0.05em` on the comparison card labels to match the all-time stat titles and give them more visual weight.
3. **Increase section spacing** — bump `mb-4` on section headings to `mb-6` or `mb-8` for more breathing room between sections.
4. **Consider full-width monthly chart** — or add a second monthly chart to fill the row.

---

## Reference: Sentry Design Principles Applied

| Sentry Principle | RunDash Implementation | Status |
|-----------------|----------------------|--------|
| Colour-coded metrics | Blue/emerald/purple/amber per measure | ✅ Consistent |
| Dark theme with depth | DaisyUI dark with card shadows | ✅ Working |
| Uppercase labels with letter-spacing | Not applied to comparison cards | ⚠️ Could improve |
| Generous section spacing (64–80px) | Using `mb-4` (16px) | ⚠️ Tight |
| Data-dense but scannable | 4 measures + 4 charts | ✅ Good |
| Consistent card styling | Comparison cards vs all-time stats differ slightly | ⚠️ Minor gap |
