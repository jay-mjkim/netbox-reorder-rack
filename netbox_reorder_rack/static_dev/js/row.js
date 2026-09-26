// Row view: several racks side by side, one face, drag between any of them and
// the shared non-racked bin. One save carries every device to its new rack/unit.
import { GridStack } from 'gridstack';
import { createToast } from './toast';

var changesMade = false;
var grids = [];

function markChanged() {
  changesMade = true;
  document.getElementById('saveButton').removeAttribute('disabled');
}

function initializeGrid(element) {
  return GridStack.init({
    cellHeight: 11,
    margin: 0,
    marginBottom: 1,
    float: true,
    disableOneColumnMode: true,
    animate: true,
    removeTimeout: 100,
    disableResize: true,
    // Shadows of devices on the other face are locked in place; anything else may
    // land in any rack. Whether a full-depth device actually fits is the server's
    // call (Device.clean), same as the per-rack view.
    acceptWidgets: function (el) {
      return el.getAttribute('data-item-face') !== 'back';
    },
  }, element);
}

// gs-y (half-units from the top) -> NetBox unit number for this grid's rack.
function unitPosition(item, gridEl) {
  var y = parseInt(item.getAttribute('gs-y')) / 2;
  var uHeight = parseInt(item.getAttribute('gs-h')) / 2;
  var rackHeight = parseInt(gridEl.getAttribute('gs-max-row')) / 2;
  if (gridEl.getAttribute('data-desc-units') === 'true') {
    return y + 1;
  }
  return uHeight > 1 ? rackHeight - y - uHeight + 1 : rackHeight - y;
}

function collectItems() {
  var items = [];
  grids.forEach(function (grid) {
    var gridEl = grid.el;
    var isRack = gridEl.getAttribute('data-grid-kind') === 'rack';
    grid.getGridItems().forEach(function (item) {
      if (item.getAttribute('data-item-face') === 'back') return;
      items.push({
        id: parseInt(item.getAttribute('gs-id')),
        rack_id: parseInt(isRack ? gridEl.getAttribute('data-rack-id') : item.getAttribute('data-rack-id')),
        y: isRack ? unitPosition(item, gridEl) : null,
        face: isRack ? rowFace : '',
      });
    });
  });
  return items;
}

function saveRow() {
  var button = document.getElementById('saveButton');
  button.setAttribute('disabled', 'disabled');

  fetch('/' + basePath + 'api/plugins/reorder/save-row/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': netbox_csrf_token,
    },
    body: JSON.stringify({ items: collectItems() }),
  }).then(function (response) {
    if (response.ok) {
      changesMade = false;
      window.location.reload();
    } else if (response.status === 304) {
      createToast('warning', 'Info', 'No changes were detected.').show();
    } else {
      button.removeAttribute('disabled');
      response.json().then(function (errorData) {
        createToast('danger', 'Error', errorData.error, errorData.message).show();
      }).catch(function () {
        createToast('danger', 'Error', 'Save failed (' + response.status + ')').show();
      });
    }
  }).catch(function (error) {
    button.removeAttribute('disabled');
    createToast('danger', 'Error', String(error)).show();
  });
}

document.querySelectorAll('.grid-stack').forEach(function (el) {
  grids.push(initializeGrid(el));
});

grids.forEach(function (grid) {
  grid.on('change', markChanged);
  grid.on('dropped', function (event, previousWidget, newWidget) {
    markChanged();
    var gridEl = newWidget.grid.el;
    var el = newWidget.el;
    var content = el.querySelector('.grid-stack-item-content');
    if (gridEl.getAttribute('data-grid-kind') === 'rack') {
      el.setAttribute('data-item-face', rowFace);
      el.setAttribute('data-rack-id', gridEl.getAttribute('data-rack-id'));
    } else {
      // Dropped into the non-racked bin: stays assigned to the rack it came from.
      el.setAttribute('data-item-face', 'none');
    }
    if (content && !content.style.backgroundImage) {
      content.style.backgroundColor = '#' + el.getAttribute('data-item-color');
      content.style.color = '#' + el.getAttribute('data-item-text-color');
    }
  });
});

document.getElementById('saveButton').addEventListener('click', saveRow);

window.addEventListener('beforeunload', function (event) {
  if (changesMade) {
    event.returnValue = 'Are you sure you want to leave? Changes you made may not be saved.';
  }
});

document.getElementById('view-selector').addEventListener('change', function () {
  var url = new URL(window.location.href);
  url.searchParams.set('view', this.value);
  window.location.href = url.toString();
});
