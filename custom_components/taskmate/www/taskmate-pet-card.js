/**
 * TaskMate Pet Card
 *
 * A child's virtual pet. It hatches from an egg and grows up through baby,
 * little, big and fully grown as the child does chores (growth and the
 * numbers are the parents' settings). After that, whatever the parents
 * switched on: its home fills up, it turns legendary gold, it lays an egg the
 * child hatches into the next pet (earlier pets stay in the pet family row),
 * and it gains pet levels. It bounces on days with a chore, gets sleepy after
 * a missed day, wears accessories unlocked by the child's level, and plays a
 * short "evolving" moment the first time this device sees it grow. Before
 * adoption the card is the adoption form: pick a creature, give it a name.
 *
 * Reads `pet` from the child's entry in the overview sensor's `children`
 * (present only while pets are switched on in the admin panel). Single
 * layout consuming the design tokens, like the bounty card; layout classes
 * carry a pt- prefix.
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

const _safeColor = (c, d) => (typeof c === "string" && /^#[0-9a-fA-F]{3,8}$/.test(c) ? c : d);
const DEFAULT_ACCENT = "#16a085";
const SPECIES_IDS = ["dragon", "cat", "dog", "bunny", "dino", "unicorn"];
const ACC_ICON = { bow: "🎀", top_hat: "🎩", scarf: "🧣", crown: "👑" };

/**
 * TaskMate pet art: one SVG per species and stage, drawn from shapes so it
 * needs no image files and works offline.
 *
 * Every creature sits facing the child on a 200×200 canvas with its feet on
 * y=186. Growing up is mostly proportion, the way real young animals change:
 * a baby is all head and eyes on stubby legs; each stage after that has a
 * longer body, a relatively smaller head and smaller eyes, and gains the
 * features that make the change obvious (wings and horns, a long horn and a
 * rainbow mane, a collar, long ears).
 *
 * petArt(species, stage) returns an SVG string built only from the fixed
 * tables below, never from user text. petAnchors() says where a hat and a
 * scarf sit, so accessories follow the head as it grows.
 */

const PET_STAGE_ORDER = ["egg", "baby", "kid", "teen", "grown"];

const PET_PALETTES = {
  dragon:  { body: "#3fb58a", shade: "#2f9473", belly: "#f6e27a", accent: "#2e8f8c", line: "#1d5a4b", extra: "#ffb547", cheek: "#ff9d8a" },
  cat:     { body: "#f39b3d", shade: "#d9761f", belly: "#ffe6c7", accent: "#d9761f", line: "#7a3e12", extra: "#ff8fa3", cheek: "#ff9d8a" },
  dog:     { body: "#c98b5a", shade: "#a96e43", belly: "#f6dfc4", accent: "#6f4126", line: "#4a2a17", extra: "#e2463f", cheek: "#ff9d8a" },
  bunny:   { body: "#d6cdee", shade: "#b8acd9", belly: "#fbf8ff", accent: "#f7a8c4", line: "#56478a", extra: "#ffffff", cheek: "#ff9dbb" },
  dino:    { body: "#4c9be8", shade: "#3a7fc6", belly: "#d3e9ff", accent: "#f5b841", line: "#1f4e86", extra: "#f5b841", cheek: "#ff9d8a" },
  unicorn: { body: "#fff6fb", shade: "#efdcea", belly: "#ffffff", accent: "#f2c14e", line: "#7a6a9a", extra: "#c9a2e8", cheek: "#ffa6c9" },
};

const RAINBOW = ["#ff6b6b", "#ffb347", "#ffe066", "#6fdc8c", "#5cc8ff", "#a78bfa"];

// Proportions per stage (baby, kid, teen, grown).
const PET_GEOMETRY = [
  { headR: 37, bodyRx: 29, bodyRy: 23, legH: 3, eyeR: 9.5, eyeGap: 15 },
  { headR: 35, bodyRx: 33, bodyRy: 29, legH: 8, eyeR: 8.2, eyeGap: 15 },
  { headR: 32, bodyRx: 37, bodyRy: 35, legH: 13, eyeR: 7, eyeGap: 14 },
  { headR: 30, bodyRx: 41, bodyRy: 41, legH: 17, eyeR: 6.2, eyeGap: 13 },
];

const GROUND = 186;

function petLayout(stage) {
  const k = Math.max(0, PET_STAGE_ORDER.indexOf(stage) - 1);
  const g = PET_GEOMETRY[k];
  const bodyCy = GROUND - 6 - g.legH - g.bodyRy;
  const bodyTop = bodyCy - g.bodyRy;
  const headCy = bodyTop - g.headR * 0.42;
  return { k, ...g, cx: 100, bodyCy, bodyTop, headCy, headTop: headCy - g.headR };
}

/** Where a hat sits (top of the head) and a scarf (the neck), in canvas units. */
function petAnchors(species, stage) {
  if (stage === "egg") return { head: { x: 100, y: 62 }, neck: { x: 100, y: 150 } };
  const L = petLayout(stage);
  // The unicorn's horn takes the top of its head, so its hat sits to one side.
  const hx = species === "unicorn" && L.k >= 1 ? 100 - L.headR * 0.62 : 100;
  return { head: { x: f(hx), y: L.headTop + (hx === 100 ? 4 : 10) }, neck: { x: 100, y: L.headCy + L.headR * 1.08 } };
}

const f = (n) => Math.round(n * 10) / 10;

// The egg is drawn without a <clipPath>: on iOS 15 Safari a clip inside the
// wobbling .tm-pet group froze the whole page (#1113). The spots all sit well
// inside the shell, and the shading is a crescent cut to the egg's edge.
function egg(species) {
  const p = PET_PALETTES[species];
  const spots = {
    dragon: `<path d="M70 120 q8 -10 16 0 q8 -10 16 0 q8 -10 16 0 q8 -10 16 0" fill="none" stroke="${p.belly}" stroke-width="7" stroke-linecap="round"/>`,
    cat: `<path d="M64 100 q10 6 20 0 M116 100 q10 6 20 0 M72 140 q14 8 28 0 q14 8 28 0" fill="none" stroke="${p.accent}" stroke-width="7" stroke-linecap="round"/>`,
    dog: `<ellipse cx="80" cy="112" rx="13" ry="16" fill="${p.accent}"/><ellipse cx="124" cy="146" rx="10" ry="8" fill="${p.accent}"/>`,
    bunny: `<circle cx="80" cy="108" r="7" fill="${p.accent}"/><circle cx="118" cy="96" r="5" fill="${p.accent}"/><circle cx="112" cy="140" r="8" fill="${p.accent}"/><circle cx="84" cy="150" r="5" fill="${p.accent}"/>`,
    dino: `<path d="M70 96 l8 -10 l8 10 M96 90 l8 -10 l8 10 M122 96 l8 -10 l8 10" fill="${p.accent}" stroke="${p.accent}" stroke-width="4" stroke-linejoin="round"/><circle cx="90" cy="140" r="8" fill="${p.shade}"/><circle cx="118" cy="128" r="6" fill="${p.shade}"/>`,
    unicorn: RAINBOW.map((c, i) => `<path d="M${62 + i * 3} ${118 + i * 7} q38 -18 ${76 - i * 6} 0" fill="none" stroke="${c}" stroke-width="5" stroke-linecap="round"/>`).join(""),
  }[species];
  return `
    <ellipse cx="100" cy="188" rx="46" ry="7" fill="#000" opacity=".12"/>
    <path d="M100 46 C140 46 152 112 152 136 C152 166 128 186 100 186 C72 186 48 166 48 136 C48 112 60 46 100 46Z" fill="${p.body}"/>
    ${spots}
    <path d="M149.7 113.1 C151.3 122.1 152 130.3 152 136 C152 164.3 130.7 183.7 104.8 185.8 A40 44 0 0 1 149.7 113.1Z" fill="${p.shade}" opacity=".35"/>
    <ellipse cx="80" cy="84" rx="9" ry="15" fill="#fff" opacity=".55" transform="rotate(-20 80 84)"/>
    <path d="M100 46 C140 46 152 112 152 136 C152 166 128 186 100 186 C72 186 48 166 48 136 C48 112 60 46 100 46Z" fill="none" stroke="${p.line}" stroke-width="5"/>`;
}

function eyes(L, p, species) {
  const y = L.headCy + L.headR * 0.08;
  const r = L.eyeR;
  const ry = species === "cat" && L.k >= 2 ? r * 1.15 : r * 1.12;
  const one = (x) => `
    <ellipse cx="${f(x)}" cy="${f(y)}" rx="${f(r)}" ry="${f(ry)}" fill="#2b2140"/>
    <circle cx="${f(x + r * 0.32)}" cy="${f(y - r * 0.38)}" r="${f(r * 0.36)}" fill="#fff"/>
    <circle cx="${f(x - r * 0.35)}" cy="${f(y + r * 0.4)}" r="${f(r * 0.16)}" fill="#fff" opacity=".9"/>`;
  return one(L.cx - L.eyeGap) + one(L.cx + L.eyeGap);
}

function cheeks(L, p) {
  const y = L.headCy + L.headR * 0.38;
  const dx = L.eyeGap + L.eyeR * 1.3;
  return `<ellipse cx="${f(L.cx - dx)}" cy="${f(y)}" rx="${f(L.eyeR * 0.85)}" ry="${f(L.eyeR * 0.5)}" fill="${p.cheek}" opacity=".7"/>
          <ellipse cx="${f(L.cx + dx)}" cy="${f(y)}" rx="${f(L.eyeR * 0.85)}" ry="${f(L.eyeR * 0.5)}" fill="${p.cheek}" opacity=".7"/>`;
}

function smile(x, y, w, line) {
  return `<path d="M${f(x - w)} ${f(y)} q${f(w / 2)} ${f(w * 0.7)} ${f(w)} 0 q${f(w / 2)} ${f(w * 0.7)} ${f(w)} 0" fill="none" stroke="${line}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>`;
}

/* ── species parts: behind the body, on the body, on the head ───────── */

function tail(species, L, p) {
  const x = L.cx + L.bodyRx * 0.7;
  const y = L.bodyCy + L.bodyRy * 0.55;
  const len = 18 + L.k * 12;
  const sw = 10 + L.k * 2;
  switch (species) {
    case "dragon": {
      const ex = x - 6 + len + 8;
      const ey = y + 6 - len * 0.9;
      const tip = L.k >= 2
        ? `<path d="M${f(ex - 9)} ${f(ey + 2)} L${f(ex + 4)} ${f(ey - 14)} L${f(ex + 9)} ${f(ey + 5)} Z" fill="${p.accent}" stroke="${p.line}" stroke-width="3" stroke-linejoin="round"/>`
        : "";
      return `<path d="M${f(x - 6)} ${f(y + 6)} q${f(len * 0.9)} ${f(len * 0.2)} ${f(len + 8)} ${f(-len * 0.9)}" fill="none" stroke="${p.line}" stroke-width="${sw + 6}" stroke-linecap="round"/>
              <path d="M${f(x - 6)} ${f(y + 6)} q${f(len * 0.9)} ${f(len * 0.2)} ${f(len + 8)} ${f(-len * 0.9)}" fill="none" stroke="${p.body}" stroke-width="${sw}" stroke-linecap="round"/>${tip}`;
    }
    case "cat": {
      const l = 22 + L.k * 14;
      return `<path d="M${f(x - 4)} ${f(y + 8)} q${f(l * 0.9)} 0 ${f(l * 0.7)} ${f(-l)} q-2 -10 8 -12" fill="none" stroke="${p.line}" stroke-width="${sw + 2}" stroke-linecap="round"/>
              <path d="M${f(x - 4)} ${f(y + 8)} q${f(l * 0.9)} 0 ${f(l * 0.7)} ${f(-l)} q-2 -10 8 -12" fill="none" stroke="${p.body}" stroke-width="${sw - 4}" stroke-linecap="round"/>`;
    }
    case "dog": {
      const l = 14 + L.k * 7;
      return `<path d="M${f(x - 4)} ${f(y)} q${f(l)} ${f(-4)} ${f(l * 1.1)} ${f(-l * 1.2)}" fill="none" stroke="${p.line}" stroke-width="${sw}" stroke-linecap="round"/>
              <path d="M${f(x - 4)} ${f(y)} q${f(l)} ${f(-4)} ${f(l * 1.1)} ${f(-l * 1.2)}" fill="none" stroke="${p.body}" stroke-width="${sw - 6}" stroke-linecap="round"/>`;
    }
    case "bunny": {
      const r = 9 + L.k * 1.5;
      return `<circle cx="${f(x + 4)}" cy="${f(y + 4)}" r="${f(r)}" fill="${p.extra}" stroke="${p.line}" stroke-width="3.5"/>`;
    }
    case "dino": {
      const l = 26 + L.k * 16;
      return `<path d="M${f(x - 10)} ${f(y - 8)} Q${f(x + l * 0.6)} ${f(y - 2)} ${f(x + l)} ${f(y + 14)} Q${f(x + l * 0.4)} ${f(y + 22)} ${f(x - 10)} ${f(y + 18)} Z" fill="${p.body}" stroke="${p.line}" stroke-width="3.5" stroke-linejoin="round"/>`;
    }
    case "unicorn": {
      if (L.k === 0) return `<path d="M${f(x)} ${f(y)} q12 2 16 -10" fill="none" stroke="${p.extra}" stroke-width="8" stroke-linecap="round"/>`;
      const n = L.k >= 3 ? 6 : L.k >= 2 ? 4 : 2;
      const colors = L.k >= 3 ? RAINBOW : [p.extra, "#f6b3d6", p.extra, "#f6b3d6"];
      return colors.slice(0, n).map((c, i) =>
        `<path d="M${f(x - 4)} ${f(y - 4 + i * 2.5)} q${f(18 + L.k * 6)} ${f(-6 + i * 3)} ${f(14 + L.k * 6 + i * 2)} ${f(18 + L.k * 6)}" fill="none" stroke="${c}" stroke-width="5" stroke-linecap="round"/>`).join("");
    }
  }
  return "";
}

function wings(L, p) {
  if (L.k === 0) return "";
  const s = [0, 0.45, 0.8, 1.15][L.k];
  const y = L.bodyTop + 2;
  const one = (dir) => {
    const x = L.cx + dir * (L.bodyRx * 0.55);
    const w = 46 * s;
    const h = 40 * s;
    return `<path d="M${f(x)} ${f(y + 8)} L${f(x + dir * w)} ${f(y - h)} Q${f(x + dir * w * 0.9)} ${f(y - h * 0.2)} ${f(x + dir * w * 1.02)} ${f(y + h * 0.15)} Q${f(x + dir * w * 0.62)} ${f(y - h * 0.05)} ${f(x + dir * w * 0.62)} ${f(y + h * 0.42)} Q${f(x + dir * w * 0.3)} ${f(y + h * 0.15)} ${f(x)} ${f(y + 24)} Z" fill="${p.accent}" stroke="${p.line}" stroke-width="3.5" stroke-linejoin="round"/>`;
  };
  return one(-1) + one(1);
}

// Dino plates: a crest over the head that grows from one nub to a full row.
function dinoCrest(L, p) {
  if (L.k === 0) return "";
  const n = L.k + 1;
  let out = "";
  for (let i = 0; i < n; i += 1) {
    const a = n === 1 ? 0 : -0.55 + (1.1 * i) / (n - 1);
    const mid = 1 - Math.abs(a) / 0.9;
    const size = (6 + L.k * 3) * (0.75 + 0.35 * mid);
    const bx = L.cx + Math.sin(a) * L.headR * 0.98;
    const by = L.headCy - Math.cos(a) * L.headR * 0.94;
    const tx = bx + Math.sin(a) * size * 1.2;
    const ty = by - Math.cos(a) * size * 1.2;
    const nx = Math.cos(a) * size * 0.7;
    const ny = Math.sin(a) * size * 0.7;
    out += `<path d="M${f(bx - nx)} ${f(by - ny)} L${f(tx)} ${f(ty)} L${f(bx + nx)} ${f(by + ny)} Z" fill="${p.accent}" stroke="${p.line}" stroke-width="3" stroke-linejoin="round"/>`;
  }
  return out;
}

function backSpikes(species, L, p) {
  if (species !== "dino" || L.k < 2) return "";
  const x0 = L.cx + L.bodyRx * 0.7;
  const y0 = L.bodyCy + L.bodyRy * 0.55 - 8;
  const len = 26 + L.k * 16;
  let out = "";
  for (let i = 1; i <= L.k; i += 1) {
    const t = i / (L.k + 1);
    const x = x0 + len * t;
    const y = y0 + 4 * t + 14 * t * t - 2;
    const size = 9 - i * 1.5;
    out += `<path d="M${f(x - size)} ${f(y + 3)} L${f(x)} ${f(y - size * 1.3)} L${f(x + size)} ${f(y + 3)} Z" fill="${p.accent}" stroke="${p.line}" stroke-width="2.5" stroke-linejoin="round"/>`;
  }
  return out;
}

function body(species, L, p) {
  const { cx, bodyCy, bodyRx, bodyRy } = L;
  const footY = GROUND - 7;
  const footRx = 11 + L.k * 2 + (species === "bunny" ? 4 : 0);
  const footColor = species === "unicorn" ? "#b9a6cf" : p.shade;
  const legs = L.legH > 4
    ? [-1, 1].map((d) => `<rect x="${f(cx + d * bodyRx * 0.45 - 8)}" y="${f(bodyCy + bodyRy * 0.5)}" width="16" height="${f(footY - bodyCy - bodyRy * 0.5)}" rx="8" fill="${p.body}" stroke="${p.line}" stroke-width="3.5"/>`).join("")
    : "";
  const feet = [-1, 1].map((d) => `<ellipse cx="${f(cx + d * bodyRx * 0.45)}" cy="${f(footY)}" rx="${f(footRx)}" ry="7.5" fill="${footColor}" stroke="${p.line}" stroke-width="3.5"/>`).join("");
  const bellyRx = bodyRx * 0.62;
  const bellyRy = bodyRy * 0.68;
  let bellyMarks = "";
  if (species === "dragon" || species === "dino") {
    for (let i = 1; i <= 2 + L.k; i += 1) {
      const y = bodyCy + bodyRy * 0.12 - bellyRy + (i * 2 * bellyRy) / (3 + L.k);
      const half = bellyRx * Math.sqrt(Math.max(0, 1 - ((y - bodyCy - bodyRy * 0.12) / bellyRy) ** 2)) * 0.82;
      bellyMarks += `<path d="M${f(cx - half)} ${f(y)} q${f(half)} 4 ${f(half * 2)} 0" fill="none" stroke="${p.shade}" stroke-width="2.5" stroke-linecap="round" opacity=".55"/>`;
    }
  }
  let stripes = "";
  if (species === "cat" && L.k >= 1) {
    stripes = [-1, 1].map((d) => `<path d="M${f(cx + d * bodyRx * 0.98)} ${f(bodyCy - 6)} q${f(-d * 9)} 3 ${f(-d * 13)} 10 M${f(cx + d * bodyRx * 0.92)} ${f(bodyCy + 10)} q${f(-d * 8)} 3 ${f(-d * 11)} 9" fill="none" stroke="${p.accent}" stroke-width="4" stroke-linecap="round"/>`).join("");
  }
  const arms = [-1, 1].map((d) => `<ellipse cx="${f(cx + d * bodyRx * 0.62)}" cy="${f(bodyCy + bodyRy * 0.15)}" rx="7.5" ry="${f(9 + L.k * 1.5)}" fill="${p.body}" stroke="${p.line}" stroke-width="3.5" transform="rotate(${-d * 14} ${f(cx + d * bodyRx * 0.62)} ${f(bodyCy + bodyRy * 0.15)})"/>`).join("");
  return `${legs}
    <ellipse cx="${cx}" cy="${f(bodyCy)}" rx="${f(bodyRx)}" ry="${f(bodyRy)}" fill="${p.body}" stroke="${p.line}" stroke-width="4"/>
    <ellipse cx="${cx}" cy="${f(bodyCy + bodyRy * 0.12)}" rx="${f(bellyRx)}" ry="${f(bellyRy)}" fill="${p.belly}"/>
    ${bellyMarks}${stripes}${feet}${arms}`;
}

function collar(species, L, p) {
  if (species !== "dog" || L.k < 2) return "";
  const y = L.bodyTop + 7;
  const w = L.bodyRx * 0.72;
  return `<path d="M${f(L.cx - w)} ${f(y)} q${f(w)} 12 ${f(w * 2)} 0" fill="none" stroke="${p.extra}" stroke-width="7" stroke-linecap="round"/>
          <circle cx="${L.cx}" cy="${f(y + 11)}" r="6" fill="#ffd166" stroke="${p.line}" stroke-width="2.5"/>`;
}

function earsBack(species, L, p) {
  const { cx, headCy, headR } = L;
  switch (species) {
    case "cat": {
      const h = headR * 0.75;
      return [-1, 1].map((d) => {
        const bx = cx + d * headR * 0.72;
        const by = headCy - headR * 0.45;
        return `<path d="M${f(bx - d * 14)} ${f(by + 6)} L${f(bx + d * 6)} ${f(by - h)} L${f(bx + d * 16)} ${f(by + 10)} Z" fill="${p.body}" stroke="${p.line}" stroke-width="3.5" stroke-linejoin="round"/>
                <path d="M${f(bx - d * 5)} ${f(by + 2)} L${f(bx + d * 5)} ${f(by - h * 0.62)} L${f(bx + d * 10)} ${f(by + 4)} Z" fill="${p.extra}"/>`;
      }).join("");
    }
    case "bunny": {
      const len = [28, 35, 41, 45][L.k];
      return [-1, 1].map((d) => {
        const bx = cx + d * headR * 0.42;
        const by = headCy - headR * 0.7;
        const tilt = d * (L.k === 0 ? 24 : 10);
        return `<g transform="rotate(${tilt} ${f(bx)} ${f(by + 8)})">
                  <ellipse cx="${f(bx)}" cy="${f(by - len / 2 + 6)}" rx="${f(10 + L.k)}" ry="${f(len / 2 + 4)}" fill="${p.body}" stroke="${p.line}" stroke-width="3.5"/>
                  <ellipse cx="${f(bx)}" cy="${f(by - len / 2 + 8)}" rx="${f(5 + L.k * 0.5)}" ry="${f(len / 2 - 4)}" fill="${p.accent}"/>
                </g>`;
      }).join("");
    }
    case "unicorn": {
      return [-1, 1].map((d) => {
        const bx = cx + d * headR * 0.62;
        const by = headCy - headR * 0.62;
        return `<path d="M${f(bx - d * 9)} ${f(by + 6)} Q${f(bx + d * 2)} ${f(by - 22)} ${f(bx + d * 12)} ${f(by + 6)} Z" fill="${p.body}" stroke="${p.line}" stroke-width="3.5" stroke-linejoin="round"/>`;
      }).join("");
    }
    case "dragon": {
      if (L.k === 0) return "";
      const h = [0, 8, 18, 26][L.k];
      return [-1, 1].map((d) => {
        const bx = cx + d * headR * 0.5;
        const by = headCy - headR * 0.78;
        return `<path d="M${f(bx - d * 6)} ${f(by + 6)} Q${f(bx + d * 2)} ${f(by - h)} ${f(bx + d * (6 + h * 0.6))} ${f(by - h * 1.05)} Q${f(bx + d * 6)} ${f(by - h * 0.3)} ${f(bx + d * 8)} ${f(by + 8)} Z" fill="${p.extra}" stroke="${p.line}" stroke-width="3" stroke-linejoin="round"/>`;
      }).join("");
    }
  }
  return "";
}

function head(species, L, p) {
  const { cx, headCy, headR, k } = L;
  let shape = `<circle cx="${cx}" cy="${f(headCy)}" r="${headR}" fill="${p.body}" stroke="${p.line}" stroke-width="4"/>`;
  if (species === "unicorn" || species === "dino") {
    shape = `<ellipse cx="${cx}" cy="${f(headCy)}" rx="${f(headR * 1.02)}" ry="${f(headR * 0.96)}" fill="${p.body}" stroke="${p.line}" stroke-width="4"/>`;
  }
  const mouthY = headCy + headR * 0.5;
  let face = "";
  let top = "";
  let front = "";
  let behind = "";
  switch (species) {
    case "dragon": {
      face = `<ellipse cx="${cx}" cy="${f(mouthY - 2)}" rx="${f(headR * 0.5)}" ry="${f(headR * 0.3)}" fill="${p.belly}" opacity=".9"/>
              <circle cx="${f(cx - 5)}" cy="${f(mouthY - 6)}" r="2" fill="${p.line}"/><circle cx="${f(cx + 5)}" cy="${f(mouthY - 6)}" r="2" fill="${p.line}"/>
              ${smile(cx, mouthY + 1, 6, p.line)}`;
      if (k >= 3) {
        top = [0, 1, 2].map((i) => `<path d="M${f(cx - 8 + i * 8 - 4)} ${f(headCy - headR + 3)} l4 -9 l4 9 z" fill="${p.accent}" stroke="${p.line}" stroke-width="2.5" stroke-linejoin="round"/>`).join("");
      }
      break;
    }
    case "cat": {
      face = `<path d="M${f(cx - 4)} ${f(mouthY - 7)} h8 l-4 5 z" fill="${p.extra}" stroke="${p.line}" stroke-width="2" stroke-linejoin="round"/>
              ${smile(cx, mouthY - 1, 5, p.line)}`;
      if (k >= 1) {
        const w = 10 + k * 4;
        face += [-1, 1].map((d) => `<path d="M${f(cx + d * 12)} ${f(mouthY - 4)} l${f(d * w)} -4 M${f(cx + d * 12)} ${f(mouthY)} l${f(d * w)} 2" stroke="${p.line}" stroke-width="2" stroke-linecap="round" opacity=".75"/>`).join("");
        top = `<path d="M${f(cx - 8)} ${f(headCy - headR + 4)} l3 9 M${cx} ${f(headCy - headR + 1)} v10 M${f(cx + 8)} ${f(headCy - headR + 4)} l-3 9" stroke="${p.accent}" stroke-width="4" stroke-linecap="round"/>`;
      }
      break;
    }
    case "dog": {
      const sw = headR * (0.42 + k * 0.05);
      const sh = headR * (0.3 + k * 0.03);
      face = `<ellipse cx="${cx}" cy="${f(mouthY - 3)}" rx="${f(sw)}" ry="${f(sh)}" fill="${p.belly}"/>
              <ellipse cx="${cx}" cy="${f(mouthY - sh * 0.75)}" rx="6" ry="4.5" fill="${p.line}"/>
              ${smile(cx, mouthY - 1, 6, p.line)}
              ${k >= 1 ? `<path d="M${f(cx - 3)} ${f(mouthY + 3)} q3 9 6 0" fill="${p.extra}" stroke="${p.line}" stroke-width="2"/>` : ""}`;
      if (k >= 1) top = `<ellipse cx="${f(cx + L.eyeGap + 2)}" cy="${f(headCy - 2)}" rx="${f(L.eyeR * 1.7)}" ry="${f(L.eyeR * 1.9)}" fill="${p.accent}" opacity=".55"/>`;
      front = [-1, 1].map((d) => {
        const ex = cx + d * headR * 0.88;
        const ey = headCy - headR * 0.35;
        const len = headR * (0.95 + k * 0.08);
        return `<path d="M${f(ex - d * 6)} ${f(ey - 6)} Q${f(ex + d * 16)} ${f(ey - 4)} ${f(ex + d * 10)} ${f(ey + len)} Q${f(ex)} ${f(ey + len + 6)} ${f(ex - d * 8)} ${f(ey + len * 0.6)} Z" fill="${p.accent}" stroke="${p.line}" stroke-width="3.5" stroke-linejoin="round"/>`;
      }).join("");
      break;
    }
    case "bunny": {
      face = `<ellipse cx="${cx}" cy="${f(mouthY - 7)}" rx="4.5" ry="3.5" fill="${p.accent}" stroke="${p.line}" stroke-width="2"/>
              ${smile(cx, mouthY - 2, 5, p.line)}
              ${k >= 1 ? `<rect x="${f(cx - 4.5)}" y="${f(mouthY + 1)}" width="9" height="${7 + k}" rx="2" fill="#fff" stroke="${p.line}" stroke-width="2"/><path d="M${cx} ${f(mouthY + 1)} v${7 + k}" stroke="${p.line}" stroke-width="1.5"/>` : ""}`;
      break;
    }
    case "dino": {
      face = `<circle cx="${f(cx - 6)}" cy="${f(mouthY - 6)}" r="2" fill="${p.line}"/><circle cx="${f(cx + 6)}" cy="${f(mouthY - 6)}" r="2" fill="${p.line}"/>
              <path d="M${f(cx - headR * 0.42)} ${f(mouthY)} q${f(headR * 0.42)} 10 ${f(headR * 0.84)} 0" fill="none" stroke="${p.line}" stroke-width="3" stroke-linecap="round"/>
              ${k >= 2 ? `<path d="M${f(cx - 8)} ${f(mouthY + 2.5)} l3 5 l3 -4 M${f(cx + 2)} ${f(mouthY + 2.5)} l3 5 l3 -4" fill="#fff" stroke="${p.line}" stroke-width="1.5" stroke-linejoin="round"/>` : ""}
              <circle cx="${f(cx + headR * 0.5)}" cy="${f(headCy - headR * 0.55)}" r="${f(3 + k)}" fill="${p.shade}" opacity=".6"/>
              <circle cx="${f(cx - headR * 0.6)}" cy="${f(headCy - headR * 0.35)}" r="${f(2 + k * 0.8)}" fill="${p.shade}" opacity=".6"/>`;
      break;
    }
    case "unicorn": {
      face = `<ellipse cx="${cx}" cy="${f(mouthY - 2)}" rx="${f(headR * 0.5)}" ry="${f(headR * 0.3)}" fill="#ffe3f0"/>
              <ellipse cx="${f(cx - 6)}" cy="${f(mouthY - 5)}" rx="2" ry="1.5" fill="${p.line}"/><ellipse cx="${f(cx + 6)}" cy="${f(mouthY - 5)}" rx="2" ry="1.5" fill="${p.line}"/>
              ${smile(cx, mouthY + 1, 6, p.line)}`;
      // The horn arrives as a nub and grows into a long gold spiral.
      if (k >= 1) {
        const h = [0, 12, 26, 38][k];
        const w = 6 + k * 1.5;
        const base = headCy - headR + 4;
        top = `<path d="M${f(cx - w)} ${f(base)} L${cx} ${f(base - h)} L${f(cx + w)} ${f(base)} Z" fill="${p.accent}" stroke="${p.line}" stroke-width="3" stroke-linejoin="round"/>`;
        for (let i = 1; i < k + 1; i += 1) {
          const y = base - (h * i) / (k + 1);
          const half = w * (1 - i / (k + 1));
          top += `<path d="M${f(cx - half)} ${f(y + 2)} L${f(cx + half)} ${f(y - 2)}" stroke="${p.line}" stroke-width="2" opacity=".6"/>`;
        }
      }
      // Mane: a forelock on a foal, then a mane flowing behind the head and
      // down the neck that grows longer, rainbow when grown.
      const colors = k >= 3 ? RAINBOW : [p.extra, "#f6b3d6", p.extra, "#f6b3d6"];
      const strands = [2, 3, 4, 6][k];
      for (let i = 0; i < strands; i += 1) {
        const a = 0.15 + i * (1.25 / Math.max(1, strands - 1));
        const sx = cx + Math.sin(a) * headR * 0.7;
        const sy = headCy - Math.cos(a) * headR * 0.7;
        const reach = headR * (0.45 + k * 0.12);
        const drop = 8 + k * 9 + i * 3;
        behind += `<path d="M${f(sx)} ${f(sy)} q${f(reach)} ${f(-2)} ${f(reach * 0.8)} ${f(reach * 0.6 + drop)}" fill="none" stroke="${colors[i % colors.length]}" stroke-width="${8 + k * 1.5}" stroke-linecap="round"/>`;
      }
      // Forelock over the brow, clear of the eyes.
      top += `<path d="M${f(cx - 2)} ${f(headCy - headR + 3)} q${f(-10)} 4 ${f(-12)} ${f(10 + k)}" fill="none" stroke="${colors[0]}" stroke-width="${6 + k}" stroke-linecap="round"/>`;
      break;
    }
  }
  return `${behind}${shape}${top}${front}${eyes(L, p, species)}${cheeks(L, p)}${face}`;
}

// A legendary pet keeps its shape and features but turns gold.
const LEGENDARY_PALETTE = { body: "#f6c445", shade: "#dea024", belly: "#fff3bf", accent: "#ffe07a", line: "#7d5200", extra: "#ff9f1c", cheek: "#ff9d8a" };

function sparkle(x, y, r, color) {
  return `<path d="M${f(x)} ${f(y - r)} Q${f(x + r * 0.18)} ${f(y - r * 0.18)} ${f(x + r)} ${f(y)} Q${f(x + r * 0.18)} ${f(y + r * 0.18)} ${f(x)} ${f(y + r)} Q${f(x - r * 0.18)} ${f(y + r * 0.18)} ${f(x - r)} ${f(y)} Q${f(x - r * 0.18)} ${f(y - r * 0.18)} ${f(x)} ${f(y - r)} Z" fill="${color}"/>`;
}

/** The creature alone on its 200×200 canvas (no <svg> wrapper). */
function petBody(species, stage, legendary = false) {
  const sp = PET_PALETTES[species] ? species : "dragon";
  if (!PET_STAGE_ORDER.includes(stage)) stage = "baby";
  if (stage === "egg") return egg(sp);
  const p = legendary ? { ...LEGENDARY_PALETTE, ...(sp === "unicorn" ? { extra: "#c9a2e8" } : {}) } : PET_PALETTES[sp];
  const L = petLayout(stage);
  const glow = legendary
    ? `<radialGradient id="tm-gold-glow"><stop offset="0" stop-color="#ffe9a3" stop-opacity=".95"/><stop offset="1" stop-color="#ffe9a3" stop-opacity="0"/></radialGradient>
       <ellipse cx="100" cy="${f(L.bodyCy - 10)}" rx="98" ry="92" fill="url(#tm-gold-glow)"/>`
    : "";
  const sparkles = legendary
    ? sparkle(28, 60, 9, "#ffd23f") + sparkle(172, 48, 11, "#ffd23f") + sparkle(178, 128, 7, "#fff1a8") + sparkle(22, 140, 6, "#fff1a8")
    : "";
  return `${glow}
      <ellipse cx="100" cy="188" rx="${f(L.bodyRx + 14)}" ry="6" fill="#000" opacity=".12"/>
      ${sp === "dragon" ? wings(L, p) : ""}
      ${tail(sp, L, p)}
      ${backSpikes(sp, L, p)}
      ${body(sp, L, p)}
      ${collar(sp, L, p)}
      ${earsBack(sp, L, p)}
      ${sp === "dino" ? dinoCrest(L, p) : ""}
      ${head(sp, L, p)}
      ${sparkles}`;
}

function petArt(species, stage, legendary = false) {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" class="tm-pet-art" aria-hidden="true">${petBody(species, stage, legendary)}</svg>`;
}

/* ── the pet's home: items unlocked one by one after fully grown ────── */

const HOME_W = 320;
const HOME_H = 210;
const HOME_GROUND = 192;

function flower(x, y, color) {
  const petals = [0, 72, 144, 216, 288].map((a) => {
    const r = (a * Math.PI) / 180;
    return `<circle cx="${f(x + Math.cos(r) * 5)}" cy="${f(y + Math.sin(r) * 5)}" r="4.2" fill="${color}"/>`;
  }).join("");
  return `<path d="M${x} ${y + 4} v${HOME_GROUND - y}" stroke="#4f9d3a" stroke-width="2.5"/>${petals}<circle cx="${x}" cy="${y}" r="3.4" fill="#ffd23f"/>`;
}

// Each item: [layer, markup]. Layer "back" sits behind the pet, "front" beside it.
const HOME_ITEMS = [
  ["ground", `<path d="M0 ${HOME_GROUND - 4} Q80 ${HOME_GROUND - 10} 160 ${HOME_GROUND - 5} T320 ${HOME_GROUND - 6} V${HOME_H} H0 Z" fill="#8fd16a"/>
              <path d="M18 ${HOME_GROUND - 3} l3 -8 l3 8 M64 ${HOME_GROUND - 6} l3 -8 l3 8 M250 ${HOME_GROUND - 5} l3 -8 l3 8 M296 ${HOME_GROUND - 4} l3 -8 l3 8" stroke="#5fae45" stroke-width="2.5" fill="none" stroke-linecap="round"/>`],
  ["front", `<ellipse cx="44" cy="${HOME_GROUND + 2}" rx="36" ry="11" fill="#e86f8a" stroke="#9c3a52" stroke-width="3"/>
             <ellipse cx="44" cy="${HOME_GROUND - 1}" rx="26" ry="6" fill="#f7a8bb"/>`],
  ["front", flower(14, 168, "#ff7eb6") + flower(86, 174, "#a78bfa") + flower(238, 172, "#ff9f43") + flower(308, 166, "#5cc8ff")],
  ["back", `<rect x="22" y="104" width="14" height="${HOME_GROUND - 104}" rx="5" fill="#9b6a43" stroke="#5e3b22" stroke-width="3"/>
            <circle cx="29" cy="92" r="26" fill="#5fbf6a" stroke="#2f7a3a" stroke-width="3"/><circle cx="12" cy="108" r="16" fill="#5fbf6a" stroke="#2f7a3a" stroke-width="3"/><circle cx="48" cy="106" r="17" fill="#5fbf6a" stroke="#2f7a3a" stroke-width="3"/>
            <circle cx="20" cy="86" r="3.5" fill="#e2463f"/><circle cx="40" cy="100" r="3.5" fill="#e2463f"/>`],
  ["front", `<ellipse cx="276" cy="${HOME_GROUND + 6}" rx="40" ry="10" fill="#5cc8ff" stroke="#2a7fb8" stroke-width="3"/>
             <path d="M256 ${HOME_GROUND + 6} q8 -3 16 0 M280 ${HOME_GROUND + 4} q8 -3 16 0" stroke="#d6f2ff" stroke-width="2.5" fill="none" stroke-linecap="round"/>`],
  ["back", `<path d="M0 150 H320 M0 172 H320" stroke="#c9905f" stroke-width="6"/>` +
            [10, 52, 94, 222, 264, 306].map((x) => `<path d="M${x - 6} ${HOME_GROUND} V144 l6 -8 l6 8 V${HOME_GROUND} Z" fill="#e2b07a" stroke="#9b6a43" stroke-width="2.5" stroke-linejoin="round"/>`).join("")],
  ["sky", `<circle cx="286" cy="36" r="17" fill="#ffd23f"/>` +
           [0, 45, 90, 135, 180, 225, 270, 315].map((a) => {
             const r = (a * Math.PI) / 180;
             return `<path d="M${f(286 + Math.cos(r) * 22)} ${f(36 + Math.sin(r) * 22)} L${f(286 + Math.cos(r) * 29)} ${f(36 + Math.sin(r) * 29)}" stroke="#ffd23f" stroke-width="3.5" stroke-linecap="round"/>`;
           }).join("")],
  ["sky", `<path d="M0 14 Q80 44 160 22 T320 16" fill="none" stroke="#6b5b3e" stroke-width="1.5"/>` +
           [[20, 21], [52, 30], [86, 33], [120, 28], [154, 23], [190, 24], [226, 30], [260, 27], [296, 20]].map(([x, y], i) =>
             `<ellipse cx="${x}" cy="${y + 6}" rx="4" ry="5.5" fill="${RAINBOW[i % RAINBOW.length]}"/>`).join("")],
  ["sky", RAINBOW.map((c, i) => `<path d="M${10 + i * 6} ${HOME_GROUND} A${150 - i * 6} ${130 - i * 6} 0 0 1 ${310 - i * 6} ${HOME_GROUND}" fill="none" stroke="${c}" stroke-width="6" opacity=".45"/>`).join("")],
  ["back", `<rect x="64" y="136" width="42" height="40" fill="#fff4e0" stroke="#9b6a43" stroke-width="3"/>
            <path d="M57 140 L85 112 L113 140 Z" fill="#e86f5a" stroke="#9c3a2a" stroke-width="3" stroke-linejoin="round"/>
            <rect x="78" y="152" width="14" height="24" rx="3" fill="#9b6a43"/><rect x="68" y="144" width="8" height="8" fill="#9fd8ff" stroke="#9b6a43" stroke-width="2"/>`],
];
const HOME_ITEM_COUNT = HOME_ITEMS.length;

const HEAD_ACC = { crown: "👑", top_hat: "🎩" };
const NECK_ACC = { scarf: "🧣", bow: "🎀" };

/**
 * The whole scene: home items unlocked so far, the pet (gold if legendary)
 * with its hat and scarf, and the egg it laid when there is one.
 * opts: { legendary, home (0–10), egg (bool), accessories: [...] }.
 *
 * Returned as stacked layers { back, pet, front, egg } (egg is "" when there
 * is none), each a full-size SVG on the same canvas. The card wraps the pet
 * and egg layers in HTML elements and animates those: old iOS Safari repaints
 * an animated SVG group on the main thread every frame, which froze the page
 * once a pet hatched (#1126); an animated HTML element is moved on the GPU.
 */
function petScene(species, stage, opts = {}) {
  const home = Math.max(0, Math.min(HOME_ITEM_COUNT, Number(opts.home) || 0));
  const items = HOME_ITEMS.slice(0, home);
  const layer = (name) => items.filter(([l]) => l === name).map(([, m]) => m).join("");
  const acc = Array.isArray(opts.accessories) ? opts.accessories : [];
  const headAcc = acc.includes("crown") ? HEAD_ACC.crown : acc.includes("top_hat") ? HEAD_ACC.top_hat : "";
  const neckAcc = acc.includes("scarf") ? NECK_ACC.scarf : acc.includes("bow") ? NECK_ACC.bow : "";
  const a = petAnchors(species, stage);
  const px = (HOME_W - 200) / 2;
  const py = HOME_GROUND - 186;
  const dress = stage === "egg" ? "" : `
      ${neckAcc ? `<text x="${a.neck.x}" y="${a.neck.y + 14}" font-size="22" text-anchor="middle">${neckAcc}</text>` : ""}
      ${headAcc ? `<text x="${a.head.x}" y="${a.head.y + 2}" font-size="${headAcc === HEAD_ACC.crown ? 32 : 38}" text-anchor="middle" transform="rotate(-8 ${a.head.x} ${a.head.y})">${headAcc}</text>` : ""}`;
  const EX = 44;
  const newEgg = opts.egg
    ? `<g><ellipse cx="${EX}" cy="${HOME_GROUND + 1}" rx="18" ry="4" fill="#000" opacity=".14"/>
        <path d="M${EX} ${HOME_GROUND - 40} C${EX + 16} ${HOME_GROUND - 40} ${EX + 20} ${HOME_GROUND - 14} ${EX + 20} ${HOME_GROUND - 10} C${EX + 20} ${HOME_GROUND - 1} ${EX + 10} ${HOME_GROUND + 1} ${EX} ${HOME_GROUND + 1} C${EX - 10} ${HOME_GROUND + 1} ${EX - 20} ${HOME_GROUND - 1} ${EX - 20} ${HOME_GROUND - 10} C${EX - 20} ${HOME_GROUND - 14} ${EX - 16} ${HOME_GROUND - 40} ${EX} ${HOME_GROUND - 40} Z" fill="#fff6e3" stroke="#a07a3c" stroke-width="3"/>
        <circle cx="${EX - 6}" cy="${HOME_GROUND - 24}" r="3.5" fill="#f6b3d6"/><circle cx="${EX + 6}" cy="${HOME_GROUND - 14}" r="4" fill="#9fd8ff"/><circle cx="${EX + 5}" cy="${HOME_GROUND - 30}" r="2.5" fill="#ffd23f"/>
        ${sparkle(EX + 22, HOME_GROUND - 44, 6, "#ffd23f")}</g>`
    : "";
  const svg = (cls, inner) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${HOME_W} ${HOME_H}" class="${cls}" aria-hidden="true">${inner}</svg>`;
  return {
    back: svg("tm-pet-scene", `${layer("sky")}${layer("back")}${layer("ground")}`),
    pet: svg("pt-layer", `<g transform="translate(${px} ${py})">${petBody(species, stage, !!opts.legendary)}${dress}</g>`),
    front: svg("pt-layer", layer("front")),
    egg: newEgg ? svg("pt-layer", newEgg) : "",
  };
}


// SVG markup → a DOM node Lit can render (no innerHTML). Every input is from
// the fixed tables above, never user text; parsed once per look and cloned.
const _artCache = new Map();
function _artNode(markup) {
  let node = _artCache.get(markup);
  if (!node) {
    node = new DOMParser().parseFromString(markup, "image/svg+xml").documentElement;
    if (_artCache.size > 60) _artCache.clear();
    _artCache.set(markup, node);
  }
  return node.cloneNode(true);
}
window.__taskmate_pet_art = { petArt, petScene, petAnchors };

class TaskMatePetCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
      _species: { type: String },
      _busy: { type: Boolean },
      _error: { type: String },
      _petting: { type: Boolean },
      _evolving: { type: String },
      _hatching: { type: Boolean },
    };
  }

  constructor() {
    super();
    this._species = "dragon";
    this._busy = false;
    this._error = "";
    this._petting = false;
    this._evolving = "";
    this._hatching = false;
  }

  setConfig(config) {
    if (!config || !config.entity) throw new Error("You need to define an entity");
    if (!config.child_id) throw new Error("You need to define a child_id");
    this.config = config;
  }

  static getStubConfig() {
    return { entity: "sensor.taskmate_overview", child_id: "" };
  }

  static getConfigElement() {
    return document.createElement("taskmate-pet-card-editor");
  }

  getCardSize() {
    return 5;
  }

  shouldUpdate(changedProps) {
    if (changedProps.has("hass") && changedProps.size === 1) {
      return window.__taskmate_hasChanged
        ? window.__taskmate_hasChanged(changedProps.get("hass"), this.hass, this.config?.entity)
        : true;
    }
    return true;
  }

  _t(key, params) {
    const fn = window.__taskmate_localize;
    return fn ? fn(this.hass, key, params) : key;
  }

  _attrs() {
    return (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity))
      || this.hass?.states?.[this.config.entity]?.attributes || {};
  }

  _child() {
    return (this._attrs().children || []).find(c => String(c.id) === String(this.config.child_id));
  }

  _applyDesign() {
    const design = window.__taskmate_design
      ? window.__taskmate_design.apply(this, this.hass, this.config, this.config.entity)
      : "classic";
    const configured = this.config.header_color;
    if (typeof configured === "string" && /^#[0-9a-fA-F]{3,8}$/.test(configured)) {
      this.style.setProperty("--pt-accent", _safeColor(configured, DEFAULT_ACCENT));
    } else {
      this.style.removeProperty("--pt-accent");
    }
    return design;
  }

  async _adopt(child, hatchEgg = false) {
    const input = this.renderRoot && this.renderRoot.querySelector("#pt-name");
    const name = String((input && input.value) || "").trim();
    if (!name) { this._error = this._t("pet.name_needed"); return; }
    this._busy = true;
    this._error = "";
    try {
      const data = { child_id: child.id, species: this._species, name };
      if (hatchEgg) data.hatch_egg = true;
      await this.hass.callService("taskmate", "adopt_pet", data);
      this._hatching = false;
    } catch (err) {
      this._error = String(err?.message || err);
    } finally {
      this._busy = false;
    }
  }

  _pet() {
    // A tap is a cuddle: a little hop and hearts, nothing saved.
    this._petting = true;
    clearTimeout(this._pettingTimer);
    this._pettingTimer = setTimeout(() => { this._petting = false; }, 900);
  }

  // ── growing up, seen on this device ────────────────────────────────
  // The card remembers what it last showed for this child; anything bigger
  // since then plays the "evolving" moment once. The first look is quiet.
  _seenKey() { return `taskmate_pet_seen_${this.config.child_id}`; }

  _milestones(pet) {
    return {
      name: pet.name,
      stage: PET_STAGE_ORDER.indexOf(pet.stage),
      legendary: !!pet.legendary,
      egg: !!pet.egg_ready,
      home: Number(pet.home) || 0,
      level: Number(pet.pet_level) || 0,
    };
  }

  _checkEvolve(pet) {
    if (!pet || !pet.adopted) return;
    const now = this._milestones(pet);
    const snapshot = JSON.stringify(now);
    let saved;
    try { saved = localStorage.getItem(this._seenKey()); } catch (_e) { saved = null; }
    if (saved === snapshot) return;
    let before;
    try { before = JSON.parse(saved || "null"); } catch (_e) { before = null; }
    try { localStorage.setItem(this._seenKey(), snapshot); } catch (_e) { /* private mode */ }
    if (!before || before.name !== now.name) return;
    let kind = "";
    if (now.stage > before.stage) kind = "stage";
    else if (now.legendary && !before.legendary) kind = "legendary";
    else if (now.egg && !before.egg) kind = "egg";
    else if (now.level > before.level && before.level) kind = "level";
    else if (now.home > before.home) kind = "home";
    if (!kind) return;
    this._evolving = kind;
    clearTimeout(this._evolveTimer);
    this._evolveTimer = setTimeout(() => { this._evolving = ""; }, 3200);
  }

  updated(changed) {
    super.updated && super.updated(changed);
    if (changed.has("hass") && this.config) {
      const child = this._child();
      if (child && child.pet) this._checkEvolve(child.pet);
    }
  }

  render() {
    if (!this.hass || !this.config) return html``;
    this._applyDesign();
    const child = this._child();
    const title = this.config.title || (child && child.pet && child.pet.adopted ? child.pet.name : this._t("pet.title"));
    if (!child) return html`<ha-card>${this._header(title)}<div class="pt-empty">${this._t("pet.no_child")}</div></ha-card>`;
    const pet = child.pet;
    if (!pet) return html`<ha-card>${this._header(title)}<div class="pt-empty">${this._t("pet.off")}</div></ha-card>`;
    // Compact (#1094): the kiosk card shows the pet in a side tile — no
    // banner, no accessories or family row, just the pet, its mood and growth.
    if (this.config.compact) {
      return html`<ha-card class="pt-compact">
        ${pet.adopted ? html`<div class="pt-compact-name">🐾 ${pet.name}${pet.pet_level ? html` <small>💖 ${this._t("pet.level", { level: pet.pet_level })}</small>` : ""}</div>` : ""}
        ${pet.adopted ? this._renderPet(child, pet) : this._renderAdopt(child)}
      </ha-card>`;
    }
    return html`<ha-card>${this._header(title, pet)}${pet.adopted ? this._renderPet(child, pet) : this._renderAdopt(child)}</ha-card>`;
  }

  _speciesName(id) { return this._t(`pet.species_${id}`); }

  _header(title, pet) {
    const sub = pet && pet.adopted
      ? (pet.legendary
        ? this._t("pet.stage_legendary", { species: this._speciesName(pet.species) })
        : this._t(`pet.stage_${pet.stage}`, { species: this._speciesName(pet.species) }))
      : "";
    return html`
      <div class="pt-hd">
        <ha-icon class="pt-hd-icon" icon="mdi:paw"></ha-icon>
        <div class="pt-hd-text">
          <div class="pt-hd-title">${title}</div>
          ${sub ? html`<div class="pt-hd-sub">${sub}</div>` : ""}
        </div>
        ${pet && pet.pet_level ? html`<span class="pt-level">💖 ${this._t("pet.level", { level: pet.pet_level })}</span>` : ""}
      </div>`;
  }

  _goalText(pet, percent) {
    const g = pet.goal;
    if (!g) return this._t("pet.fully_grown", { name: pet.name });
    if (g.kind === "stage") {
      const next = PET_STAGE_ORDER[PET_STAGE_ORDER.indexOf(pet.stage) + 1] || "grown";
      return this._t("pet.goal_stage", { percent, stage: this._t(`pet.stage_${next}`, { species: this._speciesName(pet.species) }) });
    }
    if (g.kind === "level") return this._t("pet.goal_level", { percent, level: (Number(pet.pet_level) || 1) + 1 });
    return this._t(`pet.goal_${g.kind}`, { percent, name: pet.name });
  }

  _renderPet(child, pet) {
    const acc = pet.accessories || [];
    const g = pet.goal;
    const span = g ? Math.max(1, g.at - g.from) : 1;
    const pct = g ? Math.max(0, Math.min(100, Math.floor(((pet.xp - g.from) / span) * 100))) : 100;
    const scene = petScene(pet.species, pet.stage, {
      legendary: !!pet.legendary,
      home: pet.home || 0,
      egg: !!pet.egg_ready,
      accessories: acc,
    });
    const homeClass = pet.home ? "has-home" : "";
    return html`
      <div class="pt-body">
        <button type="button" class="pt-stage ${homeClass} mood-${pet.mood} stage-${pet.stage} ${pet.legendary ? "legendary" : ""} ${this._petting ? "petting" : ""} ${this._evolving ? "evolving" : ""}"
                aria-label="${this._t("pet.cuddle", { name: pet.name })}" @click=${() => this._pet()}>
          ${_artNode(scene.back)}
          <div class="pt-layer tm-pet">${_artNode(scene.pet)}</div>
          ${_artNode(scene.front)}
          ${scene.egg ? html`<div class="pt-layer tm-new-egg">${_artNode(scene.egg)}</div>` : ""}
          ${pet.mood === "sleepy" ? html`<span class="pt-zzz" aria-hidden="true">💤</span>` : ""}
          ${pet.mood === "proud" ? html`<span class="pt-spark" aria-hidden="true">✨</span>` : ""}
          ${this._petting ? html`<span class="pt-hearts" aria-hidden="true">💕</span>` : ""}
          ${this._evolving ? html`<span class="pt-burst" aria-hidden="true"></span>` : ""}
        </button>
        ${this._evolving
          ? html`<div class="pt-evolve" role="status">${this._t(`pet.evolve_${this._evolving}`, { name: pet.name, level: pet.pet_level || "" })}</div>`
          : html`<div class="pt-mood">${this._t(`pet.mood_${pet.mood}`, { name: pet.name })}</div>`}
        <div class="pt-grow">
          <div class="pt-grow-text">${this._goalText(pet, pct)}</div>
          ${g ? html`<span class="pt-bar" role="progressbar" aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100"><i style="width:${pct}%"></i></span>` : ""}
        </div>
        ${pet.egg_ready ? this._renderEggReady(child, pet) : ""}
        ${this.config.compact ? "" : html`<div class="pt-acc">
          ${["bow", "top_hat", "scarf", "crown"].map(a => html`
            <span class="pt-acc-item ${acc.includes(a) ? "on" : ""}" title="${this._t(`pet.acc_${a}`)}">
              <span>${ACC_ICON[a]}</span>
              <small>${acc.includes(a) ? this._t(`pet.acc_${a}`) : this._t("pet.acc_locked", { level: { bow: 3, top_hat: 8, scarf: 15, crown: 25 }[a] })}</small>
            </span>`)}
        </div>`}
        ${pet.family && pet.family.length && !this.config.compact ? this._renderFamily(pet.family) : ""}
      </div>`;
  }

  _renderEggReady(child, pet) {
    if (!this._hatching) {
      return html`
        <div class="pt-egg-note">
          <span>${this._t("pet.egg_ready", { name: pet.name })}</span>
          <button class="pt-btn" @click=${() => { this._hatching = true; this._error = ""; this.requestUpdate(); }}>🥚 ${this._t("pet.hatch")}</button>
        </div>`;
    }
    return html`<div class="pt-hatch">${this._renderPicker(child, true)}</div>`;
  }

  _renderFamily(family) {
    return html`
      <div class="pt-family">
        <div class="pt-family-title">${this._t("pet.family_title")}</div>
        <div class="pt-family-row">
          ${family.map(m => html`
            <div class="pt-family-pet ${m.legendary ? "legendary" : ""}">
              ${_artNode(petArt(SPECIES_IDS.includes(m.species) ? m.species : "dragon", "grown", !!m.legendary))}
              <small>${m.name}</small>
            </div>`)}
        </div>
      </div>`;
  }

  _renderPicker(child, hatching) {
    const q = hatching ? this._t("pet.hatch_question", { name: child.name }) : this._t("pet.adopt_question", { name: child.name });
    return html`
      <div class="pt-adopt-q">${q}</div>
      <div class="pt-pick" role="radiogroup" aria-label="${q}">
        ${SPECIES_IDS.map(id => html`
          <button type="button" role="radio" aria-checked="${this._species === id}" class="pt-opt ${this._species === id ? "on" : ""}"
                  @click=${() => { this._species = id; }}>
            ${_artNode(petArt(id, "baby"))}<small>${this._speciesName(id)}</small>
          </button>`)}
      </div>
      <input id="pt-name" class="pt-name" maxlength="24" placeholder="${this._t("pet.name_placeholder")}" aria-label="${this._t("pet.name_placeholder")}">
      ${this._error ? html`<div class="pt-err" role="alert">${this._error}</div>` : ""}
      <button class="pt-btn" ?disabled=${this._busy} @click=${() => this._adopt(child, hatching)}>🥚 ${this._t(hatching ? "pet.hatch" : "pet.adopt")}</button>`;
  }

  _renderAdopt(child) {
    return html`<div class="pt-body">${this._renderPicker(child, false)}</div>`;
  }

  static get styles() {
    const base = css`
      :host { display: block; --pt-accent: var(--tmd-accent, #16a085); }
      ha-card { overflow: hidden; background: var(--tmd-surface, var(--ha-card-background, var(--card-background-color, #fff)));
        color: var(--tmd-text, var(--primary-text-color)); border-radius: var(--tmd-radius, var(--ha-card-border-radius, 12px)); font-family: var(--tmd-font-body, inherit); }
      /* Compact (#1094): inside the kiosk card's side column */
      ha-card.pt-compact { box-shadow: none; border: 0; background: transparent; }
      .pt-compact-name { font-weight: 800; font-size: 1.05rem; padding: 4px 4px 0; }
      .pt-compact-name small { font-weight: 600; opacity: .8; margin-inline-start: 6px; }
      .pt-compact .pt-body { padding: 6px 4px 4px; gap: 8px; }
      .pt-compact .pt-stage { max-width: 220px; margin: 0 auto; }
      .pt-hd { display: flex; align-items: center; gap: 12px; padding: 14px 18px; background: var(--pt-accent); color: var(--tmd-hd-text, #fff); }
      :host([data-tm-design="playroom"]) .pt-hd { background: linear-gradient(135deg, var(--pt-accent), color-mix(in srgb, var(--pt-accent) 72%, #fff)); }
      .pt-hd-icon { --mdc-icon-size: 28px; }
      .pt-hd-text { flex: 1; min-width: 0; }
      .pt-hd-title { font-family: var(--tmd-font-display, inherit); font-size: 1.3rem; font-weight: 600; }
      .pt-hd-sub { font-size: .85rem; opacity: .9; }
      .pt-level { font-weight: 800; font-size: .9rem; padding: 4px 10px; border-radius: 999px; background: rgba(255,255,255,.22); white-space: nowrap; }
      .pt-empty { padding: 26px; text-align: center; color: var(--tmd-dim, var(--secondary-text-color)); }
      .pt-body { padding: 16px; display: flex; flex-direction: column; align-items: center; gap: 12px; text-align: center; }
      .pt-stage { position: relative; width: 100%; max-width: 360px; aspect-ratio: 320 / 210; padding: 0; border: 0; cursor: pointer; border-radius: 22px; overflow: hidden;
        background: radial-gradient(ellipse at 50% 80%, color-mix(in srgb, var(--pt-accent) 20%, transparent), transparent 70%); }
      .pt-stage.has-home { background: linear-gradient(#dff1ff, #f4fbff 70%); }
      .pt-stage.legendary:not(.has-home) { background: radial-gradient(ellipse at 50% 60%, #fff4c9, transparent 72%); }
      .pt-stage svg { display: block; width: 100%; height: 100%; }
      .pt-layer { position: absolute; inset: 0; pointer-events: none; }
      /* Animated layers are HTML, never SVG groups: see petScene (#1126). The
         origins are the pet's and the egg's feet on the 320×210 canvas. */
      .pt-stage .tm-pet { transform-origin: 50% 95%; }
      .mood-happy .tm-pet, .mood-proud .tm-pet { animation: pt-bounce 1.6s ease-in-out infinite; }
      .mood-content .tm-pet { animation: pt-sway 3s ease-in-out infinite; }
      .mood-sleepy .tm-pet { filter: grayscale(.35) brightness(.92); }
      .stage-egg .tm-pet { animation: pt-wobble 2.2s ease-in-out infinite; }
      .petting .tm-pet { animation: pt-hop .5s ease-out; }
      .evolving .tm-pet { animation: pt-evolve 1.6s ease-in-out 2; }
      .tm-new-egg { transform-origin: 15% 94%; animation: pt-wobble 2.6s ease-in-out infinite; }
      .pt-zzz { position: absolute; top: 6px; inset-inline-end: 10px; font-size: 30px; animation: pt-float 2.4s ease-in-out infinite; }
      .pt-spark { position: absolute; top: 6px; inset-inline-start: 10px; font-size: 28px; animation: pt-float 1.8s ease-in-out infinite; }
      .pt-hearts { position: absolute; top: 4px; left: 50%; transform: translateX(-50%); font-size: 30px; animation: pt-up .9s ease-out forwards; } /* rtl-ok: centred horizontally */
      .pt-burst { position: absolute; inset: 0; pointer-events: none; background: radial-gradient(circle at 50% 60%, rgba(255,255,255,.95), rgba(255,236,160,.6) 30%, transparent 62%);
        animation: pt-flash 1.6s ease-out 2; opacity: 0; }
      .pt-mood { font-weight: 700; font-size: 1.05rem; }
      .pt-evolve { font-weight: 800; font-size: 1.2rem; color: var(--pt-accent); animation: pt-pop .5s ease-out; }
      .pt-grow { width: 100%; max-width: 340px; display: flex; flex-direction: column; gap: 6px; }
      .pt-grow-text { font-size: .9rem; color: var(--tmd-dim, var(--secondary-text-color)); }
      .pt-bar { display: block; height: 10px; border-radius: 6px; background: var(--tmd-surface-2, rgba(127,127,127,.15)); overflow: hidden; }
      .pt-bar i { display: block; height: 100%; background: var(--pt-accent); border-radius: 6px; }
      .legendary ~ .pt-grow .pt-bar i { background: linear-gradient(90deg, #f6c445, #ff9f1c); }
      .pt-egg-note { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 12px 14px; border-radius: 16px; width: 100%; max-width: 340px; box-sizing: border-box;
        background: color-mix(in srgb, #ffd23f 18%, transparent); font-weight: 700; }
      .pt-hatch { display: flex; flex-direction: column; align-items: center; gap: 10px; width: 100%; }
      .pt-acc { display: flex; gap: 8px; flex-wrap: wrap; justify-content: center; }
      .pt-acc-item { display: flex; flex-direction: column; align-items: center; gap: 2px; padding: 6px 10px; border-radius: 12px; min-width: 64px;
        background: var(--tmd-surface-2, rgba(127,127,127,.1)); opacity: .45; filter: grayscale(1); }
      .pt-acc-item.on { opacity: 1; filter: none; background: color-mix(in srgb, var(--pt-accent) 14%, transparent); }
      .pt-acc-item span { font-size: 24px; }
      .pt-acc-item small { font-size: .7rem; }
      .pt-family { width: 100%; }
      .pt-family-title { font-weight: 700; font-size: .95rem; margin-bottom: 6px; }
      .pt-family-row { display: flex; gap: 8px; justify-content: center; flex-wrap: wrap; }
      .pt-family-pet { width: 72px; display: flex; flex-direction: column; align-items: center; padding: 4px 2px 6px; border-radius: 14px;
        background: var(--tmd-surface-2, rgba(127,127,127,.1)); }
      .pt-family-pet.legendary { background: color-mix(in srgb, #ffd23f 22%, transparent); }
      .pt-family-pet svg { width: 64px; height: 64px; }
      .pt-family-pet small { font-size: .72rem; max-width: 68px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .pt-adopt-q { font-weight: 700; font-size: 1.05rem; }
      .pt-pick { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; width: 100%; max-width: 330px; }
      .pt-opt { display: flex; flex-direction: column; align-items: center; gap: 0; padding: 4px 4px 8px; border-radius: 14px; cursor: pointer; font: inherit;
        border: 2px solid var(--tmd-border, var(--divider-color, #ddd)); background: var(--tmd-surface, var(--card-background-color, #fff)); color: inherit; }
      .pt-opt svg { width: 64px; height: 64px; }
      .pt-opt small { display: block; font-size: .75rem; }
      .pt-opt small::first-letter { text-transform: uppercase; }
      .pt-opt.on { border-color: var(--pt-accent); background: color-mix(in srgb, var(--pt-accent) 12%, transparent); }
      .pt-name { width: 100%; max-width: 330px; box-sizing: border-box; padding: 10px 12px; font: inherit; font-size: 1rem; border-radius: 12px;
        border: 2px solid var(--tmd-border, var(--divider-color, #ddd)); background: var(--tmd-surface, var(--card-background-color, #fff)); color: inherit; }
      .pt-btn { border: 0; border-radius: 999px; padding: 10px 22px; font: inherit; font-weight: 800; cursor: pointer; background: var(--pt-accent); color: #fff; }
      .pt-btn:disabled { opacity: .5; }
      .pt-err { color: var(--tmd-bad, var(--error-color, #c62828)); font-size: .85rem; }
      @keyframes pt-bounce { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-8px); } }
      @keyframes pt-sway { 0%, 100% { transform: rotate(-2deg); } 50% { transform: rotate(2deg); } }
      @keyframes pt-wobble { 0%, 80%, 100% { transform: rotate(0); } 85% { transform: rotate(-7deg); } 92% { transform: rotate(7deg); } }
      @keyframes pt-hop { 0% { transform: none; } 40% { transform: scale(1.06) translateY(-14px); } 100% { transform: none; } }
      @keyframes pt-evolve { 0% { transform: scale(1); } 30% { transform: scale(.82) rotate(-6deg); } 55% { transform: scale(1.12) rotate(4deg); } 100% { transform: scale(1); } }
      @keyframes pt-flash { 0% { opacity: 0; } 35% { opacity: 1; } 100% { opacity: 0; } }
      @keyframes pt-pop { 0% { transform: scale(.6); opacity: 0; } 70% { transform: scale(1.08); opacity: 1; } 100% { transform: scale(1); } }
      @keyframes pt-float { 0%, 100% { transform: translateY(0); opacity: .9; } 50% { transform: translateY(-8px); opacity: .6; } }
      @keyframes pt-up { from { transform: translate(-50%, 10px); opacity: 1; } to { transform: translate(-50%, -30px); opacity: 0; } }
      @media (prefers-reduced-motion: reduce) { .tm-pet, .tm-new-egg, .pt-zzz, .pt-spark, .pt-hearts, .pt-burst, .pt-evolve { animation: none !important; } }
    `;
    const tokens = window.__taskmate_design && window.__taskmate_design.styles
      ? window.__taskmate_design.styles() : null;
    return tokens ? [tokens, base] : base;
  }
}

class TaskMatePetCardEditor extends LitElement {
  static get properties() {
    return { hass: { type: Object }, config: { type: Object } };
  }

  setConfig(config) { this.config = config; }

  _t(key, params) {
    const fn = window.__taskmate_localize;
    return fn ? fn(this.hass, key, params) : key;
  }

  _buildSchema() {
    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config?.entity))
      || this.hass?.states?.[this.config?.entity]?.attributes || {};
    const children = attrs.children || [];
    return [
      { name: "entity", selector: { entity: { domain: "sensor" } } },
      { name: "child_id", selector: { select: { options: children.map(c => ({ value: c.id, label: c.name })), mode: "dropdown" } } },
      { name: "title", selector: { text: {} } },
      {
        name: "card_design",
        selector: {
          select: {
            options: window.__taskmate_design
              ? window.__taskmate_design.editorOptions(this._t.bind(this))
              : [{ value: "global", label: "Use global default" }],
            mode: "dropdown",
          },
        },
      },
    ];
  }

  _computeLabel = (entry) => ({
    entity: this._t("common.editor.overview_entity"),
    child_id: this._t("pet.editor.child"),
    title: this._t("common.editor.card_title"),
    card_design: this._t("common.design.field_label"),
  }[entry.name] ?? entry.name);

  render() {
    if (!this.hass || !this.config) return html``;
    const data = {
      entity: this.config.entity || "",
      child_id: this.config.child_id || "",
      title: this.config.title || "",
      card_design: this.config.card_design || "global",
    };
    return html`<ha-form .hass=${this.hass} .data=${data} .schema=${this._buildSchema()}
      .computeLabel=${this._computeLabel} @value-changed=${this._formChanged}></ha-form>`;
  }

  _formChanged(e) {
    const newConfig = { ...this.config };
    for (const [key, value] of Object.entries(e.detail.value || {})) {
      if (value === "" || value === null || value === undefined || (key === "card_design" && value === "global")) delete newConfig[key];
      else newConfig[key] = value;
    }
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: newConfig }, bubbles: true, composed: true }));
  }

  static get styles() {
    return css`:host { display: block; }`;
  }
}

customElements.define("taskmate-pet-card", TaskMatePetCard);
customElements.define("taskmate-pet-card-editor", TaskMatePetCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "taskmate-pet-card",
  name: "TaskMate Pet",
  description: "A virtual pet that grows as the child does chores",
  preview: true,
  getEntitySuggestion: (hass, entityId) =>
    window.__taskmate_suggest ? window.__taskmate_suggest(hass, entityId, "taskmate-pet-card", "overview") : undefined,
});
