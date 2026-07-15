/* ============================================================================
   Databook design-system — shared Chart.js factory
   Loaded globally (no Chart.js dependency at load time). On any page that
   loads Chart.js, call DBChart.apply(Chart) once to theme every chart with the
   navy/accent palette + Public Sans, then use DBChart.navy / .accent /
   .palette / .money() for per-dataset colors. Keeps chart styling consistent
   without each view re-declaring fonts, grid colors, and tooltips.
   ========================================================================== */
window.DBChart = {
  navy: '#162e51',
  accent: '#2491ff',
  navyFill: 'rgba(22, 46, 81, 0.08)',
  accentFill: 'rgba(36, 145, 255, 0.14)',
  grid: '#eef0f2',
  muted: '#757575',
  border: '#dfe1e2',
  // Categorical palette: navy → accent ramp, then harmonized state hues.
  palette: ['#162e51', '#2491ff', '#1f3a63', '#759fbc', '#2e8540', '#c2850c', '#005ea2', '#90c3c8', '#b50909', '#54278f'],

  // Compact money formatter for axis ticks ($1.2B / $340M / $12K).
  money: function (v) {
    v = +v || 0;
    var a = Math.abs(v);
    if (a >= 1e9) return '$' + (v / 1e9).toFixed(1) + 'B';
    if (a >= 1e6) return '$' + (v / 1e6).toFixed(0) + 'M';
    if (a >= 1e3) return '$' + (v / 1e3).toFixed(0) + 'K';
    return '$' + v;
  },

  // Theme Chart.js global defaults. Safe to call once Chart.js is loaded.
  apply: function (Chart) {
    if (!Chart || !Chart.defaults) return;
    Chart.defaults.font.family = "'Public Sans', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif";
    Chart.defaults.font.size = 12;
    Chart.defaults.color = this.muted;
    var p = Chart.defaults.plugins || {};
    if (p.legend) {
      p.legend.labels = Object.assign({}, p.legend.labels, { usePointStyle: true, boxWidth: 10, padding: 14 });
    }
    if (p.tooltip) {
      p.tooltip.backgroundColor = this.navy;
      p.tooltip.padding = 10;
      p.tooltip.cornerRadius = 6;
      p.tooltip.titleFont = { weight: '600' };
    }
  }
};
