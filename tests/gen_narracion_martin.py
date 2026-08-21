import asyncio, os, subprocess, sys
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

NARR = [
    (0.3, "Hola, soy Martín, el asistente de Central Mutuos ConCreces. Te voy a mostrar cómo funciona el módulo de Victoria paso a paso."),
    (10.3, "Paso uno: llega un correo con el set de crédito. El sistema lo detecta y descarga los adjuntos automáticamente en segundos."),
    (20.3, "Paso dos: cada documento se lee y se clasifica por tipo: tasación, estudio de títulos, carpeta de crédito y simulación."),
    (30.3, "Paso tres: la validación irrenunciable. RUT con RUT, codeudor con codeudor, rol de avalúo y dirección. Todo debe coincidir exactamente."),
    (43.3, "Paso cuatro: Victoria revisa cada documento en pantalla, sin descargarlo, y lo acepta o rechaza con un clic."),
    (54.3, "Paso cinco: los formularios se completan solos con los datos extraídos. Cero digitación y cero errores."),
    (66.3, "Paso seis: revisión final. El checklist completo queda aprobado en verde."),
    (75.3, "Paso siete: Victoria confirma y el set viaja a ConCreces con un solo clic."),
    (84.3, "Así de simple y rápido opera el módulo de Victoria. Todo validado, todo en orden, listo para ConCreces."),
]

async def gen_audios():
    from emergentintegrations.llm.openai import OpenAITextToSpeech
    tts = OpenAITextToSpeech(api_key=os.getenv("EMERGENT_LLM_KEY"))
    for i, (_, texto) in enumerate(NARR):
        audio = await tts.generate_speech(text=texto, model="tts-1-hd", voice="onyx", speed=1.05)
        with open(f"/tmp/narr_{i}.mp3", "wb") as f:
            f.write(audio)
        print(f"narr_{i}.mp3 {len(audio)}b", flush=True)

def mux(video_in, video_out):
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    inputs = ["-i", video_in]
    for i in range(len(NARR)):
        inputs += ["-i", f"/tmp/narr_{i}.mp3"]
    partes = []
    for i, (off, _) in enumerate(NARR):
        ms = int(off * 1000)
        partes.append(f"[{i+1}:a]adelay={ms}|{ms}[a{i}]")
    mezcla = "".join(f"[a{i}]" for i in range(len(NARR)))
    fc = ";".join(partes) + f";{mezcla}amix=inputs={len(NARR)}:normalize=0[aout]"
    cmd = [ff, "-y"] + inputs + ["-filter_complex", fc, "-map", "0:v", "-map", "[aout]",
           "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest", video_out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("FFMPEG ERROR:", r.stderr[-500:])
        sys.exit(1)
    print("mux ok:", video_out, os.path.getsize(video_out))

if __name__ == "__main__":
    asyncio.run(gen_audios())
    mux("/tmp/demo_martin_raw.mp4", "/app/backend/demos/demo_victoria.mp4")
