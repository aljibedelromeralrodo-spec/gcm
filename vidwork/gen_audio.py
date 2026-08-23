import asyncio, os, sys, json, subprocess
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
from emergentintegrations.llm.openai import OpenAITextToSpeech

APERTURA = ("Martín no es un chatbot. Es un mentor diario. Una app móvil de responsabilidad social creada para acompañar "
"a personas comunes: dueñas de casa, familias de ingresos medios y bajos, gente que nunca tuvo acceso a educación "
"financiera real. Martín es ese amigo que todos quisiéramos tener pero pocos tienen. Alguien que te pregunta cómo te "
"fue hoy, que celebra cuando ahorraste algo, que te contiene cuando la situación aprieta, que te orienta si quieres "
"emprender o postular a un subsidio habitacional. Con valores. Con espiritualidad. La Santa Biblia es el centro de sus "
"valores, su guía de aprendizaje y su fuente de sabiduría para acompañar a las personas en los momentos difíciles. "
"Con chilenismos. Con calidez. Como un amigo de verdad. Martín resuelve algo real: la soledad financiera de millones "
"de personas que no saben a quién preguntarle cómo llegar a fin de mes. Esto es responsabilidad social con tecnología "
"al servicio de las personas. Esto es Martín Suma UC.")

SEGS = {
"ap": APERTURA,
"t1": "Así se ve Martín cada mañana. Le saluda primero, le pregunta cuánto gastó y cuánto pudo ahorrar, y con eso construye su presupuesto mensual, día a día, con frases que motivan. Desde Mi Punto de Partida hasta el Presupuesto Familiar: todo parte por conocerse.",
"t2": "¿Deudas? Martín las ordena con el método bola de nieve y le enseña a tratar con los bancos. ¿El sueño de la casa propia? Le explica los subsidios: DS uno en sus tres tramos, DS diecinueve y DS cuarenta y nueve, y cómo postular paso a paso. ¿Ganas de emprender? Primeros pasos, fondos del Estado y finanzas sanas para su negocio.",
"t3": "Y cuando el ánimo pesa, Martín contiene: autoestima, experiencias guiadas con su propia voz, y una conversación de verdad, con memoria propia gracias a su Conciencia. Un amigo que le conoce, le recuerda y le acompaña.",
"fin": "Descárgalo. Tu amigo financiero te está esperando.",
}

def dur(path):
    out = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",path],capture_output=True,text=True).stdout.strip()
    return float(out)

async def main():
    tts = OpenAITextToSpeech(api_key=os.getenv("EMERGENT_LLM_KEY").strip('"'))
    for k, txt in SEGS.items():
        audio = await tts.generate_speech(text=txt, model="tts-1-hd", voice="onyx", speed=0.95)
        open(f"/app/vidwork/aud_{k}.mp3","wb").write(audio)
        print(k,"ok")
    durs = {k: dur(f"/app/vidwork/aud_{k}.mp3") for k in SEGS}
    json.dump(durs, open("/app/vidwork/durs.json","w"))
    print(durs, "total:", sum(durs.values()))

asyncio.run(main())
