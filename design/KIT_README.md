This kit styles one candidate case study so that it sits naturally beside Apollo.io's current product and website. It is unofficial. The tokens record what Apollo's public pages show, and the components are original to this kit. It is not Apollo's design system.

## Rules for every output

1. Start every screen, slide and exported image with the **PrototypeBanner**. It says that the work is a prototype with illustrative data and that it is not an Apollo product.
2. Write "Apollo.io" in plain type. Do not place, redraw or imitate the Apollo logo. The brand row of the **AppFrame** shows a product name and a plain `action-primary` square.
3. Do not build sign-in, sign-up, billing or payment screens with this kit, and do not copy real product screens. Build new screens for the case study.
4. Mark invented numbers as illustrative, next to the numbers. Use invented people and companies, and `.example` domains.
5. Sign brand-style pages with the author's name.

## Two modes

**Product mode** is for the working prototype: screens, dashboards, tables and charts. Use the `sans` family, the `ui-*` and `figure-*` type styles, the semantic colour tokens and the components. Start from **AppFrame**.

**Brand mode** is for a cover, a one-page brief or a closing slide. Use the `display`, `brand` and `eyebrow` families, the `brand-*` type styles and the `brand-*` colours. Start from **BrandSheet**. Brand tokens do not change in the dark theme.

Keep the modes apart. Do not put a display headline inside the app, and do not put product controls on a cover.

## Colour

- **Neutral first.** The interface is sand. Use `bg-secondary` for the canvas and `bg-primary` for cards, tables and the sidebar. Use `text-primary`, `text-secondary` and `text-tertiary` for text and `border-default` for outlines. Most of a screen has no hue.
- **Yellow is the action.** `action-primary` fills the one primary button in a view, and its label is `on-action`. Do not use yellow for text, links, borders, status or chart marks. Do not use it to mean "selected".
- **Selection is pebble.** Selected rows, selected cards and active filters use `selected-bg`, `selected-border` and `selected-text`. A selected segment, chip or toggle is dark: `bg-inverse` with `text-inverse`.
- **Links and focus are ocean.** Use `text-link` with an `ocean-30` underline, and `focus-ring` for keyboard focus.
- **Status has three families and always has words.** Evergreen is good, ember needs attention, rust is wrong or destructive. Use the 20 step as a fill with the 70 step as text (`positive-bg` with `text-positive`), and the 50 step for dots and bars (`positive-solid`). Do not rely on colour alone.
- **Iris means that a model did it.** Use `ai-bg`, `text-ai`, `cs-btn--ai` and `cs-badge--ai` only for content that a model wrote, suggested or read.
- **Charts have their own colours.** Series take `viz-1` to `viz-8` in fixed order, and a series keeps its colour when filters change. Use `viz-emphasis` with `viz-other` when one series is the point. Use `viz-seq-1` to `viz-seq-7` for magnitude and the `viz-div-*` set for values around a midpoint. `viz-positive`, `viz-warning` and `viz-error` are reserved for status. Chart text uses text tokens, not a series colour.
- **Alpha tokens make states.** Lay `bg-hover` and `bg-pressed` over the resting surface, so that hover works on any ground.
- **Both themes are complete.** Set `data-theme="dark"` on the root element. Semantic tokens change by themselves, so do not write theme-specific colours in a screen.

## Type

- Product text is Inter Variable (`sans`) at three weights: 400 for text, 450 for labels and titles, 550 for strong emphasis. Do not use 600 or 700 in the product.
- Use `ui-body-sm` (13px) for most interface text, `ui-caption` (12px) for help text and axis labels, and `ui-body-lg` (15px) for reading copy. Titles are `ui-title-sm`, `ui-title-md` and `ui-title-lg`. A page has one `ui-title-lg`.
- Numbers that lead use `figure-lg`, or `figure-hero` once in a view. Big numbers use proportional figures. Columns of numbers use tabular figures (`cs-num`) and align right.
- IDs, domains and field keys use `ui-mono`.
- Write sentence case everywhere in the product. Do not set labels in capitals, do not use title case, and do not end a label with a colon.
- Brand headlines use the `display` family at weight 550 with tight leading (`brand-display-*`). An uppercase `brand-eyebrow` may sit above a brand headline. It does not appear in the product.

## Space, shape and depth

- Spacing runs on 2, 4, 8, 12, 16, 20, 24 and 32px (`space-xxs` to `space-xxxl`). Put controls `space-sm` apart, cards `space-lg` apart and page sections `space-xxl` apart.
- Controls are 32px high (`control-md`), 28px when small and 40px when large. Table rows are 40px by default, with 32px and 56px options.
- `radius-sm` (8px) rounds controls. `radius-md` (12px) rounds cards, modals and badges. `radius-xs` (4px) rounds checkboxes. `radius-full` makes pills, tracks and dots.
- The interface is flat. Cards, tables and fields have a hairline and no shadow. Only floating surfaces cast a shadow: `elevation-2` for menus and chart tooltips, `elevation-5` for modals. In the dark theme a modal takes a `border-default` line in place of its shadow.
- Motion is short and functional: 120ms ease-in-out on colour and border changes, and nothing on page load. Honour `prefers-reduced-motion`.
- Focus is a solid 1px `focus-ring` outline, 1px outside the control.

## Layout

- The app frame is a 240px sidebar (`sidebar-w`), a 48px top bar (`topbar-h`) and a content area with `space-xxl` padding on `bg-secondary`.
- A dashboard reads from top to bottom: the page title, one **FilterBar**, a row of three or four **MetricTile**s, charts in a two-column grid, then the detail **Table**. Content stops at `modal-xl` (1200px).
- Left-align text and right-align numbers. Centre content only in an **EmptyState** and in a **Modal** on its backdrop.

## Voice

Write plain, direct and confident copy in the second person. The public site writes short statements and puts a full stop inside a headline for rhythm, as in "One system. Three layers."

- **Say what it is.** Write "Possible duplicate", not "Entity resolution candidate".
- **Lead with the verb on buttons** and name the object: "Merge records", "Link to parent", "Flag as wrong". Use sentence case and no full stop.
- **Write numbers with compact units:** 238.4M, 12.9K, 91.6%, +0.4 pts. State the period of every change: "vs last week".
- **State limits plainly.** "This segment has 212 records. Treat the figure as a rough guide."
- **Errors say what happened and what to do next.** Do not apologise or blame. Do not use exclamation marks or emoji.
- **Data words:** contact, company, record, field, source, verified, enriched, stale, duplicate, parent, subsidiary. Use one word for one thing across the prototype.

## Data display

- Pick the form before the colour. One number is a **MetricTile**. One ratio is a **Meter**. The parts of one whole are a **SegmentBar**. Change over time is a **LineChart**. Amounts across categories are a **BarChart** or ranked Meters. Two dimensions are a **Heatmap**. More than seven categories are a **Table**.
- Give one chart one y-axis. Do not use pies, donuts, dual axes or dashed gridlines.
- Show a legend for two or more series, and add a direct label for up to four. Give every chart a table view, so that no value is reachable only by hover.
- Send a status colour with an icon or a word. Green and red must not be the only difference between two things.
- Show the denominator and the sample size near any rate. Show the date of the newest data on every dashboard.

## Icons

The app uses its own icon font, which is not in this kit. The kit uses Lucide outline icons at a 1.5px stroke in its place; see the Icons asset group. Draw icons inline at 16px or 20px so that they take the text colour. Do not use emoji or filled icons.

## What is not in this kit

There is no logo, no licensed font and no app icon font. The `display`, `brand` and `eyebrow` families name the site's licensed faces first, so those faces appear on a machine that has them. Everyone else sees the free stand-ins: Commissioner Flare for display, Inter for brand text and Roboto Mono for eyebrows.
