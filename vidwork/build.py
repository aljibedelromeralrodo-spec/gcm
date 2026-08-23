import asyncio, json, subprocess, math
from playwright.async_api import async_playwright

W, H = 1280, 720
URL = "http://localhost:3000/martin-app.html"
durs = json.load(open("/app/vidwork/durs.json"))
IMGS = ["v_familia", "v_duena", "v_emprende", "v_casa", "v_abuela", "v_soledad"]

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-1500:]); raise SystemExit(1)

def apertura():
    n = len(IMGS)
    total = durs["ap"] + 1.0
    xf = 1.4
    per = (total + xf * (n - 1)) / n
    ins, filt = [], []
    for i, s in enumerate(IMGS):
        ins += ["-loop", "1", "-t", f"{per:.2f}", "-i", f"/app/vidwork/{s}.jpeg"]
        filt.append(f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,zoompan=z='min(zoom+0.0006,1.08)':d={int(per*25)}:s={W}x{H}:fps=25[v{i}]")
    prev = "v0"
    off = per - xf
    for i in range(1, n):
        out = f"x{i}"
        filt.append(f"[{prev}][v{i}]xfade=transition=fade:duration={xf}:offset={off:.2f}[{out}]")
        prev = out
        off += per - xf
    run(["ffmpeg", "-y", *ins, "-i", "/app/vidwork/aud_ap.mp3",
         "-filter_complex", ";".join(filt), "-map", f"[{prev}]", "-map", f"{n}:a",
         "-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "fast", "-crf", "22",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-af", "apad", "-shortest",
         "/app/vidwork/seg_ap.mp4"])
    print("apertura OK")

async def grabar(pw, name, seconds, acciones):
    browser = await pw.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
    ctx = await browser.new_context(viewport={"width": 390, "height": 780},
                                    record_video_dir="/app/vidwork/rec",
                                    record_video_size={"width": 390, "height": 780})
    page = await ctx.new_page()
    await page.goto(URL, wait_until="networkidle")
    await asyncio.sleep(2)
    try:
        await acciones(page, seconds)
    except Exception as e:
        print("accion warn", name, e)
    video = page.video
    await ctx.close()
    path = await video.path()
    await browser.close()
    subprocess.run(["mv", path, f"/app/vidwork/rec_{name}.webm"], check=True)
    print("grabado", name)

async def acc1(page, s):
    await page.fill("#reg-gasto", "18000")
    await asyncio.sleep(1)
    await page.fill("#reg-ahorro", "3000")
    await asyncio.sleep(1.2)
    await page.click('[data-testid="reg-guardar"]', force=True)
    await asyncio.sleep(6)
    await page.evaluate("document.getElementById('progreso').scrollIntoView({behavior:'smooth'})")
    await asyncio.sleep(3)
    await page.evaluate("document.getElementById('grid').scrollIntoView({behavior:'smooth'})")
    await asyncio.sleep(3)
    await page.click('[data-testid="card-partida"]', force=True)
    await asyncio.sleep(3.5)
    await page.click('[data-testid="btn-volver"]', force=True)
    await page.click('[data-testid="card-presupuesto"]', force=True)
    await asyncio.sleep(max(s - 20, 4))

async def acc2(page, s):
    await page.evaluate("document.getElementById('grid').scrollIntoView()")
    await page.click('[data-testid="card-deudas"]', force=True)
    await asyncio.sleep(4)
    await page.click('[data-testid="btn-volver"]', force=True)
    await page.click('[data-testid="card-casa"]', force=True)
    await asyncio.sleep(2)
    accs = await page.locator(".acc>b").all()
    for a in accs[:3]:
        await a.click(force=True)
        await asyncio.sleep(2.2)
    await page.evaluate("document.getElementById('v-mod').scrollBy({top:400,behavior:'smooth'})")
    await asyncio.sleep(3)
    await page.click('[data-testid="btn-volver"]', force=True)
    await page.click('[data-testid="card-emprender"]', force=True)
    await asyncio.sleep(max(s - 16, 4))

async def acc3(page, s):
    await page.evaluate("document.getElementById('grid').scrollIntoView()")
    await page.click('[data-testid="card-quererme"]', force=True)
    await asyncio.sleep(3.5)
    await page.click('[data-testid="btn-volver"]', force=True)
    await page.click('[data-testid="card-experiencias"]', force=True)
    await asyncio.sleep(4)
    await page.click('[data-testid="btn-volver"]', force=True)
    await page.click('[data-testid="card-conciencia"]', force=True)
    await asyncio.sleep(4)
    await page.click('[data-testid="btn-volver"]', force=True)
    await page.click('[data-testid="nav-chat"]', force=True)
    await asyncio.sleep(max(s - 16, 3))

def montar(name):
    d = durs[name] + 0.8
    run(["ffmpeg", "-y", "-i", f"/app/vidwork/rec_t{name[-1]}.webm", "-i", f"/app/vidwork/aud_{name}.mp3",
         "-filter_complex", f"[0:v]scale=-2:720,pad={W}:720:(ow-iw)/2:0:color=0x101E5E,setsar=1[v]",
         "-map", "[v]", "-map", "1:a", "-t", f"{d:.2f}",
         "-c:v", "libx264", "-preset", "fast", "-crf", "22", "-r", "25", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "160k", "-af", "apad", "-shortest", f"/app/vidwork/seg_{name}.mp4"])
    print("mux", name)

async def cierre_shot(pw):
    browser = await pw.chromium.launch(args=["--no-sandbox"])
    page = await browser.new_page(viewport={"width": W, "height": 720})
    await page.goto("file:///app/vidwork/cierre.html")
    await page.wait_for_timeout(2500)
    await page.screenshot(path="/app/vidwork/cierre.png")
    await browser.close()

def montar_cierre():
    d = durs["fin"] + 2.0
    run(["ffmpeg", "-y", "-loop", "1", "-t", f"{d:.2f}", "-i", "/app/vidwork/cierre.png",
         "-i", "/app/vidwork/aud_fin.mp3",
         "-filter_complex", f"[0:v]scale={W}:720,setsar=1,fade=t=in:d=0.8[v]",
         "-map", "[v]", "-map", "1:a", "-t", f"{d:.2f}",
         "-c:v", "libx264", "-preset", "fast", "-crf", "22", "-r", "25", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "160k", "-af", "adelay=800|800,apad", "-shortest",
         "/app/vidwork/seg_fin.mp4"])
    print("cierre OK")

async def main():
    apertura()
    async with async_playwright() as pw:
        await grabar(pw, "t1", durs["t1"] + 1, acc1)
        await grabar(pw, "t2", durs["t2"] + 1, acc2)
        await grabar(pw, "t3", durs["t3"] + 1, acc3)
        await cierre_shot(pw)
    for k in ["t1", "t2", "t3"]:
        montar(k)
    montar_cierre()
    open("/app/vidwork/lista.txt", "w").write("\n".join(
        f"file '/app/vidwork/seg_{k}.mp4'" for k in ["ap", "t1", "t2", "t3", "fin"]))
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "/app/vidwork/lista.txt",
         "-c", "copy", "/app/vidwork/final.mp4"])
    print("FINAL", subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", "/app/vidwork/final.mp4"],
        capture_output=True, text=True).stdout.strip())

asyncio.run(main())
