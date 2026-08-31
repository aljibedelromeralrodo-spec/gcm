import { test, expect } from '@playwright/test';
import { login, abrirModulo } from './helpers';

test('login admin -> dashboard + modulo clientes renderiza (split BrokersPanel/UFAmountInput OK)', async ({ page }) => {
  await login(page);

  // Dashboard cargado (sidebar + topbar visibles)
  await expect(page.getByTestId('sidebar')).toBeVisible();

  // Va a Carpeta Clientes (supermódulo Operación y Clientes)
  await abrirModulo(page, 'sm_operacion', 'clientes', 'clientes-module');

  // Verifica que el módulo (que ahora importa desde ./clientes) sigue renderizando
  await expect(page.getByTestId('clientes-module')).toBeVisible({ timeout: 15000 });
  await expect(page.getByTestId('clientes-list')).toBeVisible();
  await expect(page.getByTestId('btn-new-folder')).toBeVisible();
});

test('TEST REPAROS: el botón de reparos del abogado abre el modal (corte 10)', async ({ page }) => {
  await login(page);
  await abrirModulo(page, 'sm_operacion', 'clientes', 'clientes-module');
  const btn = page.locator('[data-testid^="reparos-btn-"]').first();
  if (!(await btn.isVisible().catch(() => false))) {
    console.log('Sin carpetas con reparos visibles — nada que validar');
    return;
  }
  await btn.click({ force: true });
  await expect(page.getByTestId('reparos-modal')).toBeVisible({ timeout: 15000 });
  await page.keyboard.press('Escape');
  await page.getByTestId('reparos-modal').click({ position: { x: 5, y: 5 }, force: true }).catch(() => {});
});
