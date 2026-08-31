# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: ficha-cliente.spec.js >> login -> abrir ficha Victoria sin que el polling de 45s borre la edición
- Location: e2e/ficha-cliente.spec.js:8:5

# Error details

```
Error: browserType.launch: Executable doesn't exist at /pw-browsers/chromium_headless_shell-1234/chrome-linux/headless_shell
╔════════════════════════════════════════════════════════════╗
║ Looks like Playwright was just installed or updated.       ║
║ Please run the following command to download new browsers: ║
║                                                            ║
║     npx playwright install                                 ║
║                                                            ║
║ <3 Playwright Team                                         ║
╚════════════════════════════════════════════════════════════╝
```