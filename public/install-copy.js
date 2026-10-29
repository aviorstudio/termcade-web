const resets = new WeakMap();

function copyWithSelection(text) {
	const previousFocus = document.activeElement;
	const field = document.createElement('textarea');
	field.value = text;
	field.readOnly = true;
	field.tabIndex = -1;
	field.setAttribute('aria-hidden', 'true');
	field.style.cssText = 'position:fixed;top:0;left:0;width:1px;height:1px;opacity:0';
	document.body.append(field);
	try {
		field.select();
		if (!document.execCommand('copy')) throw new Error('Copy unavailable');
	} finally {
		field.remove();
		if (previousFocus instanceof HTMLElement) previousFocus.focus({ preventScroll: true });
	}
}

async function writeCommand(text) {
	if (navigator.clipboard?.writeText) {
		try {
			await navigator.clipboard.writeText(text);
			return;
		} catch {
			// Older browsers and denied clipboard permissions can still allow selection-based copying.
		}
	}
	copyWithSelection(text);
}

for (const button of document.querySelectorAll('[data-copy-command]')) button.hidden = false;

document.addEventListener('click', async (event) => {
	if (!(event.target instanceof Element)) return;
	const button = event.target.closest('[data-copy-command]');
	if (!(button instanceof HTMLButtonElement) || button.disabled || button.getAttribute('aria-busy') === 'true') return;
	const row = button.closest('[data-install-command]');
	const code = row?.querySelector('code');
	const label = button.querySelector('[data-copy-label]');
	const status = row?.querySelector('[data-copy-status]');
	if (!code || !label || !status) return;

	clearTimeout(resets.get(button));
	button.setAttribute('aria-busy', 'true');
	try {
		await writeCommand(code.textContent ?? '');
		label.textContent = 'Copied!';
		status.textContent = 'Install command copied.';
		resets.set(
			button,
			setTimeout(() => {
				label.textContent = 'Copy';
				status.textContent = '';
			}, 2000),
		);
	} catch {
		label.textContent = 'Select text';
		status.textContent = 'Copy failed. Select and copy the command.';
		const range = document.createRange();
		range.selectNodeContents(code);
		const selection = window.getSelection();
		selection?.removeAllRanges();
		selection?.addRange(range);
	} finally {
		button.removeAttribute('aria-busy');
	}
});
