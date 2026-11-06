/**
 * TaskMate Penalties Card — thin wrapper over the shared incentive base (QUAL-2).
 */
import { createIncentiveCard } from "./taskmate-incentive-card.js";

createIncentiveCard({
  // Carries this module's ?v= version onto the lazily loaded editor.
  moduleUrl: import.meta.url,
  tag: "taskmate-penalties-card",
  kind: "penalty",
  idKey: "penalty_id",
  i18n: "penalties",
  // The card's own "Add …" / "New …" button labels (#1234).
  addKey: "add_penalty",
  newKey: "new_penalty",
  attr: "penalties",
  icon: "mdi:alert-circle-outline",
  headerIcon: "mdi:alert-circle-outline",
  applyIcon: "mdi:minus-circle-outline",
  sign: "",
  // `fmt` formats the figure the HA way (#771); the card passes its helper.
  dpts: (n, fmt = String) => `−${fmt(Math.abs(n))}`,
  accent: "#e74c3c",
  accentDark: "#c0392b",
  accentLight: "rgba(231, 76, 60, 0.12)",
  accentFlash: "rgba(231,76,60,0.25)",
  accentShadow: "rgba(231,76,60,0.3)",
  designAccent: "var(--tmd-bad)",
  designHd: "#c0392b",
  designIcons: { console: "▼", cleanpro: "－", playroom: "⚠️" },
  cardName: "TaskMate Penalties",
  cardDesc: "Apply point-deduction penalties to children",
  bannerName: "PENALTIES",
  bannerColor: "#922b21",
});
