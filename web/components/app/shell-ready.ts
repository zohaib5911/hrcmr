/**
 * Whether the signed-in shell has been on screen in this browser tab. The first load shows the
 * workspace splash; later page loads show a skeleton inside the shell (see route-loading.tsx).
 * Module state on purpose: it lives exactly as long as the tab's JavaScript.
 */
let ready = false;

export function markShellReady() {
  ready = true;
}

export function isShellReady() {
  return ready;
}
