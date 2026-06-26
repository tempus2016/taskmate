/**
 * TaskMate Bonuses Card — thin wrapper over the shared incentive base (QUAL-2).
 */
import { createIncentiveCard } from "./taskmate-incentive-card.js";

createIncentiveCard({
  tag: "taskmate-bonuses-card",
  kind: "bonus",
  idKey: "bonus_id",
  i18n: "bonuses",
  attr: "bonuses",
  icon: "mdi:star-circle-outline",
  headerIcon: "mdi:star-circle",
  applyIcon: "mdi:plus-circle-outline",
  sign: "+",
  dpts: (n) => `+${n}`,
  accent: "#2e7d32",
  accentDark: "#1b5e20",
  accentLight: "rgba(46, 125, 50, 0.12)",
  accentFlash: "rgba(46,125,50,0.25)",
  accentShadow: "rgba(46,125,50,0.3)",
  designAccent: "var(--tmd-good)",
  designHd: "#2e7d32",
  designIcons: { console: "▲", cleanpro: "＋", playroom: "🎁" },
  cardName: "TaskMate Bonuses",
  cardDesc: "Apply point-awarding bonuses to children",
  bannerName: "BONUSES",
  bannerColor: "#f39c12",
});
