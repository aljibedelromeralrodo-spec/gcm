# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: login-clientes.spec.js >> login admin -> dashboard + modulo clientes renderiza (split BrokersPanel/UFAmountInput OK)
- Location: e2e/login-clientes.spec.js:4:5

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