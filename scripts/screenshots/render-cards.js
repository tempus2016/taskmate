// Montage: render a batch of cards, each as a row of 3 designs, using ha-dev's
// live hass (optionally augmented with synthetic data for data-less cards).
const { chromium } = require('playwright');
const fs = require('fs');
const HA = process.env.HA || 'http://192.168.0.154:8124';
const TOKEN = fs.readFileSync(process.env.HA_TOKEN || (__dirname + '/../../../ha-dev/.ha_token'), 'utf8').trim();
const BATCH = process.argv[2] || 'A';

const BATCHES = {
  A: [['taskmate-leaderboard-card', {}], ['taskmate-streak-card', {}], ['taskmate-weekly-card', {}], ['taskmate-graph-card', {}]],
  B: [['taskmate-parent-dashboard-card', {}], ['taskmate-overview-card', {}], ['taskmate-calendar-card', {}], ['taskmate-activity-card', {}]],
  C: [['taskmate-points-card', {}], ['taskmate-child-card', { __childFirst: true }], ['taskmate-reorder-card', { __childFirst: true }], ['taskmate-badges-card', { __badges: true }]],
  D: [['taskmate-rewards-card', {}], ['taskmate-reward-progress-card', {}], ['taskmate-approvals-card', {}], ['taskmate-bonuses-card', {}], ['taskmate-penalties-card', {}]],
};
const cards = BATCHES[BATCH];
const ALL = ['taskmate-leaderboard-card','taskmate-streak-card','taskmate-weekly-card','taskmate-graph-card','taskmate-parent-dashboard-card','taskmate-overview-card','taskmate-calendar-card','taskmate-activity-card','taskmate-points-card','taskmate-child-card','taskmate-reorder-card','taskmate-badges-card','taskmate-rewards-card','taskmate-reward-progress-card','taskmate-approvals-card','taskmate-bonuses-card','taskmate-penalties-card'];
const MODULES = ['taskmate-attr-resolver.js','taskmate-localize.js','taskmate-design.js',...ALL.map(c=>c+'.js')];

(async () => {
  try {
    const browser = await chromium.connectOverCDP(process.env.CDP || 'http://192.168.0.154:3002');
    const ctx = await browser.newContext({ viewport: { width: 1180, height: 1000 }, deviceScaleFactor: 2 });
    const page = await ctx.newPage();
    await page.addInitScript((tok) => { const u = location.origin; localStorage.setItem('hassTokens', JSON.stringify({ access_token: tok, token_type: 'Bearer', expires_in: 315360000, hassUrl: u, clientId: u + '/', expires: Date.now() + 315360000000, refresh_token: '' })); }, TOKEN);
    await page.goto(HA, { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => !!customElements.get('hui-masonry-view'), null, { timeout: 45000 });
    const v = Date.now();
    for (const f of MODULES) await page.addScriptTag({ url: `${HA}/taskmate/${f}?v=${v}`, type: 'module' });
    await page.waitForFunction(() => !!window.__taskmate_design && !!customElements.get('taskmate-penalties-card'), null, { timeout: 20000 });

    await page.evaluate(async ({ cards, augment }) => {
      const ha = document.querySelector('home-assistant');
      let hass = ha.hass;
      const ovId = 'sensor.taskmate_overview';
      const children = (hass.states[ovId]?.attributes?.children || []);
      const childId = children[0]?.id;
      const badgesEntity = Object.keys(hass.states).find(e => /taskmate_badges/.test(e));
      if (augment) {
        const kids = children.map(c => c.id);
        const now = new Date().toISOString();
        const mk = (id, attrs) => ({ entity_id: id, state: '0', attributes: attrs, last_changed: now, last_updated: now, context: { id: '1' } });
        const synthRewards = [
          { id: 'r1', name: 'Movie night', description: 'Pick a family film', cost: 150, icon: 'mdi:movie', enabled: true, assigned_to: [], child_costs: {} },
          { id: 'r2', name: 'Ice cream trip', description: 'A trip to the parlour', cost: 80, icon: 'mdi:ice-cream', enabled: true, assigned_to: [], child_costs: {} },
          { id: 'r3', name: 'New Lego set', description: 'Earn a new set', cost: 400, icon: 'mdi:toy-brick', enabled: true, assigned_to: [], child_costs: {} },
        ];
        const pend = [
          { id: 'pc1', chore_id: 'c1', chore_name: 'Make bed', child_id: kids[0], child_name: children[0]?.name, points: 8, timestamp: now, approved: false, time_category: 'morning' },
          { id: 'pc2', chore_id: 'c2', chore_name: 'Feed the dog', child_id: kids[1] || kids[0], child_name: (children[1] || children[0])?.name, points: 10, timestamp: now, approved: false, time_category: 'morning' },
        ];
        const newStates = { ...hass.states,
          'sensor.taskmate_rewards': mk('sensor.taskmate_rewards', { rewards: synthRewards, total_rewards: synthRewards.length, reward_claims: [], pending_reward_claims: [] }),
          'sensor.taskmate_incentives': mk('sensor.taskmate_incentives', {
            bonuses: [
              { id: 'b1', name: 'Tidied bedroom', points: 5, icon: 'mdi:broom', description: '' },
              { id: 'b2', name: 'Helped with dinner', points: 3, icon: 'mdi:silverware-fork-knife', description: '' },
              { id: 'b3', name: 'Extra reading', points: 4, icon: 'mdi:book-open-variant', description: '' },
            ],
            penalties: [
              { id: 'p1', name: "Didn't go to bed", points: 5, icon: 'mdi:bed', description: '' },
              { id: 'p2', name: 'Left a mess', points: 3, icon: 'mdi:delete-variant', description: '' },
              { id: 'p3', name: 'Backchat', points: 2, icon: 'mdi:account-voice', description: '' },
            ],
          }),
          'sensor.pending_approvals': mk('sensor.pending_approvals', { pending_completions: pend, chore_completions: pend, reward_claims: [], pending_reward_claims: [] }),
        };
        hass = { ...hass, states: newStates };
      }
      const wrap = document.createElement('div');
      wrap.id = '__m';
      wrap.style.cssText = 'position:relative;z-index:2147483647;width:1140px;background:#e9ebef;padding:18px;display:flex;flex-direction:column;gap:24px';
      // hide HA app
      ha.style.display = 'none'; document.documentElement.style.background = '#e9ebef'; document.body.style.margin = '0';
      document.body.appendChild(wrap);
      for (const [tag, cfg] of cards) {
        const row = document.createElement('div');
        row.style.cssText = 'display:grid;grid-template-columns:360px 360px 360px;gap:14px';
        const head = document.createElement('div');
        head.textContent = tag.replace('taskmate-', '').replace('-card', '');
        head.style.cssText = 'grid-column:1/-1;font:800 13px sans-serif;color:#333;text-transform:uppercase;letter-spacing:.05em';
        row.appendChild(head);
        for (const design of ['playroom', 'console', 'cleanpro']) {
          const col = document.createElement('div'); col.style.width = '360px';
          const lbl = document.createElement('div'); lbl.textContent = design; lbl.style.cssText = 'font:700 10px sans-serif;color:#777;margin:0 0 4px 2px;text-transform:uppercase';
          col.appendChild(lbl);
          const config = { entity: ovId, ...cfg, card_design: design };
          if (cfg.__childFirst) config.child_id = childId;
          if (cfg.__badges && badgesEntity) config.entity = badgesEntity;
          delete config.__childFirst; delete config.__badges;
          const el = document.createElement(tag);
          try { if (el.setConfig) el.setConfig(config); el.hass = hass; } catch (e) { lbl.textContent = design + ' ERR ' + e.message; }
          col.appendChild(el); row.appendChild(col);
        }
        wrap.appendChild(row);
      }
      await new Promise(r => setTimeout(r, 1100));
    }, { cards, augment: BATCH === 'D' });

    const el = await page.$('#__m');
    await el.screenshot({ path: `/home/claude/workspace/taskmate/.tmp/montage-${BATCH}.png` });
    await ctx.close(); await browser.close();
    console.log('OK montage-' + BATCH + '.png');
  } catch (e) { console.error('ERR:', e && e.message); process.exit(1); }
})();
