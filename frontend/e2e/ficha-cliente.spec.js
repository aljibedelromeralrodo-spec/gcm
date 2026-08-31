import { test, expect } from '@playwright/test';
import { login, abrirModulo, dismissModals } from './helpers';

test('login -> abrir ficha Victoria sin que el polling de 45s borre la edición', async ({ page }) => {
  await login(page);

  // Módulo Victoria Vilches (supermódulo Control y Postventa)
  await abrirModulo(page, 'sm_control', 'mod_victoria');
  await expect(page.getByTestId('victoria-dashboard')).toBeVisible({ timeout: 20000 });

  // Abre la primera ficha de cliente
  const abrir = page.locator('[data-testid^="cliente-abrir-"]').first();
  await expect(abrir).toBeVisible({ timeout: 15000 });
  await abrir.click({ force: true });
  await expect(page.getByTestId('victoria-ficha')).toBeVisible({ timeout: 20000 });

  // Paso 2: formularios auto-rellenados (los inputs del hook con eslint-disable)
  await page.getByTestId('stepper-paso-2').click({ force: true });
  const input = page.locator('[data-testid^="form-"]').first();
  await expect(input).toBeVisible({ timeout: 15000 });

  // Anti-regresión: el poll de 45s NO debe borrar lo que el usuario escribe
  await input.fill('TEST EDICION NO BORRAR');
  await expect(input).toHaveValue('TEST EDICION NO BORRAR');
  await page.waitForTimeout(50000); // un ciclo de polling (45s) + margen
  await dismissModals(page);
  await expect(input).toHaveValue('TEST EDICION NO BORRAR'); // si falla, el hook reseteó el form
});
