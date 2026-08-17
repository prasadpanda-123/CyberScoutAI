---
name: CyberScout AI
colors:
  surface: '#0b1326'
  surface-dim: '#0b1326'
  surface-bright: '#31394d'
  surface-container-lowest: '#060e20'
  surface-container-low: '#131b2e'
  surface-container: '#171f33'
  surface-container-high: '#222a3d'
  surface-container-highest: '#2d3449'
  on-surface: '#dae2fd'
  on-surface-variant: '#bfc7d2'
  inverse-surface: '#dae2fd'
  inverse-on-surface: '#283044'
  outline: '#89929b'
  outline-variant: '#3f4850'
  surface-tint: '#93ccff'
  primary: '#93ccff'
  on-primary: '#003351'
  primary-container: '#3198dc'
  on-primary-container: '#002c47'
  inverse-primary: '#006398'
  secondary: '#7bd0ff'
  on-secondary: '#00354a'
  secondary-container: '#00a6e0'
  on-secondary-container: '#00374d'
  tertiary: '#ffb875'
  on-tertiary: '#4b2800'
  tertiary-container: '#d07d1c'
  on-tertiary-container: '#412200'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#cce5ff'
  primary-fixed-dim: '#93ccff'
  on-primary-fixed: '#001d31'
  on-primary-fixed-variant: '#004b73'
  secondary-fixed: '#c4e7ff'
  secondary-fixed-dim: '#7bd0ff'
  on-secondary-fixed: '#001e2c'
  on-secondary-fixed-variant: '#004c69'
  tertiary-fixed: '#ffdcc0'
  tertiary-fixed-dim: '#ffb875'
  on-tertiary-fixed: '#2d1600'
  on-tertiary-fixed-variant: '#6b3b00'
  background: '#0b1326'
  on-background: '#dae2fd'
  surface-variant: '#2d3449'
  bg-body: '#070B14'
  bg-surface: '#0B0F19'
  bg-card-hover: '#1E293B'
  admin-accent: '#EF4444'
  success: '#10B981'
  warning: '#F59E0B'
  danger: '#EF4444'
  info: '#06B6D4'
  border-subtle: '#1E293B'
  text-primary: '#F8FAFC'
  text-secondary: '#94A3B8'
  text-muted: '#64748B'
typography:
  display-kpi:
    fontFamily: Inter
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 48px
    letterSpacing: -0.04em
  headline-lg:
    fontFamily: Inter
    fontSize: 30px
    fontWeight: '600'
    lineHeight: 36px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.02em
  headline-sm:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-caps:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
  mono-code:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 20px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  sidebar-width: 280px
  sidebar-collapsed: 64px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 32px
  stack-sm: 8px
  stack-md: 16px
  stack-lg: 32px
---

## Brand & Style

The design system embodies a **Technical Precision** aesthetic, tailored for high-stakes cybersecurity environments. It rejects the stereotypical "hacker" tropes in favor of a mature, sophisticated interface that communicates reliability and systemic intelligence.

### Design Principles
- **Clarity over Decoration:** Every pixel serves a functional purpose. Minimalist principles guide the layout, ensuring that critical security data is never obscured by unnecessary visual noise.
- **Directional Hierarchy:** Information flows from high-level system health metrics to granular log details. High-contrast typography ensures immediate legibility in high-pressure scenarios.
- **Architectural Depth:** The UI uses a "Substrate" model. The background is the foundation, surfaces are the workspaces, and cards are the actionable units.
- **Safety through Color:** The system uses distinct color modes—User (Primary Blue) and Admin (Alert Red)—to provide immediate cognitive orientation, preventing accidental administrative actions in the wrong context.

### Visual Style: Corporate Modern / Technical
Drawing inspiration from high-end developer tools and aerospace interfaces, the system utilizes tight grids, low-radius geometry, and a sophisticated dark-first palette. It prioritizes the "tool" feel over the "website" feel.

## Colors

This design system utilizes a refined dark mode as its default state to reduce eye strain for security analysts. A crisp light mode is available, maintaining the same semantic logic but flipping the lightness values for surfaces and text.

### Color Logic
- **Primary & Secondary:** Used exclusively for user-facing interactive elements, focus states, and primary brand indicators.
- **Admin Palette:** When in administrative contexts, the primary blue is replaced with `admin-accent` (Red). This includes borders, buttons, and focus rings to signal "High-Privilege" access.
- **Semantic Feedback:** Success, Warning, and Danger colors are reserved for status badges, system health indicators, and form validation.
- **Surface Tiering:**
  1. `bg-body`: The deepest layer.
  2. `bg-surface`: Used for sidebars and secondary navigation.
  3. `neutral_color_hex` (bg-card): The interactive surface for content.

## Typography

The system relies on a high-performance sans-serif stack for maximum readability. 

### Implementation Rules
- **Tightened Tracking:** Headings and KPI metrics use negative letter spacing to create a compact, "engineered" look.
- **Mono Integration:** Use `jetbrainsMono` for all system IDs, hash values, terminal outputs, and log streams.
- **Labeling:** Small labels and metadata should use `label-caps` for clear distinction from body text.
- **Responsive Scaling:** On mobile, `headline-lg` should scale down to 24px. KPI metrics should never drop below 32px to ensure they remain the focal point of the dashboard.

## Layout & Spacing

The layout is built on a **Fixed Sidebar / Independent Scroll** model. This ensures that global navigation is always accessible while analyzing long-form data tables or logs.

### Grid & Containers
- **Main Content:** Utilizes a fluid grid with a maximum content width of 1600px to maintain readability on ultra-wide monitors.
- **Sidebar:** Fixed to the left. It supports a collapsed state (icons only) to maximize workspace during deep analysis.
- **Mobile:** The sidebar transitions to an off-canvas drawer. Margins are reduced to 16px to maximize horizontal space for tables.

### Spacing Rhythm
The system uses a strict 8px base grid. All margins and paddings should be multiples of 8. Consistent `stack` variables ensure vertical rhythm between card elements and sections.

## Elevation & Depth

This design system uses **Tonal Layering** and **Subtle Glows** instead of traditional heavy shadows.

### Depth Strategy
- **Base Layer:** `bg-body` is the "floor" of the application.
- **Raised Surfaces:** `bg-surface` (sidebar) and `bg-card` (content tiles) use color shifts to indicate elevation.
- **Focus Glows:** Interactive elements like active inputs or primary buttons use a soft, 15% opacity glow (`brand-glow`) to signify focus.
- **Glassmorphism:** The top navigation bar uses a high-blur (20px) background filter with 92% opacity to maintain a sense of space while scrolling.
- **Admin Boundaries:** Administrative containers use a subtle red inner-border or glow to indicate "high-alert" status.

## Shapes

The shape language is **Soft-Geometric**. We use a conservative 4px (0.25rem) base radius to maintain a professional, technical feel.

- **Buttons & Inputs:** Use the base `rounded` (4px) setting.
- **Cards:** Use `rounded-lg` (8px) to provide enough visual separation from the background.
- **Status Badges:** Use a pill-shape (full rounding) to differentiate them from interactive buttons.
- **Selection States:** Focus rings should follow the radius of the element they wrap with a 2px offset.

## Components

### Buttons
- **Primary:** Solid `brand-primary` with white text. On hover, apply a subtle scale (0.98) and increase glow.
- **Admin Action:** Solid `admin-accent` (Red). Reserved for destructive or high-privilege actions.
- **Ghost:** `border-subtle` with `text-secondary`. Used for secondary actions in the sidebar or table headers.

### Data Tables
- **Header:** Sticky with a subtle border-bottom. Use `label-caps` for column titles.
- **Rows:** Subtle hover state change to `bg-card-hover`. No vertical borders, only horizontal dividers.
- **Badges:** Success/Warning/Danger/Info colors with low-opacity backgrounds and high-contrast text.

### Cards
- **Opportunity/KPI Cards:** Use `bg-card`. Metrics are displayed using `display-kpi`. Metadata is tucked into the footer with `text-muted`.
- **Profile Card:** Located at the bottom of the fixed sidebar. High-contrast avatar with a clear logout/settings trigger.

### Input Fields
- **Styling:** Dark backgrounds (`bg-body`) with `border-subtle`.
- **Focus:** Border transitions to `brand-primary` (or `admin-accent` in admin mode) with a soft outer glow.
- **Monospace:** Use for API keys, secret tokens, and ID fields.

### Navigation
- **Sidebar:** Active items use a vertical 2px "intent" bar on the left and a subtle background tint.
- **Off-Canvas:** Full-height drawer on mobile with a semi-transparent backdrop blur.