'use strict';
document.querySelectorAll('.copy-btn').forEach((button) => {
  // Cache the original markup exactly once. Copy requests may resolve out of order.
  const originalMarkup = button.innerHTML;
  let restoreTimer = null;
  let latestAttempt = 0;
  const status = document.createElement('span');
  status.className = 'visually-hidden';
  status.setAttribute('role', 'status');
  status.setAttribute('aria-live', 'polite');
  button.insertAdjacentElement('afterend', status);

  button.addEventListener('click', async () => {
    const value = button.dataset.copy;
    if (!value) return;
    const attempt = ++latestAttempt;
    let label;
    let announcement;
    try {
      await navigator.clipboard.writeText(value);
      label = 'Example URL copied ✓';
      announcement = 'Example URL copied to clipboard.';
    } catch (error) {
      label = 'Clipboard unavailable';
      announcement = 'Clipboard unavailable. You can inspect the example URL in the API.';
    }
    // Ignore stale asynchronous completions from older clicks.
    if (attempt !== latestAttempt) return;
    if (restoreTimer !== null) clearTimeout(restoreTimer);
    button.textContent = label;
    status.textContent = announcement;
    restoreTimer = setTimeout(() => {
      button.innerHTML = originalMarkup;
      restoreTimer = null;
    }, 1900);
  });
});
