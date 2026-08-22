import asyncio, os, subprocess, sys
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

NARR = [
    (0.3, "Hola, soy Martín. Te presento el Módulo Ventas de Central Mutuos, con las ejecutivas Yerile Barrera y Deysi Salazar."),
    (9.3, "Cuando llega una solicitud con documentación incompleta y entrega inmediata, califica automáticamente para Ventas."),
    (20.3, "La asignación es alternada: una solicitud para Yerile, la siguiente para Deysi, y así sucesivamente. Siempre equilibrado."),
    (32.3, "Cada ejecutiva ve solo sus clientes: qué documentos faltan, cuándo se asignó y el último contacto registrado."),
    (44.3, "Desde la ficha registra contactos, actualiza el estado y sube documentos, con las mismas validaciones irrenunciables del módulo de Daniela Galindo."),
    (57.3, "El administrador ve el reporte completo en tiempo real: clientes por ejecutiva, estados, faltantes y días en gestión."),
    (68.3, "Documentación completa y cliente listo para avanzar. Así trabaja el Módulo Ventas de Central Mutuos."),
]

async def gen_audios():
    from emergentintegrations.llm.openai import OpenAITextToSpeech
    tts = OpenAITextToSpeech(api_key=os.getenv("EMERGENT_LLM_KEY"))
    for i, (_, texto) in enumerate(NARR):
        audio = await tts.generate_speech(text=texto, model="tts-1-hd", voice="onyx", speed=1.0)
        with open(f"/tmp/nv_{i}.mp3", "wb") as f:
            f.write(audio)
        print(f"nv_{i}.mp3 {len(audio)}b", flush=True)

def mux(video_in, video_out):
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    inputs = ["-i", video_in]
    for i in range(len(NARR)):
        inputs += ["-i", f"/tmp/nv_{i}.mp3"]
    partes = []
    for i, (off, _) in enumerate(NARR):
        ms = int(off * 1000)
        partes.append(f"[{i+1}:a]adelay={ms}|{ms}[a{i}]")
    mezcla = "".join(f"[a{i}]" for i in range(len(NARR)))
    fc = ";".join(partes) + f";{mezcla}amix=inputs={len(NARR)}:normalize=0[aout]"
    r = subprocess.run([ff, "-y"] + inputs + ["-filter_complex", fc, "-map", "0:v", "-map", "[aout]",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest", video_out],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("FFMPEG ERROR:", r.stderr[-400:])
        sys.exit(1)
    print("mux ok:", video_out, os.path.getsize(video_out))

if __name__ == "__main__":
    asyncio.run(gen_audios())
    mux("/tmp/demo_ventas_raw.mp4", "/app/backend/demos/demo_ventas.mp4")
