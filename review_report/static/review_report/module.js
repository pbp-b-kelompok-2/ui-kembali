document.body.addEventListener('htmx:beforeSwap', function (event) {
  if (event.detail.target.id !== 'rr-content') return;
  if ([403, 409, 422].includes(event.detail.xhr.status)) {
    event.detail.shouldSwap = true;
    event.detail.isError = false;
  }
});
document.body.addEventListener('htmx:afterSwap', function (event) {
  if (event.detail.target.id === 'rr-content') {
    const content = document.getElementById('rr-content');
    const error = content.querySelector('[role="alert"]');
    if (error) {
      error.setAttribute('tabindex', '-1');
      error.focus();
    } else content.focus({preventScroll: true});
  }
});
