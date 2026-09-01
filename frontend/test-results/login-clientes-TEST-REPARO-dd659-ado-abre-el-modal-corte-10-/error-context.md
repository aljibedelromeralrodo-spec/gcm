# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: login-clientes.spec.js >> TEST REPAROS: el botón de reparos del abogado abre el modal (corte 10)
- Location: e2e/login-clientes.spec.js:19:5

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByTestId('sidebar')
Expected: visible
Timeout: 20000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" with timeout 20000ms
  - waiting for getByTestId('sidebar')

```

```yaml
- text: CENTRAL MUTUOS CON CRECES Código de Acceso
- textbox "Ingrese su código": administrador
- text: Contraseña
- textbox "Ingrese su contraseña": "141617575"
- button "Verificando..." [disabled]
- paragraph: Central Mutuos · Con Creces
```

# Test source

```ts
  1  | // Helpers compartidos E2E — Central Mutuos (SPA: login en "/", módulos por sidebar, sin rutas /login)
  2  | import { expect } from '@playwright/test';
  3  | 
  4  | export const ADMIN_USER = process.env.TEST_ADMIN_USER || 'administrador';
  5  | export const ADMIN_PASS = process.env.TEST_ADMIN_PASS || '141617575';
  6  | 
  7  | export async function login(page, user = ADMIN_USER, pass = ADMIN_PASS) {
  8  |   await page.goto('/');
  9  |   await page.getByTestId('login-rut').fill(user);
  10 |   await page.getByTestId('login-password').fill(pass);
  11 |   await page.getByTestId('login-submit').click();
> 12 |   await expect(page.getByTestId('sidebar')).toBeVisible({ timeout: 20000 });
     |                                             ^ Error: expect(locator).toBeVisible() failed
  13 |   await dismissModals(page);
  14 | }
  15 | 
  16 | // Cierra el tour de bienvenida ("Saltar") y el Briefing Mañanero ("Comenzar jornada") si aparecen
  17 | export async function dismissModals(page) {
  18 |   for (let i = 0; i < 6; i++) {
  19 |     const saltar = page.locator('text=Saltar').first();
  20 |     const briefing = page.locator('text=Comenzar jornada').first();
  21 |     if (await saltar.isVisible().catch(() => false)) {
  22 |       await saltar.click({ force: true });
  23 |       await page.waitForTimeout(800);
  24 |     } else if (await briefing.isVisible().catch(() => false)) {
  25 |       await briefing.click({ force: true });
  26 |       await page.waitForTimeout(800);
  27 |     } else {
  28 |       break;
  29 |     }
  30 |   }
  31 | }
  32 | 
  33 | // Abre un módulo del sidebar expandiendo su supermódulo si hace falta (con reintentos verificados)
  34 | export async function abrirModulo(page, smKey, modKey, targetTestId) {
  35 |   for (let intento = 0; intento < 6; intento++) {
  36 |     await dismissModals(page);
  37 |     const nav = page.getByTestId(`nav-${modKey}`);
  38 |     if (!(await nav.isVisible().catch(() => false))) {
  39 |       await page.getByTestId(`sm-toggle-${smKey}`).click({ force: true, timeout: 5000 }).catch(() => {});
  40 |       await page.waitForTimeout(700);
  41 |     }
  42 |     await nav.click({ force: true, timeout: 5000 }).catch(() => {});
  43 |     await dismissModals(page);
  44 |     if (!targetTestId) return;
  45 |     // espera hasta 8s a que el módulo (lazy) termine de cargar
  46 |     const ok = await page.getByTestId(targetTestId).waitFor({ state: 'visible', timeout: 8000 })
  47 |       .then(() => true).catch(() => false);
  48 |     if (ok) return;
  49 |   }
  50 | }
  51 | 
```