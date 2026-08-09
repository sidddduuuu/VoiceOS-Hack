# World Labs visual reference for LabLoop

Reference: <https://www.worldlabs.ai/?ref=lapaninja>

This is an inspiration brief, not permission to copy World Labs branding, text,
logo, illustrations, source code, or proprietary assets.

## What we are borrowing

- A bright, near-white canvas with unusually generous negative space.
- Editorial serif display type paired with quiet sans-serif interface type.
- A single large, isometric system illustration that explains the product before
  the user reads supporting copy.
- Restrained graphite, cool gray/lilac, and warm metallic accents.
- A calm top navigation followed by a denser, dark product surface.
- Motion that makes a system feel alive without turning the page into a game.

The reference gallery identifies Gilda Display and Roobert. LabLoop will not rely
on those licensed/network fonts. Use an editorial system-serif stack for display
copy and the system UI stack for controls and data.

## LabLoop translation

The original mechanical globe becomes an original lab-process apparatus: sample
vessels, a protocol path, a measurement chamber, a supervisor relay, and an
inventory reservoir. It visualizes the current experiment state; it is not a 3D
viewer and has no drag/orbit interaction.

Physical scene: a researcher with occupied, gloved hands glances at a shared lab
monitor under bright overhead lighting and needs the current state in under two
seconds. This requires a light primary canvas, strong contrast, large state cues,
and a darker live-record section that remains legible from several feet away.

## Visual rules

- Use true/cool near-white, graphite, fog gray, dusty lilac, restrained blue, and
  warm copper. Red is reserved for blocking safety/deviation states.
- Serif is allowed only for the LabLoop wordmark, page thesis, protocol title, and
  major narrative headings. All controls, measurements, timestamps, and labels use
  sans-serif or tabular monospace numerals.
- Prefer open composition, rules, and continuous surfaces over card grids.
- Corners remain modest: 0–16px depending on function; pills are only for compact
  status tags and buttons.
- No gradient text, decorative grids, glass-card stacks, copied globe motifs,
  stock laboratory photography, or generic AI sparkle icons.

## Motion rules

- The apparatus path advances with protocol state; samples and measurement pulses
  move only to communicate real activity.
- Voice listening/processing/complete/error states have distinct waveform motion.
- New records enter with opacity/transform transitions; historical content is
  visible by default and never depends on animation to appear.
- Most transitions last 150–250ms with ease-out-quart/expo curves. Ambient apparatus
  motion may use a slow 8–16 second cycle.
- Animate only transform and opacity. No layout animation, bounce, elastic easing,
  scroll hijacking, custom cursor, WebGL, or required pointer interaction.
- `prefers-reduced-motion: reduce` disables ambient loops and makes state changes
  immediate or cross-faded.

## Responsive rules

- Wide screens: editorial introduction and apparatus share the first viewport;
  the dark live console below uses asymmetric two-column composition.
- Tablet: apparatus remains prominent above or beside current protocol state.
- Mobile: one semantic column, persistent connection state, no horizontal scroll,
  and minimum 44px controls.

## Source notes

The public reference and its gallery snapshot show a white/gray minimal landing
page, serif/sans pairing, a mechanical isometric centerpiece, and a transition to
Marble product content. These observations are sufficient for direction; every
LabLoop asset and component must be original.
