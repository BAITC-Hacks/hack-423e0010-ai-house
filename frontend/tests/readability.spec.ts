import {expect, test, type Page} from '@playwright/test';

// Audit rendered text and control values against their actual solid backgrounds.
// The welcome illustration is decorative; its gradient is checked separately.
async function auditText(page: Page) {
  const failures = await page.evaluate(() => {
    const rgb = (color: string) => (color.match(/[\d.]+/g) ?? []).map(Number);
    const luminance = (color: number[]) => color.slice(0, 3).map(v => {
      const s = v / 255;
      return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
    }).reduce((sum, v, i) => sum + v * [0.2126, 0.7152, 0.0722][i], 0);
    const composite = (front: number[], back: number[]) => {
      const alpha = front[3] ?? 1;
      return front.slice(0, 3).map((v, i) => v * alpha + back[i] * (1 - alpha));
    };
    const background = (el: Element): number[] => {
      const style = getComputedStyle(el);
      const color = rgb(style.backgroundColor);
      if (style.backgroundImage !== 'none') throw new Error(`Unsupported background: ${el.className}`);
      return composite(color, el.parentElement ? background(el.parentElement) : [255, 255, 255]);
    };
    const failures: string[] = [];
    for (const el of document.querySelectorAll('body *')) {
      if (!(el instanceof HTMLElement) || !el.checkVisibility({checkVisibilityCSS: true, checkOpacity: true})) continue;
      if (el.closest('svg, script, style, .welcome-illustration, :disabled')) continue;
      const hasText = [...el.childNodes].some(n => n.nodeType === Node.TEXT_NODE && n.textContent?.trim());
      const control = el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement || el instanceof HTMLSelectElement;
      if (!hasText && !control) continue;
      if (el instanceof HTMLInputElement && ['checkbox', 'radio', 'hidden'].includes(el.type)) continue;
      const style = getComputedStyle(el);
      const size = parseFloat(style.fontSize);
      if (size === 0) continue; // Mobile navigation uses icons with accessible labels.
      const label = `${el.tagName}.${el.className}: ${(el.textContent || el.getAttribute('aria-label') || '').slice(0, 45)}`;
      if (size < 13) failures.push(`${label}: ${size}px`);
      // Check both ends of the welcome panel's gradient, instead of assuming white.
      const backgrounds = el.closest('.welcome') ? [[252, 253, 249], [248, 250, 244]] : [background(el)];
      const colors = [style.color];
      if ((el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) && el.placeholder) colors.push(getComputedStyle(el, '::placeholder').color);
      for (const bg of backgrounds) for (const color of colors) {
        const fgL = luminance(composite(rgb(color), bg));
        const bgL = luminance(bg);
        const ratio = (Math.max(fgL, bgL) + 0.05) / (Math.min(fgL, bgL) + 0.05);
        if (ratio < 4.5) failures.push(`${label}: contrast ${ratio.toFixed(2)}:1`);
      }
    }
    return failures;
  });
  expect(failures).toEqual([]);
}

test('text remains readable across results, assistant, profile, comparison and history', async ({page}) => {
  await page.goto('/');
  const search = page.getByRole('button', {name: 'Найти совпадения'});
  await expect(search).toBeEnabled();
  await auditText(page);
  await search.click();
  const cards = page.getByTestId('contractor-card');
  await expect(cards).toHaveCount(3);
  await cards.first().locator('.evidence summary').click();
  await page.getByLabel('Сообщение помощнику').fill('Сравни варианты');
  await page.getByRole('button', {name: 'Отправить сообщение'}).click();
  await expect(page.locator('.message.assistant')).not.toHaveCount(0);
  await expect(search).toBeEnabled();
  await auditText(page);
  for (const selector of ['.message', '.explanation p']) {
    const values = await page.locator(selector).first().evaluate(el => {
      const style = getComputedStyle(el);
      return {size: parseFloat(style.fontSize), line: parseFloat(style.lineHeight)};
    });
    expect(values.size).toBeGreaterThanOrEqual(15);
    expect(values.line / values.size).toBeCloseTo(1.5);
  }
  await page.screenshot({path: '../data/screenshots/readability-desktop.png', fullPage: true});
  await cards.first().locator('.name-button').click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await auditText(page);
  await page.keyboard.press('Escape');
  await cards.nth(0).getByRole('checkbox').check();
  await cards.nth(1).getByRole('checkbox').check();
  await page.locator('.compare-bar button').click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await auditText(page);
  await page.keyboard.press('Escape');
  await page.getByRole('button', {name: /История/}).click();
  await expect(page.locator('.history-row')).toHaveCount(1);
  await auditText(page);
});

for (const width of [320, 390, 768, 1024, 1280, 1600]) {
  test(`readable layout at ${width}px without horizontal overflow`, async ({page}) => {
    await page.setViewportSize({width, height: 900});
    await page.goto('/');
    await page.getByRole('button', {name: 'Найти совпадения'}).click();
    await expect(page.getByTestId('contractor-card')).toHaveCount(3);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    await auditText(page);
    if (width < 1251) await page.getByRole('button', {name: 'Помощник', exact: true}).click();
    await expect(page.getByLabel('Сообщение помощнику')).toBeInViewport();
    await expect(page.getByRole('button', {name: 'Отправить сообщение'})).toBeInViewport();
    expect(await page.locator('.chat-content').evaluate(el => el.clientHeight)).toBeGreaterThan(100);
    await auditText(page);
    if (width === 390) await page.screenshot({path: '../data/screenshots/readability-mobile-chat.png'});
  });
}
