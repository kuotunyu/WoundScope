# WoundScope Design System

> Source of truth for the React review workbench. Page-specific files under
> `pages/` override only the named rule and must preserve the safety and
> accessibility constraints in this document.

## Direction

- Concept: `Clinical Editorial／沉靜研究室`
- Style: paper-like, matte, precise, calm, research-focused
- Variance: 6/10; density: 7/10; motion: 3/10
- Avoid: framework-default dashboards, AI purple gradients, giant hero areas,
  repetitive cards, patient imagery, decorative clinical claims

## Color tokens

| Role | Light | Dark |
|---|---|---|
| Canvas | `#F4F1EA` | `#172024` |
| Surface | `#FBFAF7` | `#202B30` |
| Elevated | `#FFFFFF` | `#29363B` |
| Ink | `#24313A` | `#F3F0E8` |
| Muted ink | `#5E6A6F` | `#BEC8C8` |
| Primary | `#526C61` | `#9AB7AA` |
| Secondary | `#708E99` | `#A9C5CE` |
| Accent | `#B85F49` | `#E39A82` |
| Review | `#8A5D23` | `#E0B36A` |
| Success | `#426653` | `#8DB89D` |
| Border | `#D8D5CC` | `#3D4B50` |

- Normal text contrast: at least 4.5:1.
- Large text and non-text controls: at least 3:1.
- State meaning always combines icon, copy, and color.

## Typography

- Heading/metrics: `Noto Serif TC`, `Songti TC`, `PMingLiU`, serif.
- Body/UI: `Noto Sans TC`, `PingFang TC`, `Microsoft JhengHei`, sans-serif.
- No remote font request; system-local fallbacks prevent render blocking.
- Desktop body: 17px/1.65; mobile body: 16px/1.65.
- Secondary copy: at least 15px; labels/buttons: at least 16px.
- Metric numerals: 28–36px with a compact scope label.
- Long text measure: 42–72 characters.

## Layout and spacing

- 4/8px rhythm: 4, 8, 12, 16, 24, 32, 48.
- Container: min(1440px, viewport minus adaptive gutters).
- Desktop workbench: 12 columns; control 4, image stage 8.
- Tablet: 5/7 or stacked according to available width.
- Mobile: one column; result metrics form a 2×2 grid where readable.
- Interactive target: minimum 44×44px.
- Avoid nested cards when border, spacing, or typography already communicates hierarchy.

## Components

### Header

- Compact wordmark, runtime status, GitHub/cards links, labeled theme control.
- No fixed header that hides content; no icon-only control without accessible name.

### Evidence strip

- Exactly four concise verified signals.
- Every metric includes official-validation/non-clinical scope.
- Never resemble an e-commerce rating or leaderboard.

### Showcase

- Abstract inline SVG contour/grid only; `aria-hidden="true"`.
- Clearly labeled as interface illustration, never a prediction.
- Model-unavailable state is intentional permission-aware copy, not an error.

### Review workspace

- Visible upload label and helper/error text.
- Original/Overlay/Mask buttons use `aria-pressed`.
- Slider is keyboard-operable and shows its numeric value.
- Mask uses contour plus translucent fill; color is not the only signal.
- Loading disables duplicate submission and displays progress after 300ms.

## Depth, icons, and motion

- Lucide outline icons only, consistent stroke width and tokenized sizes.
- Border first; use one restrained shadow layer for elevated surfaces.
- Page canvas stays paper-like with a restrained cool haze; grid lines belong only
  inside segmentation／measurement surfaces, never across the whole page.
- Hover/focus/pressed transitions: 150–220ms, no layout-shifting transforms.
- One initial 180–260ms stagger; no continuous decorative motion.
- `prefers-reduced-motion: reduce` removes nonessential animation.
- Z-index scale only: 10 header, 20 controls, 30 fullscreen, 40 dialog.

## Required verification

- 390×844, 1024×768, 1440×900 and 375px small-phone width.
- Keyboard focus order, visible focus, upload errors, disabled/loading states.
- Light and dark contrast checked independently.
- No horizontal overflow, clipped text, hidden footer, or tiny controls.
- No medical images, private paths, filenames, model artifacts, or secrets.
