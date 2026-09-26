// Import Toast directly rather than from 'bootstrap': the package entry point pulls in
// every component, including the ones that require @popperjs/core (a peer dependency
// this plugin does not declare), so the build only succeeded when a package manager
// happened to auto-install that peer. Toast needs no popper.
import Toast from 'bootstrap/js/dist/toast.js';

// Bootstrap toast in NetBox's style, shared by the rack and row pages.
export function createToast(level, title, message, extra) {
  let iconName = 'mdi-alert';
  switch (level) {
    case 'success':
      iconName = 'mdi-check-circle';
      break;
    case 'info':
      iconName = 'mdi-information';
      break;
  }

  const container = document.createElement('div');
  container.setAttribute('class', 'toast-container position-fixed bottom-0 end-0 m-3');

  const main = document.createElement('div');
  main.setAttribute('class', 'toast');
  main.setAttribute('role', 'alert');
  main.setAttribute('aria-live', 'assertive');
  main.setAttribute('aria-atomic', 'true');

  const header = document.createElement('div');
  header.setAttribute('class', `toast-header bg-${level} text-dark`);

  const icon = document.createElement('i');
  icon.setAttribute('class', `mdi ${iconName}`);

  const titleElement = document.createElement('strong');
  titleElement.setAttribute('class', 'me-auto ms-1');
  titleElement.innerText = title;

  const button = document.createElement('button');
  button.setAttribute('type', 'button');
  button.setAttribute('class', 'btn-close');
  button.setAttribute('data-bs-dismiss', 'toast');
  button.setAttribute('aria-label', 'Close');

  const body = document.createElement('div');
  body.setAttribute('class', 'toast-body text-dark');
  body.innerText = (message || '').trim();

  header.appendChild(icon);
  header.appendChild(titleElement);
  if (typeof extra !== 'undefined') {
    const extraElement = document.createElement('small');
    extraElement.setAttribute('class', 'text-dark');
    extraElement.innerText = extra;
    header.appendChild(extraElement);
  }
  header.appendChild(button);

  main.appendChild(header);
  main.appendChild(body);
  container.appendChild(main);
  document.body.appendChild(container);

  return new Toast(main);
}
