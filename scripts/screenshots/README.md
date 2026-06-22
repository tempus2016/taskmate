# TaskMate screenshot tooling

Visual-verify the Lovelace cards from the sandbox/CI without a local browser.
Local Chrome won't run in the sandbox (missing system libs, no root), so these
drive the **browserless** container over CDP instead.

## Requirements
- A reachable **browserless** instance (default `http://192.168.0.154:3002`, no token).
- The **ha-dev** Home Assistant instance (default `http://192.168.0.154:8124`) with the
  integration installed, and an admin long-lived token at `../../../ha-dev/.ha_token`
  (i.e. `ha-dev/.ha_token` in the workspace).
- `playwright` resolvable by Node. In the sandbox it lives in the npx cache, e.g.
  `export NODE_PATH=$(dirname $(dirname $(npx --no-install playwright --help >/dev/null 2>&1; \
   find ~/.npm/_npx -path '*node_modules/playwright' | head -1)))`
  — or just `find ~/.npm/_npx -path '*node_modules/playwright'` and point `NODE_PATH` at that `node_modules`.

Override defaults with env vars: `CDP`, `HA` (base URL), `HA_TOKEN` (path to token file).

## Scripts

### `shot.js <input.html> <output.png> [width] [height]`
Render a **local static HTML** file (e.g. a wireframe in `docs/design/redesigns/`) and
screenshot it. Reads the file and `setContent`s it (browserless can't read `file://`).

### `check-cards.js`
Instantiate **every** TaskMate card in all three designs (playroom/console/cleanpro)
against ha-dev's live `hass`, capture console errors, and report whether each card's
designed shell (`.tmd`) renders. Fast pass/fail across the whole card set — run this
after any card change.

### `render-cards.js [A|B|C|D]`
Montage a batch of cards, each as a row of the 3 designs, into `montage-<batch>.png`.
Uses live ha-dev data; batch `D` augments `hass` with synthetic rewards/bonuses/
penalties/pending-approvals (on the companion sensors `sensor.taskmate_rewards` /
`_incentives` / `pending_approvals`, which the attr-resolver merges) so the data-less
cards render populated.

## How the real-card render works
The cards need HA's Lit base + the frontend, so the scripts: auth the frontend via
`localStorage.hassTokens` (from the long-lived token) → load ha-dev → inject the real
`/taskmate/*.js` modules (cache-busted) so they register against the live Lit base →
grab `document.querySelector('home-assistant').hass` → instantiate cards with
`setConfig({…, card_design})` + `el.hass`. No dashboards are modified.

Design tokens live in each card's **shadow** via `:host([data-tm-design])` (a document
stylesheet can't reach a card nested in HA's shadow DOM) — see `taskmate-design.js`.
