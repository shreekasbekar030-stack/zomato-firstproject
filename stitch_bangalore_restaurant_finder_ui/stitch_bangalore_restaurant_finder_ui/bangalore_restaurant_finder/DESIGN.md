---
name: Bangalore Restaurant Finder
colors:
  surface: '#151311'
  surface-dim: '#151311'
  surface-bright: '#3c3936'
  surface-container-lowest: '#100e0c'
  surface-container-low: '#1d1b19'
  surface-container: '#221f1d'
  surface-container-high: '#2c2927'
  surface-container-highest: '#373432'
  on-surface: '#e8e1dd'
  on-surface-variant: '#d2c5b0'
  inverse-surface: '#e8e1dd'
  inverse-on-surface: '#33302d'
  outline: '#9b8f7c'
  outline-variant: '#4e4636'
  surface-tint: '#f0c051'
  primary: '#ffd57e'
  on-primary: '#402d00'
  primary-container: '#e8b84a'
  on-primary-container: '#644900'
  inverse-primary: '#795900'
  secondary: '#d1c5ae'
  on-secondary: '#37301f'
  secondary-container: '#4e4634'
  on-secondary-container: '#c0b49d'
  tertiary: '#e5d9cd'
  on-tertiary: '#362f27'
  tertiary-container: '#c9bdb2'
  on-tertiary-container: '#544c43'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#ffdf9f'
  primary-fixed-dim: '#f0c051'
  on-primary-fixed: '#261a00'
  on-primary-fixed-variant: '#5b4300'
  secondary-fixed: '#eee1c9'
  secondary-fixed-dim: '#d1c5ae'
  on-secondary-fixed: '#211b0c'
  on-secondary-fixed-variant: '#4e4634'
  tertiary-fixed: '#ede0d5'
  tertiary-fixed-dim: '#d0c5b9'
  on-tertiary-fixed: '#201b13'
  on-tertiary-fixed-variant: '#4d453d'
  background: '#151311'
  on-background: '#e8e1dd'
  surface-variant: '#373432'
typography:
  headline-xl:
    fontFamily: Inter
    fontSize: 44px
    fontWeight: '600'
    lineHeight: 52px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '500'
    lineHeight: 32px
  headline-sm:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '500'
    lineHeight: 24px
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
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  label-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
    letterSpacing: 0.01em
  label-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.02em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 1.5rem
  margin: 2rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2.5rem
---

## Brand & Style

This design system establishes a refined, atmospheric culinary discovery experience tailored for Bangalore’s vibrant dining scene. The brand personality is discerning, grounded, and contemporary, evoking the warm, amber glow of upscale dining establishments and speakeasies. 

The UI adopts a **Minimalism** approach combined with deep, tactile dark-mode surfaces. It relies on heavy, purposeful whitespace, precise typography, and a restrained color palette that lets high-imagery food and venue photography take center stage. The emotional response is one of anticipation, exclusivity, and effortless exploration.

## Colors

The palette is anchored by deep charcoal-brown page backgrounds (`#100e0c`) layered with warm, raised surfaces (`#1c1916`) to create a subtle sense of elevation. Text hierarchies utilize a high-readability cream (`#f4efe6`) for primary content and a sophisticated muted gold-taupe (`#cbbfa8`) for secondary information. 

The primary accent is a rich, warm amber (`#e8b84a`), shifting to a brighter luminosity (`#f0c96a`) on hover, paired with deep dark text (`#1a1404`) for high-contrast interactive states. Feedback states are communicated through restrained semantic tones: an earthy rose error surface (`#3b1820`) and a deep botanical green summary surface (`#13261b`).

## Typography

The typography system utilizes Inter as a neutral grotesque foundation, balancing uncompromising legibility with understated elegance. Headings employ tighter letter-spacing and medium-to-semibold weights to anchor the layout, while body scales remain open and neutral for long-form restaurant descriptions and reviews. 

On mobile devices, scale down any headline exceeding 32px by 20% to prevent awkward wrapping within narrow viewports. Maintain strict adherence to defined line-heights to ensure ample vertical rhythm across dense lists of venues.

## Layout & Spacing

The layout relies on a **Fluid grid** system tailored for content-heavy discovery experiences. On desktop viewports, utilize a 12-column grid with 24px gutters and generous outer margins (`32px` to `64px`) to frame immersive restaurant cards and interactive maps. 

Spacing follows an 8px base rhythm. Components use strict, predictable internal padding scaled through the `space-*` tokens. On mobile form factors, the grid collapses to a single column with reduced outer margins (`16px`) while maintaining consistent 16px gutters for clean visual separation between venue tiles.

## Elevation & Depth

Depth is established primarily through **Tonal layers** rather than heavy drop shadows, aligning with the sophisticated dark theme. Raised surfaces (`#1c1916`) sit deliberately above the deeper page background (`#100e0c`) to create tier-based hierarchy for cards, modals, and navigation bars. 

Where separation requires crisp delineation, low-contrast outlines (`#3a332b`) act as ghost borders. Shadows, when used subtly on floating action elements or active dropdown menus, are deeply diffused, tinted with near-black tones to preserve the nocturnal atmosphere without introducing harsh black lines.

## Shapes

The design system employs a **Soft** shape language (`roundedness` level 1), favoring restrained, subtle curves over stark geometric right angles or overly playful pill shapes. Standard UI elements carry a `0.25rem` radius, while containers, input fields, and small cards utilize a refined `0.5rem` corner radius. 

Prominent hero cards, modals, and bottom sheets scale up to `0.75rem` (`rounded-xl`), creating a gentle, tactile containment that feels intentional and modern without sacrificing professional utility.

## Components

### Buttons
Primary actions utilize the solid accent background (`#e8b84a`) paired with dark button labels (`#1a1404`), shifting to the hover state (`#f0c96a`) on interaction. Secondary actions use transparent surfaces with low-contrast outlines (`#3a332b`) and primary text (`#f4efe6`). Maintain a minimum height of 44px for touch targets.

### Chips
Filter tags for cuisines, dietary preferences, and neighborhood selectors use the input fill surface (`#26231e`) with subtle borders (`#3a332b`) and muted text (`#cbbfa8`). Active states invert to the primary accent tone with dark text.

### Lists
Venue lists feature generous vertical padding with subtle bottom-border dividers. Each row houses structured metadata (name, cuisine, price tier, distance, and rating) aligned consistently across breakpoints.

### Checkboxes & Radio Buttons
Rendered with an input fill background (`#26231e`) and input borders (`#4a433a`). Selected states fill the control indicator with the primary accent (`#e8b84a`).

### Input Fields
Search bars and filter inputs feature the dedicated input fill (`#26231e`), structural borders (`#4a433a`), and placeholder text styled in muted text (`#cbbfa8`). Focus states shift the border seamlessly to the primary accent.

### Cards
Restaurant cards use raised surfaces (`#1c1916`) with low-contrast borders (`#3a332b`) and soft clipping for venue imagery. 

### Additional Components
- **Venue Rating Badges:** Compact badge indicators utilizing the summary surface (`#13261b`) for high ratings.
- **Quick-Filter Bar:** Horizontally scrollable container for fast neighborhood and cuisine toggling.
- **Map Pin Callouts:** Floating overlay containers mirroring raised surface styling for quick-preview details on map view.