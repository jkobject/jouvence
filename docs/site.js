document.querySelectorAll('.copy-button').forEach((button) => {
  button.addEventListener('click', async () => {
    const target = document.getElementById(button.dataset.copyTarget);
    if (!target) return;

    const text = target.textContent.trim();
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const textarea = document.createElement('textarea');
      textarea.value = text;
      textarea.setAttribute('readonly', '');
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      textarea.remove();
    }

    const previousLabel = button.textContent;
    button.textContent = button.dataset.copiedLabel || 'Copied';
    button.classList.add('is-copied');
    window.setTimeout(() => {
      button.textContent = previousLabel;
      button.classList.remove('is-copied');
    }, 1600);
  });
});
