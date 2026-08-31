// Helpers compartidos E2E — Central Mutuos (SPA: login en "/", módulos por sidebar, sin rutas /login)
import { expect } from '@playwright/test';

export const ADMIN_USER = process.env.TEST_ADMIN_USER || 'administrador';
export const ADMIN_PASS = process.env.TEST_ADMIN_PASS || '141617575';

export async function login(page, user = ADMIN_USER, pass = ADMIN_PASS) {
  await page.goto('/');
  await page.getByTestId('login-rut').fill(user);
  await page.getByTestId('login-password').fill(pass);
  await page.getByTestId('login-submit').click();
  await expect(page.getByTestId('sidebar')).toBeVisible({ timeout: 20000 });
  await dismissModals(page);
}

// Cierra el tour de bienvenida ("Saltar") y el Briefing Mañanero ("Comenzar jornada") si aparecen
export async function dismissModals(page) {
  for (let i = 0; i < 6; i++) {
    const saltar = page.locator('text=Saltar').first();
    const briefing = page.locator('text=Comenzar jornada').first();
    if (await saltar.isVisible().catch(() => false)) {
      await saltar.click({ force: true });
      await page.waitForTimeout(800);
    } else if (await briefing.isVisible().catch(() => false)) {
      await briefing.click({ force: true });
      await page.waitForTimeout(800);
    } else {
      break;
    }
  }
}

// Abre un módulo del sidebar expandiendo su supermódulo si hace falta (con reintentos verificados)
export async function abrirModulo(page, smKey, modKey, targetTestId) {
  for (let intento = 0; intento < 4; intento++) {
    await dismissModals(page);
    const nav = page.getByTestId(`nav-${modKey}`);
    if (!(await nav.isVisible().catch(() => false))) {
      await page.getByTestId(`sm-toggle-${smKey}`).click({ force: true });
      await page.waitForTimeout(600);
    }
    await nav.click({ force: true });
    await page.waitForTimeout(1500);
    await dismissModals(page);
    if (!targetTestId) return;
    if (await page.getByTestId(targetTestId).isVisible().catch(() => false)) return;
    await page.waitForTimeout(2000);
    if (await page.getByTestId(targetTestId).isVisible().catch(() => false)) return;
  }
}
