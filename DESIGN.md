---
name: AuditForge
description: A cinematic, evidence-led financial investigation workspace.
colors:
  ink: "#1d1d1f"
  muted: "#65656c"
  action-blue: "#0071e3"
  action-blue-hover: "#0077ed"
  cool-white: "#f5f5f7"
  surface: "#fff"
  line: "#dedee3"
  workspace-bg: "#0d131d"
  secondary-bg: "#ececf0"
  secondary-hover: "#e0e0e6"
  secondary-text: "#26262c"
  steel-surface: "#e9eef3"
  cinema-black: "#101113"
  focus-blue: "#67b2ff"
  tutorial-copy: "#bbcee2"
  note-copy: "#a2b7cf"
  success-bg: "#234a43"
  success-text: "#b4e6d3"
  error-text: "#ac2e2e"
  workspace-panel: "#172230"
  workspace-ink: "#e9f0f9"
  workspace-muted: "#a9b8ca"
  workspace-line: "#344153"
  workspace-action: "#2085d6"
  workspace-field: "#101a27"
  evidence-light: "#b8e6ea"
typography:
  display:
    fontFamily: "SF Pro Display, SF Pro Text, -apple-system, BlinkMacSystemFont, Manrope, Segoe UI, sans-serif"
    fontSize: "clamp(46px, 4.7vw, 72px)"
    fontWeight: 650
    lineHeight: 1.06
    letterSpacing: "-0.04em"
  headline:
    fontFamily: "SF Pro Display, SF Pro Text, -apple-system, BlinkMacSystemFont, Manrope, Segoe UI, sans-serif"
    fontSize: "clamp(36px, 4.2vw, 60px)"
    fontWeight: 650
    lineHeight: 1.08
    letterSpacing: "-0.035em"
  title:
    fontSize: "32px"
    fontWeight: 650
    lineHeight: 1.1
    letterSpacing: "-0.035em"
  body:
    fontSize: "16px"
    lineHeight: 1.55
  label:
    fontSize: "13px"
    fontWeight: 600
  button:
    fontSize: "15px"
    fontWeight: 550
    lineHeight: 1.25
  identifier:
    fontFamily: "ui-monospace, Consolas, monospace"
    fontSize: "11px"
rounded:
  tag: "4px"
  badge: "5px"
  control-small: "7px"
  input: "9px"
  document: "10px"
  panel: "12px"
  dialog: "15px"
  surface: "16px"
  pill: "999px"
spacing:
  segmented-inset: "4px"
  control-gap: "9px"
  compact-gap: "12px"
  form-row-gap: "18px"
  grid-gap: "20px"
  action-gap: "24px"
  panel-padding: "30px"
  feature-padding: "42px"
components:
  button-primary:
    backgroundColor: "{colors.action-blue}"
    textColor: "{colors.surface}"
    typography: "{typography.button}"
    rounded: "{rounded.pill}"
    padding: "14px 24px"
  button-primary-hover:
    backgroundColor: "{colors.action-blue-hover}"
  button-secondary:
    backgroundColor: "{colors.secondary-bg}"
    textColor: "{colors.secondary-text}"
    typography: "{typography.button}"
    rounded: "{rounded.pill}"
    padding: "14px 24px"
  button-secondary-hover:
    backgroundColor: "{colors.secondary-hover}"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.input}"
    padding: "13px 14px"
  feature-card:
    backgroundColor: "{colors.cool-white}"
    rounded: "{rounded.surface}"
    padding: "{spacing.feature-padding}"
  workspace-panel:
    backgroundColor: "{colors.workspace-panel}"
    rounded: "{rounded.panel}"
    padding: "{spacing.panel-padding}"
  state-badge:
    backgroundColor: "#eaf1fa"
    textColor: "#48688d"
    rounded: "{rounded.badge}"
    padding: "6px 10px"
  state-badge-completed:
    backgroundColor: "{colors.success-bg}"
    textColor: "{colors.success-text}"
  evidence-tag:
    backgroundColor: "#eef3f8"
    textColor: "#536d88"
    rounded: "{rounded.tag}"
    padding: "5px 6px"
---

# Design System: AuditForge

## Overview

**Creative North Star: "Apple-style product demonstration translated to financial evidence"**

The implemented world translates the user’s Apple Vision Pro video reference into financial evidence: generous cool-white introductory space, graphite inspection and finale scenes, large typography, physical document scenes and restrained blue actions. Presentation is cinematic; the investigation workspace carries the same type and materials into denser, legible tools.

Depth explains inspection and linked records. A metallic scanner and layered papers carry the visual signature; the working interface uses quiet borders and tonal grouping so records, evidence and remaining steps stay readable. This is the implemented system extracted from code, not a new visual proposal.

**Key Characteristics:**

- Large, tightly tracked system typography.
- Cool-white introductory surfaces and graphite operating surfaces with restrained blue actions.
- Physical document depth in presentation; bounded panels in work.
- Motion with pause and reduced-motion alternatives.
- Russian, Kazakh and English text supported by the shared font stack.

## Colors

The palette combines cool white, near-black ink and steel evidence materials, with blue reserved for action.

### Primary

- **Action Blue:** primary buttons, text links, caret and selected navigation. The brighter hover sibling signals an available action.

### Neutral

- **Cool White / Surface:** page fields and white content regions; the workspace has its own slightly cooler background.
- **Ink / Muted:** primary reading and secondary landing copy; muted text is a role, not a disabled state.
- **Steel Surface / Cinema Black:** evidence materials and the dark document sequence.
- **Line:** shared neutral separation; panels also use contextual gray borders from their source component.
- **Tutorial Copy / Note Copy:** final contrast corrections for onboarding prose and small notes.

Success and error tokens are semantic feedback accents. Focus Blue is reserved for keyboard focus, not a new decorative brand color.

**The Action Blue Rule.** Use blue for actions, selected navigation and interaction cues; keep document materials predominantly neutral.

## Typography

**Display Font / Body Font:** installed SF Pro Display / SF Pro Text, then platform system fonts, self-hosted Manrope and Segoe UI. The CSS stack is shared across the interface; there is no separate decorative face.

**Label/Mono Font:** UI monospace / Consolas for record identifiers, fields and trajectories.

**Character:** broad, tightly tracked headlines pair with clear compact controls. Weights are intentionally intermediate (550, 600, 650 and 750 in the brand), rather than forcing a generic regular/bold pair.

### Hierarchy

- **Display:** hero heading; the normative desktop role is overridden at the actual breakpoints below.
- **Headline:** landing section headings. The dark connection scene uses a nearby scene-specific clamp from its stylesheet.
- **Title:** feature headings; workspace headings use their own hierarchy (36px desktop, 32px at the medium breakpoint, 28px on phone).
- **Body:** landing reading copy. Workspace reading copy is generally 13–15px after final readability overrides; tutorial copy is 14px and small notes 13px in the final cascade.
- **Label:** compact field labels; episode labels and fact labels are 14px desktop and 13px on phone after final overrides.
- **Button:** shared pill action role; small and contextual actions keep their source-specific sizes.
- **Identifier:** monospaced evidence and record references. Allow long IDs to break where the source does so.

**The Local Font Rule.** Use SF Pro only through installed system fonts. Serve the bundled Manrope fallback; do not redistribute Apple fonts.

## Layout

Landing sections use generous vertical space (145px with 7% horizontal inset), an 1180px content width, and a three-column feature grid with a 20px gap and two-column feature spans. The header/footer container is 1320px; the hero is bounded at 1600px. The workspace uses a 1440px container, 44px desktop side padding and a 330px configuration rail beside the episode panel.

At the medium breakpoint (1100px maximum), navigation and workspace insets tighten, the episode rail becomes 290px, and the final hero heading override becomes 48px between 761px and 1100px. At the phone breakpoint (760px maximum), presentation and workspace columns become one column, landing sections use 90px / 24px padding, the auth visual is hidden, and workspace content uses 18px side padding. Top workspace tabs remain horizontal and scrollable; tables scroll inside their bordered wrapper.

On phone the final hero heading is `clamp(34px, 7.4vw, 54px)` and the final action heading is `clamp(30px, 8.8vw, 46px)`. Preserve these final overrides rather than the earlier rules they replace. The hero places text first and the scanner below (top 380px, width 94%). At 1600px minimum the hero height increases to 850px; later base positioning still wins where it has equal specificity.

Use small viewport units for full-height surfaces. Form controls use 16px text on phone. Dialogs constrain their height and scroll internally; the mobile tutorial sits above the bottom edge with side insets.

## Elevation & Depth

This is a hybrid system: workspace panels are mostly flat white with gray borders, while papers, the 3D lens and focused overlays use physical depth. Video is desaturated and shaded to preserve foreground reading. The scene’s steel lens, pale papers and cyan scan line come from the authored Three.js materials, not a general-purpose interface gradient.

### Shadow Vocabulary

- **Paper fan:** `5px 14px 32px #1b27381c` for layered presentation papers.
- **Dark evidence stack:** `5px 20px 45px #0008` for the dark cinematic scene.
- **Record drawer:** `-12px 0 50px #152c481a` for a focused side tool.
- **Finding dialog:** `0 18px 65px #102a4626` for the modal editor.
- **Tutorial:** `0 20px 75px #132b4b3d` for onboarding above the dimmed surface.

**The Evidence Depth Rule.** Reserve pronounced perspective and cast shadows for documents and focused overlays. Keep ordinary workspace panels border-led.

## Shapes

Actions are capsules. Inputs have gently rounded corners; documents and compact rows use smaller rounded rectangles; workspace panels are slightly softer; presentation surfaces and tutorial cards use the broad surface radius. Status badges and evidence tags are compact rounded rectangles rather than pills. Circular motion controls and lens geometry are reserved for their functional presentation roles.

Borders define data groups and fields. Feature media clips inside rounded surfaces; text must remain clear of the scanner and decorative paper edges.

## Components

### Buttons

Confident, quiet pill actions use the normative primary/secondary tokens. The base minimum height is 49px; the small variant is 36px with 10px / 18px padding and 14px text. Hover raises enabled buttons by 2px; active scales to 0.98. Disabled controls use 0.45 opacity and a not-allowed cursor. The focus ring is independent of hover.

### Inputs / Fields

Workspace fields use a dark inset surface and steel border, an inset reading area and a 46px minimum height. Hover darkens the border. The global keyboard focus treatment is a 3px Focus Blue outline with 4px offset. Labels remain visible; placeholder text is supplementary. Textareas resize vertically. Error prose uses the semantic error token.

### Navigation

Landing navigation is restrained inline text and is hidden at the phone breakpoint. The workspace keeps six top tabs with icons, a steel-blue selected surface, pale text and a 2px underline. Tabs scroll horizontally on phone rather than wrapping into a sidebar. The language selector remains available across surfaces.

### Chips / Tags

Workspace state badges use muted steel blue at rest and dark green with light text on completion. Evidence references are small monospaced tags, with wrapping groups and final contrast-corrected text. These convey state and record identity; they are not generic action buttons.

### Cards / Containers

Presentation feature cards use large rounded surfaces and generous padding; the three-column grid is filled by alternating wide/narrow spans. Working panels use graphite and slate, a thin steel border and tighter internal spacing. Tables keep tabular numerals, quieter header cells and a lighter slate row-hover treatment; the explicit inspect control remains keyboard reachable.

### Focused tools

The record drawer is at most 480px wide; the finding editor is at most 560px wide. Outside the guided tutorial both use the implemented FocusDialog behavior: move focus inside, cycle Tab/Shift-Tab, close on Escape or backdrop click, make background work content inert, then restore focus to the invoking control when available. Keep dialog names and visible close controls.

### Evidence dossier, scanner and presentation motion

The scanner uses pale paper, steel metal, dark rings and a restrained cyan scan line; pointer movement gently changes orientation. The sticky inspection scene uses a different, purpose-built evidence dossier: four rounded metal cassettes with inset authored document faces, bevelled edges, screws, contact details and softly reflected studio light. Scroll opens payment, exchange-rate, journal and verified-finding layers; the source is foremost at the start. The hero scanner remains a separate introductory object. Exactly one explanation is mounted; text layers never crossfade over one another. Offscreen rendering work is gated by visibility. The shared landing pause state pauses the marquee, all landing videos and scanner animation. The video-to-invitation join is borderless and full bleed; a long fade dissolves the city into the exact graphite finale ground. Gentle video zoom moves inside its frame rather than scaling the container and exposing white edges. Scroll-linked GSAP sequences remain scroll-driven; the pause control does not claim to disable those sequences.

The five-step tutorial uses four opaque shade rectangles around a transparent target window, a cyan outline and an arrow. Its target remains readable and helper placement adapts to the actual target rectangle. It performs real actions and refreshes the episode on completion; no whole-screen blur.

Reduced motion omits the GSAP presentation setup, starts videos/scanner paused, removes the animated proof layer and compresses CSS animations/transitions to effectively immediate updates. Presentation easing is `cubic-bezier(.16,1,.3,1)`; reveal motion uses GSAP `power3.out`. Ordinary button transitions take 0.22–0.3s; drawer/editor entry takes 0.45s / 0.35s. Exact motion and responsive metadata is carried in the sidecar.

## Do's and Don'ts

### Do:

- Do preserve the final CSS cascade when copying typography and responsive rules.
- Do keep visible focus on interactive controls and restore focus when a focused tool closes.
- Do let workspace tabs and data tables scroll within their own containers on small screens.
- Do connect pause controls to the marquee, videos and scanner and honor reduced motion.
- Do use tabular numerals for budgets, amounts and metrics.

### Don't:

- Don't distribute SF Pro font files.
- Don't place essential instructions inside decorative WebGL or video scenes.
- Don't copy oversized desktop headings into mobile layouts without their overrides.
- Don't use cinematic paper shadows as the default treatment for every work panel.
- Don't turn local evaluation results into an official judging claim.

Extraction evidence: `PRODUCT.md`, `docs/DIRECTION.md`, `web/src/style.css`, `web/src/revision.css`, `web/src/App.jsx`, `web/src/Scanner.jsx`, `Disassembly.jsx`, `EvidenceCore.jsx`, `Finale.jsx` and `Tutorial.jsx`. This document records implementation and does not assert a rendered whole-surface review or an official evaluation score.
