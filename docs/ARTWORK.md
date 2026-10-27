# Artwork

The current banner shows the vampire secretly typing at his CRT while the hunter sneaks up behind him. The built-in imagegen tool edited the original banner, preserving the surrounding scene, typography, and HUD.

`preview.png` is original promotional art generated with the built-in imagegen tool. The README and marketplace use the same asset.

`docs/omarchy-watching.png` is an unedited screenshot of the live Omarchy/Hyprland VNC test, showing the monochrome icon and its operational tooltip. The desktop wallpaper belongs to the installed Omarchy theme.

The bar uses the hand-authored 16-pixel glyphs in `PixelVampire.qml`, monochrome by default. `colorIcons` is an optional Omarchy widget setting. No animations or idle redraw timer run.

Visual references reviewed from the Omarchy marketplace: Navbar Cat's pixel sprite card, Sky Map's dark illustrated panel, and Top 5 Apps Bar's compact screenshot. These informed the layout and presentation. See [the marketplace](https://plugins.omarchy.org/) and its [development guide](https://plugins.omarchy.org/develop.html).

## Initial generation prompt

```text
Use case: ads-marketing.
Asset type: wide GitHub README hero and Omarchy plugin marketplace preview, landscape 1536x1024.
Primary request: Original crisp pixel-art vampire game promotional graphic for a Linux desktop utility named Vampire Slayer. Looks like an evocative polished 16-bit gothic videogame title screen, with deliberate visible square pixels, restricted dark midnight purple, bone-white, crimson and amber palette. Castle battlements, moon, bats; a charismatic small caped vampire hunter with a wooden stake faces a comically sleepy fanged vampire beside an old CRT showing a simple CPU meter. Charming rather than gory. Strong readable hierarchy, generous margins, art and typography integrated into the pixel world.
Exact headline in huge elegant pixel lettering: "VAMPIRE SLAYER"
Exact subtitle beneath: "BACKGROUND BROWSER & APP IDLE SUSPEND"
Near bottom three understated pixel HUD mode labels with icons: "WATCHING"  "GAMING"  "SUSPENDED".
Footer exact text: "Brought to you by dagelf".
No additional words, no fake metrics or claims, no existing game branding, no browser logos, no glossy 3D, no photo, no blur. Keep all text and key characters inside generous safe margins. This is promotional artwork, not a screenshot.
```

## Vampire-at-work edit prompt

```text
Use case: precise-object-edit.
Edit the provided Vampire Slayer pixel-art promotional banner. Make only this narrative change in the lower character scene: the fanged vampire on the right is AWAKE and secretly working at the existing CRT computer, leaning forward from his red chair toward the desk, his hands visibly typing on its keyboard, a sly absorbed expression, unaware of the hunter approaching from behind on the left. Remove the floating Z sleep symbols and repair only their immediate background. The left protagonist is sneaking up on him; preserve the protagonist's existing crouched stealth pose, clothes, stake, location and size as closely as possible.
Preserve everything else: exact 1536x1024 composition and crop, crisp pixel art style and pixel scale, palette, lighting, castle, moon, bats, banners, candles, furniture, cat, wine, computer screen CPU graphic, all borders and HUD icons.
Preserve every letter, word, font shape and placement of all existing text exactly: VAMPIRE SLAYER, BACKGROUND BROWSER & APP IDLE SUSPEND, WATCHING, GAMING, SUSPENDED, Brought to you by dagelf. Do not add words, labels, speech bubbles or any new props beyond what is needed for the vampire to use the existing keyboard. Do not redesign, recolor, zoom, or recompose the banner.
```
