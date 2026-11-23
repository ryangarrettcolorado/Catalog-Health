# Sources and limits

This page says where each part of the kit comes from and how exact it is. All values were read on 23 November 2026.

## Where the values come from

| Part of the kit | Source | How exact |
|---|---|---|
| Product colour ramps in light and dark: sand, sunbeam, pebble, ocean, evergreen, ember, rust, iris, tropic, sakura, moss, alpha and the ten `data-*` chart ramps | The token stylesheet that the app's public sign-in page loads | Exact values, with the source's family names and step numbers |
| Semantic colour tokens such as `bg-primary`, `text-secondary`, `action-primary` | Named for this kit | Each one points at the same ramp step that the source uses for that role. The names are this kit's own |
| Type sizes 12, 13, 15, 20, 24 and 32px, weights 400, 450 and 550, line heights and letter spacing | The same token stylesheet | Exact |
| `figure-hero` at 48 on 56px | A step on the source's size scale | The role is this kit's own |
| Spacing, radius and elevation scales | The same token stylesheet | Exact |
| Control heights 28, 32 and 40px, badge height 20px, table rows 32, 40 and 56px, modal widths | The component stylesheet of the sign-in page | Exact |
| Sidebar width 240px and top bar height 48px | Screenshots in a public product walkthrough that shows an older version of the app | Estimated |
| Brand colours, brand type sizes at 1440px, breakpoints | Computed styles on www.apollo.io | Exact |
| Chart colour order `viz-1` to `viz-8`, sequential and diverging sets | Chosen for this kit from the source's chart ramps | Derived. The order is not Apollo's. A palette validator checked it for colour-blind readers in both themes |
| Components | Written for this kit | Original. They follow the source's sizes and states, and they are not Apollo's components |

## Stand-ins

| What the source uses | What this kit ships | Note |
|---|---|---|
| Inter Variable, the product typeface | Inter Variable, Latin subset | The same family. It is free under the SIL Open Font License |
| Roboto Mono, the product monospace | Roboto Mono, Latin subset | The same family. Free |
| Season Mix, the website headline face | Commissioner Flare | A free flared sans whose weight stops at 460. It is close in tone and it is not the same design |
| ABC Diatype, the website text face | Inter Variable | Named first in the `brand` family, so it appears on a machine that has it |
| Founders Grotesk Mono, the website label face | Roboto Mono | Named first in the `eyebrow` family |
| The app's own icon font | Lucide 0.469.0 at a 1.5px stroke | Close in weight and style. Individual shapes differ |
| The Apollo logo | Nothing | Write the name in plain type |

## Source values that miss a contrast target

The kit keeps these source values exact and flags them here and in each token's note.

- `border-strong`, the outline of fields and secondary buttons, is about 1.2:1 against `bg-primary` in light and 1.4:1 in dark. A control edge should reach 3:1. Every field in this kit has a visible label for that reason.
- `action-primary` is 1.2:1 against `bg-primary` in light. The label and the shape carry the button.
- `text-disabled` is 3.8:1 on `bg-primary` in light. Use it for disabled labels only.
- `viz-warning` is 2.5:1 on `bg-primary` in light. It always carries an icon and a word.

## Where the kit differs from the source on purpose

- **Destructive button on hover.** The source lightens the fill, which drops a white label to 3.0:1. The kit darkens the fill to `rust-60`.
- **AI button on hover.** The source changes the fill to a step where the label is 3.5:1 in dark. The kit changes only the outline.
- **Avatar initials** use the 70 step of each family. The source uses the 60 step, which it applies to icons.
- **Sequential chart scale in dark.** The kit reverses the blue ramp in the dark theme, so that "near zero" fades into the surface in both themes.
- **Text on selected rows in dark.** `text-tertiary` is 4.2:1 on `selected-bg` in dark, so the kit switches meta text to `text-secondary` there.

## What the walkthrough shows

The public product walkthrough that was used for layout shows an older interface, with a blue primary button and an earlier logo. This kit follows the current look that the sign-in page and the website show: sand neutrals, a yellow primary action and Inter. Only the sidebar and top bar proportions come from the walkthrough.
