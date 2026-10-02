# Project Assistant Design System

## Direction

Minimal, grid-based enterprise operations workspace. Prefer information hierarchy,
scan speed, and explicit state over decoration. Avoid glass effects, gradients,
playful motifs, hidden labels, and color-only status communication.

## Tokens

- Primary: `#0F172A`; on-primary: `#FFFFFF`.
- Accent/action: `#0369A1`; on-accent: `#FFFFFF`.
- Background: `#F8FAFC`; surface: `#FFFFFF`.
- Text: `#020617`; muted text: `#475569`.
- Border: `#E2E8F0`; muted surface: `#E8ECF1`.
- Destructive: `#B91C1C`; focus ring: `#0F172A`.
- Typography: Plus Jakarta Sans when available, then system sans-serif.
- Spacing: 4/8px base, dense dashboard range 8/12/16/24/32px.
- Radius: 8px controls, 12px panels. Shadows are subtle and limited to raised panels.

## Interaction

- One primary action per view; 44px minimum interactive height.
- Visible labels and inline validation for every form field.
- Persistent mode/status text; never rely on color alone.
- Loading, empty, error, and success states are explicit and screen-reader friendly.
- Focus ring is always visible for keyboard input.
- Motion is limited to opacity/transform feedback and disabled by reduced-motion.

## Responsive behavior

- Mobile first at 375px; no horizontal page scroll.
- Navigation wraps into a compact horizontal tab list on small screens.
- KPI panels use one column on mobile, two on tablet, four on desktop.
- Data rows wrap long identifiers and blocker content rather than truncating evidence.

