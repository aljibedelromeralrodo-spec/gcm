import asyncio, subprocess
from playwright.async_api import async_playwright

URL = "http://localhost:3000/martin-app.html"

PRE = """() => {
  const reg = {}; const hoy = new Date();
  const vals = [[12000,4000,'super'],[25000,0,'delivery'],[8000,6000,''],[15000,5000,'bencina'],[18000,7000,'feria']];
  for (let i=4;i>=0;i--){ const d=new Date(); d.setDate(hoy.getDate()-i);
    const k=d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');
    reg[k]={g:vals[4-i][0],a:vals[4-i][1],det:vals[4-i][2]}; }
  localStorage.setItem('ma_registro', JSON.stringify(reg));
  localStorage.setItem('ma_meta','30000');
  localStorage.setItem('ma_meta_celebrada', k => '');
  localStorage.setItem('ma_desafios', JSON.stringify({moneditas:['a','b','c','d'],'sin-delivery':['a','b'],hormiga:['a','b','c','d','e','f','g']}));
  localStorage.setItem('ma_fam', JSON.stringify({nom:'Vacaciones en la playa', monto:120000}));
  localStorage.setItem('ma_conciencia', JSON.stringify({nuevos:0, corto:[
    {f:'2026-08-22 09:10',q:'usuario',t:'Quiero empezar a ahorrar para mi casa propia',e:null},
    {f:'2026-08-22 09:10',q:'martin',t:'¡Qué buena meta! Partamos por el Registro Social de Hogares y una libreta de ahorro para la vivienda…',e:'entusiasmo'},
    {f:'2026-08-23 20:15',q:'evento',t:'Registró su día: gastó $15.000, ahorró $5.000 (en bencina)',e:null},
    {f:'2026-08-24 08:30',q:'martin',t:'Le noto con energía hoy, ¿ha pensado en su meta de la casa?',e:'entusiasmo'}],
    largo:{perfil:'Persona trabajadora, con familia, que sueña con la casa propia y está ordenando sus finanzas.',
      personalidad:'Perseverante y optimista', metas_pendientes:['Casa propia','Fondo de emergencia'],
      metas_cumplidas:['Primer mes registrando gastos'], patrones_emocionales:'Entusiasmo creciente',
      temas_recurrentes:['ahorro','vivienda'], resumen:'Ha registrado 5 días seguidos y va camino a su meta de ahorro mensual.', actualizado:'24-08-2026 08:30'}}));
}"""

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage", "--autoplay-policy=no-user-gesture-required"])
        ctx = await browser.new_context(viewport={"width": 390, "height": 780},
                                        record_video_dir="/app/vidwork/rec",
                                        record_video_size={"width": 390, "height": 780})
        page = await ctx.new_page()
        await page.goto(URL, wait_until="domcontentloaded")
        await page.evaluate(PRE)
        await page.reload(wait_until="networkidle")
        await asyncio.sleep(2)
        # A: registro diario (rellenar) ~ 5-12
        await page.fill("#reg-gasto", "14000")
        await asyncio.sleep(1.2)
        await page.fill("#reg-ahorro", "6000")
        await asyncio.sleep(4)
        # B: metas de ahorro (progreso) ~ 13-20
        await page.evaluate("document.getElementById('progreso').scrollIntoView({behavior:'smooth'})")
        await asyncio.sleep(7)
        # C: chat con Martín hablando ~ 21-29
        await page.evaluate("irChat()")
        await asyncio.sleep(0.6)
        await page.evaluate("""hablar('Cuénteme, ¿cómo le fue hoy con la plata? Yo le acompaño, sin juzgar, como buen amigo.')""")
        await asyncio.sleep(8)
        # D: módulos grid ~ 30-37
        await page.evaluate("irHome(true)")
        await asyncio.sleep(1)
        await page.evaluate("document.getElementById('grid').scrollIntoView({behavior:'smooth'})")
        await asyncio.sleep(2)
        await page.evaluate("document.querySelector('[data-testid=card-conciencia]').scrollIntoView({behavior:'smooth',block:'end'})")
        await asyncio.sleep(4)
        # E: Conciencia ~ 38-44
        await page.evaluate("abrirMod('conciencia')")
        await asyncio.sleep(2.5)
        await page.evaluate("document.getElementById('con-largo').scrollIntoView({behavior:'smooth'})")
        await asyncio.sleep(4)
        # F: Modo Crisis ~ 45-51
        await page.evaluate("abrirMod('crisis')")
        await asyncio.sleep(6.5)
        # G: Desafíos ~ 52-58
        await page.evaluate("abrirMod('desafios')")
        await asyncio.sleep(2)
        await page.evaluate("document.getElementById('des-lista').scrollIntoView({behavior:'smooth'})")
        await asyncio.sleep(4.5)
        # H: Modo Familia ~ 59-66
        await page.evaluate("abrirMod('familia')")
        await asyncio.sleep(3)
        await page.evaluate("document.getElementById('fam-meta').scrollIntoView({behavior:'smooth'})")
        await asyncio.sleep(4)
        video = page.video
        await ctx.close()
        path = await video.path()
        await browser.close()
        subprocess.run(["mv", path, "/app/vidwork/rec_app.webm"], check=True)
        print("grabado rec_app.webm")

asyncio.run(main())
