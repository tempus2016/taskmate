/**
 * A tiny renderer for the TaskMate cards.
 *
 * The cards are LitElement classes that only ever run inside Home Assistant,
 * which has kept them out of CI: a bug that hides a button or wires it to the
 * wrong handler still passes ESLint and the Python suite. This harness loads a
 * card's real source in a `vm` sandbox, swaps Lit's `html` tag for a serializer
 * that keeps the template structure, and renders a chosen method so a test can
 * assert on the markup and press the buttons it produced.
 *
 * It is deliberately not a DOM: no browser, no jsdom, no build step. What it
 * gives you is the template a card would have handed to Lit, plus the handlers
 * bound to it.
 */

const { readFileSync } = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const WWW = path.join(__dirname, "../../custom_components/taskmate/www");

const localeMessages = (() => {
  let cached = null;
  return () => (cached ??= JSON.parse(readFileSync(path.join(WWW, "locales/en.json"), "utf8")));
})();

/** Resolve an en.json key the way the real localize helper does. */
function localize(key, params = {}) {
  const template = localeMessages()[key];
  if (template === undefined) return key;
  return String(template).replace(/\{(\w+)\}/g, (_, name) => (params[name] ?? ""));
}

/**
 * Stand-in for Lit's `html`/`css` tags.
 *
 * Values are kept unflattened so `render()` can tell a nested template from a
 * plain string, and an event handler from text.
 */
function template(strings, ...values) {
  return { __tmTemplate: true, strings, values };
}

/**
 * Flatten a captured template into markup, collecting event handlers as it goes.
 *
 * Handlers become `event_<n>` placeholders in the markup so a control can be
 * matched back to the function Lit would have bound to it.
 */
function serialize(value, handlers) {
  // Lit renders `null`/`undefined` as nothing and every other primitive via
  // String(), booleans included — `?disabled="${false}"` must stay falsy.
  if (value == null) return "";
  if (Array.isArray(value)) return value.map((item) => serialize(item, handlers)).join("");
  if (typeof value === "function") return `event_${handlers.push(value) - 1}`;
  if (value.__tmTemplate) {
    return value.strings.reduce(
      (out, part, i) => out + part + (i < value.values.length ? serialize(value.values[i], handlers) : ""),
      "",
    );
  }
  return String(value);
}

const ATTR_DISABLED = /\?disabled\s*=\s*["']?true\b/;
const ATTR_DISABLED_BARE = /(?:^|\s)disabled(?:[\s>=]|$)/;

/** Find the markup of an element that starts at `openEnd`, honouring nesting. */
function innerContent(markup, tag, openEnd) {
  const scan = new RegExp(`<${tag}\\b[^>]*>|</${tag}\\s*>`, "g");
  scan.lastIndex = openEnd;
  let depth = 1;
  let match;
  while ((match = scan.exec(markup)) !== null) {
    depth += match[0].startsWith("</") ? -1 : 1;
    if (depth === 0) return markup.slice(openEnd, match.index);
  }
  return markup.slice(openEnd);
}

/**
 * Render a captured template.
 *
 * Returns the markup plus every clickable control in document order. Controls
 * expose the attributes Lit would have set, their text, and `click()` — which
 * refuses to fire on a disabled control, exactly as a browser would.
 */
function render(tree) {
  const handlers = [];
  const markup = serialize(tree, handlers);

  const controls = [];
  const opening = /<([a-z][\w-]*)\b([^>]*)>/g;
  let match;
  while ((match = opening.exec(markup)) !== null) {
    const [, tag, attrs] = match;
    const handler = attrs.match(/@click\s*=\s*["']?event_(\d+)/);
    if (!handler) continue;
    const disabled = ATTR_DISABLED.test(attrs) || ATTR_DISABLED_BARE.test(attrs);
    const content = innerContent(markup, tag, opening.lastIndex);
    const attr = (name) => {
      const found = attrs.match(new RegExp(`(?:^|\\s)\\.?${name}=["']([^"']*)["']`));
      return found ? found[1] : null;
    };
    controls.push({
      tag,
      attrs,
      content,
      disabled,
      attr,
      text: content.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim(),
      async click(event = {}) {
        if (disabled) throw new Error(`Refused to click a disabled <${tag}>`);
        return handlers[Number(handler[1])]({ stopPropagation() {}, preventDefault() {}, ...event });
      },
    });
  }

  return {
    markup,
    controls,
    /** First control whose markup contains `needle` (string or RegExp). */
    control: (needle) =>
      controls.find((c) =>
        needle instanceof RegExp ? needle.test(c.tag + c.attrs + c.content) : (c.tag + c.attrs + c.content).includes(needle),
      ),
    /** Every occurrence of a capture group, in order. */
    all: (pattern) => Array.from(markup.matchAll(pattern), (m) => (m.length > 1 ? m.slice(1) : m[0])),
  };
}

/**
 * Evaluate a card's source in a sandbox and hand back its custom elements.
 *
 * `overrides.window` is merged over the default TaskMate frontend helpers, so a
 * test can decide whether the viewer is a parent, what the design layer says,
 * or which entity attributes the resolver returns.
 */
function loadCard(filename, overrides = {}) {
  const elements = new Map();

  class LitElement {
    constructor() {
      this.style = { setProperty() {}, removeProperty() {} };
      this.dispatched = [];
    }
    requestUpdate() {}
    dispatchEvent(event) {
      this.dispatched.push(event);
      return true;
    }
    connectedCallback() {}
    disconnectedCallback() {}
  }
  LitElement.prototype.html = template;
  LitElement.prototype.css = template;

  // The cards reach their Lit base through a stock HA element's prototype.
  class HuiView extends LitElement {}
  elements.set("hui-masonry-view", HuiView);
  elements.set("hui-view", HuiView);

  const sandboxWindow = {
    __taskmate_localize: (_hass, key, params) => localize(key, params),
    __taskmate_attrs: (hass, entityId) => hass?.states?.[entityId]?.attributes || {},
    __taskmate_is_parent: () => true,
    __taskmate_design: {
      apply: (_card, _hass, config) => config?.card_design || "classic",
      styles: () => null,
      editorOptions: () => [],
    },
    __taskmate_chore_visual: (chore) => (chore?.icon ? { kind: "icon", icon: chore.icon } : { kind: "none" }),
    matchMedia: () => ({ matches: false, addEventListener() {}, removeEventListener() {} }),
    addEventListener() {},
    removeEventListener() {},
    ...overrides.window,
  };

  const sandbox = {
    window: sandboxWindow,
    // The admin panel is a plain custom element rather than a Lit card.
    HTMLElement: class {
      constructor() {
        this.shadowRoot = null;
      }
      attachShadow() {
        this.shadowRoot = { innerHTML: "", querySelector: () => null, querySelectorAll: () => [] };
        return this.shadowRoot;
      }
      addEventListener() {}
      removeEventListener() {}
      setAttribute() {}
      getAttribute() {
        return null;
      }
    },
    URL,
    document: {
      createElement: () => ({ style: {}, setAttribute() {}, appendChild() {} }),
      querySelector: () => null,
      querySelectorAll: () => [],
      addEventListener() {},
      head: { appendChild() {} },
    },
    customElements: {
      get: (name) => elements.get(name),
      define: (name, element) => elements.set(name, element),
    },
    console: { info() {}, warn() {}, error() {}, log() {}, debug() {} },
    URLSearchParams,
    setTimeout,
    clearTimeout,
    setInterval,
    clearInterval,
    requestAnimationFrame: (fn) => setTimeout(fn, 0),
    Intl,
    ...overrides.sandbox,
  };
  sandbox.globalThis = sandbox;
  sandboxWindow.customElements ??= sandbox.customElements;
  sandboxWindow.document ??= sandbox.document;

  // `import.meta.url` is how the panel reads its cache-busting version. It is
  // module syntax, which a plain script context cannot parse, so it is given a
  // stand-in URL of the same shape.
  const source = readFileSync(path.join(WWW, filename), "utf8").replaceAll(
    "import.meta.url",
    JSON.stringify(`http://localhost/${filename}?v=test`),
  );
  vm.runInNewContext(source, sandbox);
  return { elements, window: sandboxWindow, get: (name) => elements.get(name) };
}

module.exports = { loadCard, render, template, localize, WWW };
