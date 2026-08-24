import subprocess, json

W, H, FPS = 1280, 720, 25
XF = 0.5

# (tipo, fuente, ss, dur)
PIEZAS = [
    ("img", "v_familia", 0, 4.3),
    ("app", "rec_app", 4.0, 6.0),      # registro diario
    ("img", "v_duena", 0, 4.3),
    ("app", "rec_app", 11.5, 5.5),     # metas de ahorro
    ("img", "v_emprende", 0, 4.3),
    ("app", "rec_app", 19.0, 5.5),     # chat Martín animado
    ("img", "v_casa", 0, 4.3),
    ("app", "rec_app", 27.5, 5.0),     # 8 módulos grid
    ("app", "rec_app", 33.0, 5.0),     # Conciencia
    ("img", "v_abuela", 0, 4.3),
    ("app", "rec_app", 38.5, 5.5),     # Modo Crisis
    ("app", "rec_app", 45.0, 5.5),     # Desafíos
    ("img", "v_soledad", 0, 4.3),
    ("app", "rec_app", 52.0, 7.0),     # Modo Familia
]

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-1200:]); raise SystemExit(1)

def norm():
    for i, (tipo, src, ss, d) in enumerate(PIEZAS):
        out = f"/app/vidwork/pz{i:02d}.mp4"
        if tipo == "img":
            run(["ffmpeg", "-y", "-loop", "1", "-t", f"{d}", "-i", f"/app/vidwork/{src}.jpeg",
                 "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,"
                        f"zoompan=z='min(zoom+0.0008,1.1)':d={int(d*FPS)}:s={W}x{H}:fps={FPS}",
                 "-t", f"{d}", "-c:v", "libx264", "-preset", "fast", "-crf", "21", "-pix_fmt", "yuv420p", "-an", out])
        else:
            run(["ffmpeg", "-y", "-ss", f"{ss}", "-t", f"{d}", "-i", "/app/vidwork/rec_app.webm",
                 "-vf", f"scale=-2:{H},pad={W}:{H}:(ow-iw)/2:0:color=0x101E5E,setsar=1,fps={FPS}",
                 "-c:v", "libx264", "-preset", "fast", "-crf", "21", "-pix_fmt", "yuv420p", "-an", out])
        print("pieza", i, "ok")

def xfade():
    n = len(PIEZAS)
    ins = []
    for i in range(n):
        ins += ["-i", f"/app/vidwork/pz{i:02d}.mp4"]
    ins += ["-i", "/app/vidwork/aud_ap.mp3"]
    durs = [p[3] for p in PIEZAS]
    filt, prev = [], "0:v"
    off = durs[0] - XF
    for i in range(1, n):
        out = f"x{i}"
        filt.append(f"[{prev}][{i}:v]xfade=transition=fade:duration={XF}:offset={off:.3f}[{out}]")
        prev = out
        off += durs[i] - XF
    total = sum(durs) - XF * (n - 1)
    run(["ffmpeg", "-y", *ins, "-filter_complex", ";".join(filt),
         "-map", f"[{prev}]", "-map", f"{n}:a", "-t", f"{total:.2f}",
         "-c:v", "libx264", "-preset", "fast", "-crf", "21", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "160k", "-af", "apad", "-shortest", "/app/vidwork/seg_cuerpo.mp4"])
    print("cuerpo", round(total, 2))

def concat():
    open("/app/vidwork/lista2.txt", "w").write(
        "file '/app/vidwork/seg_cuerpo.mp4'\nfile '/app/vidwork/seg_fin.mp4'\n")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "/app/vidwork/lista2.txt",
         "-c", "copy", "/app/vidwork/final2.mp4"])
    d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1", "/app/vidwork/final2.mp4"],
                       capture_output=True, text=True).stdout.strip()
    print("FINAL2", d)

norm(); xfade(); concat()
