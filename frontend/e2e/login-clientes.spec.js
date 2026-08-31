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
