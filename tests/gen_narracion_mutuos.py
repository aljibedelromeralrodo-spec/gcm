import asyncio, os, subprocess, sys
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

NARR = [
    (0.3, "Hola, soy Martín. Ahora te muestro el Módulo Mutuos de Victoria Vilches, construido etapa por etapa según su guía de usuario, con un cliente ficticio."),
    (10.3, "Etapa uno: evaluación del cliente. Los datos del titular y del codeudor llegan autocompletados desde la bóveda. RUT siempre con puntos y guion."),
    (21.3, "Etapa dos: registro de la operación. Se identifica la propiedad con su dirección, comuna y región."),
    (31.3, "Etapa tres: la tasación. Rol de avalúo, valor y antecedentes. Sin tasación ingresada, el sistema no permite avanzar hacia operaciones."),
    (42.3, "Etapa cuatro: datos del crédito. Precio, monto, plazo y tasa. La regla es clara: el crédito no puede superar el ochenta por ciento del valor de tasación."),
    (54.3, "Etapa cinco: seguimiento de la operación. Estudio de títulos, escrituración, notaría y conservador de bienes raíces, cada hito con su fecha."),
    (64.3, "Las validaciones irrenunciables: RUT del titular, RUT del codeudor, rol de avalúo, dirección, y la relación deuda garantía. Todo coincide, todo en verde."),
    (76.3, "Etapa seis: Victoria autoriza cada etapa con su clave y la operación se envía a revisión de riesgo en ConCreces, con correo de aviso automático."),
    (85.3, "Así opera el Módulo Mutuos de Victoria Vilches: seis etapas guiadas, validación total y cero errores. Listo para revisión de riesgo."),
]

async def gen_audios():
    from emergentintegrations.llm.openai import OpenAITextToSpeech
    tts = OpenAITextToSpeech(api_key=os.getenv("EMERGENT_LLM_KEY"))
    for i, (_, texto) in enumerate(NARR):
        audio = await tts.generate_speech(text=texto, model="tts-1-hd", voice="onyx", speed=1.0)
        with open(f"/tmp/nm_{i}.mp3", "wb") as f:
            f.write(audio)
        print(f"nm_{i}.mp3 {len(audio)}b", flush=True)

def mux(video_in, video_out):
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    inputs = ["-i", video_in]
    for i in range(len(NARR)):
        inputs += ["-i", f"/tmp/nm_{i}.mp3"]
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
    mux("/tmp/demo_mutuos_raw.mp4", "/app/backend/demos/demo_mutuos.mp4")
