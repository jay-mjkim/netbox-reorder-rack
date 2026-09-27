// Rack totals (PSU rating, measured peak, weight) computed from the items currently
// on a grid, so they track the drag before anything is saved.

function fmt(n) {
  return Math.round(n).toLocaleString();
}

function setLevel(el, used, limit) {
  el.classList.remove('warn', 'over');
  if (!limit) return;
  if (used > limit) el.classList.add('over');
  else if (used > limit * 0.8) el.classList.add('warn');
}

// Sum one grid's items. Items on the other face ('back' shadows) are skipped so a
// full-depth device is counted once.
export function sumGrid(gridEl) {
  var rated = 0, peak = 0, weight = 0, unmeasured = 0;
  gridEl.querySelectorAll('.grid-stack-item').forEach(function (item) {
    if (item.getAttribute('data-item-face') === 'back') return;
    rated += parseFloat(item.getAttribute('data-rated')) || 0;
    weight += parseFloat(item.getAttribute('data-weight')) || 0;
    var p = item.getAttribute('data-peak');
    if (p) peak += parseFloat(p) || 0; else unmeasured += 1;
  });
  return { rated: rated, peak: peak, weight: weight, unmeasured: unmeasured };
}

// Render totals for a rack into its stats block. `gridEls` are the grids that
// belong to that rack (one in the row view, front + rear in the rack view).
export function renderStats(statsEl, gridEls) {
  var t = { rated: 0, peak: 0, weight: 0, unmeasured: 0 };
  var seen = {};
  gridEls.forEach(function (g) {
    g.querySelectorAll('.grid-stack-item').forEach(function (item) {
      if (item.getAttribute('data-item-face') === 'back') return;
      var id = item.getAttribute('gs-id');
      if (seen[id]) return;
      seen[id] = true;
      t.rated += parseFloat(item.getAttribute('data-rated')) || 0;
      t.weight += parseFloat(item.getAttribute('data-weight')) || 0;
      var p = item.getAttribute('data-peak');
      if (p) t.peak += parseFloat(p) || 0; else t.unmeasured += 1;
    });
  });
  var cap = parseFloat(statsEl.getAttribute('data-capacity')) || 0;
  var maxW = parseFloat(statsEl.getAttribute('data-max-weight')) || 0;

  var rated = statsEl.querySelector('.stat-rated');
  rated.querySelector('.val').textContent = fmt(t.rated) + 'W' + (cap ? ' (' + Math.round(t.rated / cap * 100) + '%)' : '');
  setLevel(rated, t.rated, cap);

  var peak = statsEl.querySelector('.stat-peak');
  peak.querySelector('.val').textContent = fmt(t.peak) + 'W' + (cap ? ' (' + Math.round(t.peak / cap * 100) + '%)' : '')
    + (t.unmeasured ? ' +' + t.unmeasured + '대 미측정' : '');
  setLevel(peak, t.peak, cap);

  var weight = statsEl.querySelector('.stat-weight');
  weight.querySelector('.val').textContent = (Math.round(t.weight * 10) / 10).toLocaleString() + 'kg' + (maxW ? ' (' + Math.round(t.weight / maxW * 100) + '%)' : '');
  setLevel(weight, t.weight, maxW);
}
