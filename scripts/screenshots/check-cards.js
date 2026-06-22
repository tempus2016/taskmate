// Instantiate every converted card in all 3 designs against ha-dev's live hass,
// capture console errors, and confirm the designed shell (.tmd) renders.
const { chromium } = require('playwright');
const fs = require('fs');
const HA = process.env.HA || 'http://192.168.0.154:8124';
const TOKEN = fs.readFileSync(process.env.HA_TOKEN || (__dirname + '/../../../ha-dev/.ha_token'), 'utf8').trim();

const CARDS = [
  ['taskmate-points-display-card', { mode: 'multi' }],
  ['taskmate-points-card', {}],
  ['taskmate-child-card', { __childFirst: true }],
  ['taskmate-leaderboard-card', {}],
  ['taskmate-streak-card', {}],
  ['taskmate-badges-card', { __badges: true }],
  ['taskmate-graph-card', {}],
  ['taskmate-rewards-card', {}],
  ['taskmate-reward-progress-card', {}],
  ['taskmate-weekly-card', {}],
  ['taskmate-approvals-card', {}],
  ['taskmate-parent-dashboard-card', {}],
  ['taskmate-overview-card', {}],
  ['taskmate-bonuses-card', {}],
  ['taskmate-penalties-card', {}],
  ['taskmate-reorder-card', { __childFirst: true }],
  ['taskmate-activity-card', {}],
  ['taskmate-calendar-card', {}],
];
const MODULES = ['taskmate-attr-resolver.js', 'taskmate-localize.js', 'taskmate-design.js',
  ...CARDS.map(c => c[0] + '.js')];

(async () => {
  try {
    const browser = await chromium.connectOverCDP(process.env.CDP || 'http://192.168.0.154:3002');
    const ctx = await browser.newContext({ viewport: { width: 1200, height: 900 }, deviceScaleFactor: 1 });
    const page = await ctx.newPage();
    const errors = [];
    page.on('console', m => { if (m.type() === 'error') errors.push(m.text().slice(0, 200)); });
    page.on('pageerror', e => errors.push('PAGEERROR: ' + e.message.slice(0, 200)));

    await page.addInitScript((tok) => {
      const u = location.origin;
      localStorage.setItem('hassTokens', JSON.stringify({ access_token: tok, token_type: 'Bearer', expires_in: 315360000, hassUrl: u, clientId: u + '/', expires: Date.now() + 315360000000, refresh_token: '' }));
    }, TOKEN);
    await page.goto(HA, { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => !!customElements.get('hui-masonry-view'), null, { timeout: 45000 });
    const v = Date.now();
    for (const f of MODULES) await page.addScriptTag({ url: `${HA}/taskmate/${f}?v=${v}`, type: 'module' });
    await page.waitForFunction(() => !!window.__taskmate_design && !!customElements.get('taskmate-calendar-card'), null, { timeout: 20000 });

    const results = await page.evaluate(async ({ cards }) => {
      const out = [];
      const ha = document.querySelector('home-assistant');
      const hass = ha && ha.hass;
      if (!hass) return [{ tag: 'NO_HASS', ok: false }];
      const childId = (hass.states['sensor.taskmate_overview']?.attributes?.children || [])[0]?.id;
      const badgesEntity = Object.keys(hass.states).find(e => /taskmate_badges/.test(e));
      const host = document.createElement('div');
      host.style.cssText = 'position:fixed;left:-9999px;top:0;width:360px';
      document.body.appendChild(host);
      for (const [tag, cfg] of cards) {
        for (const design of ['playroom', 'console', 'cleanpro']) {
          const config = { entity: 'sensor.taskmate_overview', ...cfg, card_design: design };
          if (cfg.__childFirst) config.child_id = childId;
          if (cfg.__badges && badgesEntity) config.entity = badgesEntity;
          delete config.__childFirst; delete config.__badges;
          let rec = { tag, design, ok: false, shell: null, err: null };
          try {
            const el = document.createElement(tag);
            if (typeof el.setConfig === 'function') el.setConfig(config);
            el.hass = hass;
            host.appendChild(el);
            await new Promise(r => setTimeout(r, 60));
            const sr = el.shadowRoot;
            const hasTmd = !!(sr && sr.querySelector('.tmd'));
            const hasEmpty = !!(sr && sr.querySelector('.tmd-empty'));
            const dataAttr = el.getAttribute('data-tm-design');
            rec.ok = hasTmd && dataAttr === design;
            rec.shell = hasTmd ? (hasEmpty ? 'empty' : 'content') : 'NO .tmd';
            host.removeChild(el);
          } catch (e) { rec.err = String(e.message || e).slice(0, 160); }
          out.push(rec);
        }
      }
      return out;
    }, { cards: CARDS });

    // Summarise per card
    const byCard = {};
    for (const r of results) {
      byCard[r.tag] = byCard[r.tag] || { content: 0, empty: 0, bad: 0, errs: [] };
      if (r.err || !r.ok) { byCard[r.tag].bad++; if (r.err) byCard[r.tag].errs.push(r.design + ':' + r.err); }
      else if (r.shell === 'content') byCard[r.tag].content++;
      else if (r.shell === 'empty') byCard[r.tag].empty++;
    }
    for (const [tag, s] of Object.entries(byCard)) {
      const flag = s.bad ? 'FAIL' : (s.content ? 'OK  ' : 'EMPTY');
      console.log(`${flag} ${tag}  content=${s.content} empty=${s.empty} bad=${s.bad}` + (s.errs.length ? '  ' + s.errs.join(' | ') : ''));
    }
    console.log('--- page console errors (' + errors.length + ') ---');
    [...new Set(errors)].slice(0, 25).forEach(e => console.log('  ' + e));
    await ctx.close(); await browser.close();
  } catch (e) { console.error('ERR:', e && e.message); process.exit(1); }
})();
