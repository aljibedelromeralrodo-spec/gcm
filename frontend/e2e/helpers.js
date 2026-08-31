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
  for (let intento = 0; intento < 6; intento++) {
    await dismissModals(page);
    const nav = page.getByTestId(`nav-${modKey}`);
    if (!(await nav.isVisible().catch(() => false))) {
      await page.getByTestId(`sm-toggle-${smKey}`).click({ force: true, timeout: 5000 }).catch(() => {});
      await page.waitForTimeout(700);
    }
    await nav.click({ force: true, timeout: 5000 }).catch(() => {});
    await dismissModals(page);
    if (!targetTestId) return;
    // espera hasta 8s a que el módulo (lazy) termine de cargar
    const ok = await page.getByTestId(targetTestId).waitFor({ state: 'visible', timeout: 8000 })
      .then(() => true).catch(() => false);
    if (ok) return;
  }
}
