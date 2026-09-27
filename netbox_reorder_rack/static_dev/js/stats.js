// Capacity lanes beside each elevation and the totals under it, all derived from the
// grid items currently on screen so they follow a drag before anything is saved.

var LANES = ['weight', 'rated', 'peak'];
var STORAGE_KEY = 'netbox_reorder_rack.lanes';

function fmtInt(n) {
  return Math.round(n).toLocaleString();
}

function fmtKg(n) {
  return (Math.round(n * 10) / 10).toLocaleString();
}

function laneText(item, lane) {
  var v = item.getAttribute('data-' + lane);
  if (!v) return null;
  var n = parseFloat(v);
  if (isNaN(n)) return null;
  return lane === 'weight' ? fmtKg(n) : fmtInt(n);
}

// One cell per device in each lane, aligned to the device's slot in the grid.
export function renderLanes(elevationEl) {
  var grid = elevationEl.querySelector('.grid-stack');
  if (!grid) return;
  var height = grid.offsetHeight;
  elevationEl.querySelectorAll('.lane').forEach(function (lane) {
    var key = lane.getAttribute('data-lane');
    lane.style.height = height + 'px';
    lane.textContent = '';
    grid.querySelectorAll('.grid-stack-item').forEach(function (item) {
      if (item.getAttribute('data-item-face') === 'back') return;
      var cell = document.createElement('div');
      cell.className = 'lane-cell';
      cell.style.top = item.offsetTop + 'px';
      cell.style.height = item.offsetHeight + 'px';
      var text = laneText(item, key);
      if (text === null) {
        cell.classList.add('empty');
        cell.textContent = '–';
        cell.title = key === 'peak' ? 'not measured' : 'unknown';
      } else {
        cell.textContent = text;
        if (key === 'rated' && item.getAttribute('data-psu')) cell.title = item.getAttribute('data-psu');
      }
      lane.appendChild(cell);
    });
  });
}

function level(used, limit) {
  if (!limit) return '';
  if (used > limit) return 'over';
  if (used > limit * 0.8) return 'warn';
  return 'ok';
}

function paintStat(statEl, used, limit, unit, overText) {
  if (!statEl) return;
  var lvl = level(used, limit);
  statEl.classList.remove('ok', 'warn', 'over');
  if (lvl) statEl.classList.add(lvl);
  var bar = statEl.querySelector('.progress-bar');
  bar.classList.remove('bg-success', 'bg-warning', 'bg-danger');
  bar.classList.add(lvl === 'over' ? 'bg-danger' : lvl === 'warn' ? 'bg-warning' : 'bg-success');
  bar.style.width = (limit ? Math.min(100, Math.round(used / limit * 100)) : 0) + '%';
  bar.setAttribute('aria-valuenow', limit ? Math.round(used / limit * 100) : 0);
  var over = statEl.querySelector('.stat-over');
  if (lvl === 'over') {
    over.querySelector('.over-by').textContent = overText + ' +' + (unit === 'kg' ? fmtKg(used - limit) : fmtInt(used - limit)) + ' ' + unit;
    over.hidden = false;
  } else {
    over.hidden = true;
  }
  return lvl;
}

// Totals for one rack from the grids that belong to it (one in the row view, front and
// rear in the rack view); a full-depth device shows on both faces but is counted once.
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

  var levels = [];
  var w = statsEl.querySelector('.stat-weight');
  w.querySelector('.val').textContent = fmtKg(t.weight);
  levels.push(['weight', paintStat(w, t.weight, maxW, 'kg', 'over')]);

  var r = statsEl.querySelector('.stat-rated');
  r.querySelector('.val').textContent = fmtInt(t.rated);
  levels.push(['rated', paintStat(r, t.rated, cap, 'W', 'over')]);

  var p = statsEl.querySelector('.stat-peak');
  if (p) {
    p.querySelector('.val').textContent = fmtInt(t.peak);
    levels.push(['peak', paintStat(p, t.peak, cap, 'W', 'over')]);
    var note = p.querySelector('.stat-note');
    if (t.unmeasured) {
      note.textContent = '+' + t.unmeasured + ' not measured';
      note.hidden = false;
    } else {
      note.hidden = true;
    }
  }

  // The card as a whole: red border and a badge naming what is over. Lanes the user
  // has hidden are left out, so the badge only ever names something on screen.
  var card = statsEl.closest('.reorder-rack-card');
  if (card) {
    var root = card.closest('.reorder-row') || document.body;
    var over = levels.filter(function (l) {
      return l[1] === 'over' && !root.classList.contains('hide-lane-' + l[0]);
    }).map(function (l) { return l[0]; });
    card.classList.toggle('over-limit', over.length > 0);
    var badge = card.querySelector('.rack-over-badge');
    if (badge) {
      badge.textContent = over.join(' · ') + ' over';
      badge.hidden = over.length === 0;
    }
  }
}

// Lane visibility toggles, remembered per browser.
export function initLaneToggles(rootEl, onChange) {
  var saved = {};
  try { saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}'); } catch (e) { saved = {}; }
  var inputs = document.querySelectorAll('.lane-toggles input[data-lane]');
  function apply() {
    var state = {};
    inputs.forEach(function (input) {
      var lane = input.getAttribute('data-lane');
      state[lane] = input.checked;
      rootEl.classList.toggle('hide-lane-' + lane, !input.checked);
    });
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); } catch (e) { /* private mode */ }
    if (onChange) onChange();
  }
  inputs.forEach(function (input) {
    var lane = input.getAttribute('data-lane');
    if (typeof saved[lane] === 'boolean') input.checked = saved[lane];
    input.addEventListener('change', apply);
  });
  apply();
}

export { LANES };
