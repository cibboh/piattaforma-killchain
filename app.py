import datetime
import os
import json
import re
from flask import Flask, render_template, request, jsonify
from chatbot_model import ChatBot

app = Flask(__name__)
bot = ChatBot()

# Load static commands (ricognizione come base iniziale)
with open("static_commands.json", encoding="utf-8") as f:
    scenari = json.load(f)

all_outputs_raw = scenari["shopcorp_web"]
all_static_outputs = {}

# Carichiamo tutti gli output_* in un unico dizionario normalizzato
for chiave, diz in all_outputs_raw.items():
    if chiave.startswith("output_"):
        for comando, output in diz.items():
            all_static_outputs[comando.lower()] = output


dynamic_commands = {}
FEEDBACK_FILE = "feedback.json"

PHASES = [
    "ricognizione",
    "weaponization",
    "delivery",
    "exploit",
    "installation",
    "command_and_control",
    "actions_on_objectives"
]

def fase_successiva(fase_attuale):
    try:
        idx = PHASES.index(fase_attuale.lower())
        return PHASES[idx + 1] if idx + 1 < len(PHASES) else PHASES[-1]
    except ValueError:
        return PHASES[0]

def load_feedbacks():
    if not os.path.isfile(FEEDBACK_FILE):
        with open(FEEDBACK_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
    with open(FEEDBACK_FILE, encoding="utf-8") as f:
        return json.load(f)

def save_feedback(feedback_obj):
    fb_list = load_feedbacks()
    fb_list.append(feedback_obj)
    with open(FEEDBACK_FILE, "w", encoding="utf-8") as f:
        json.dump(fb_list, f, indent=2, ensure_ascii=False)

def costruisci_memoria_errori(fase):
    feedbacks = load_feedbacks()
    return "\n".join([
        f"- NON usare `{fb['suggerimento_errato']}` perché: {fb['motivo']}"
        for fb in feedbacks if fb.get("fase") == fase
    ]) or "Nessun errore segnalato finora."

@app.route('/')
def home():
    return render_template("home.html")

@app.route('/livello1')
def livello1():
    return render_template("livello1.html")

@app.route('/terminal', methods=['POST'])
def terminal():
    comando = request.json.get('command', '').strip().lower()

    if comando in all_static_outputs:
        return jsonify({"output": all_static_outputs[comando]})
    if comando in dynamic_commands:
        return jsonify({"output": dynamic_commands[comando]})
    return jsonify({"output": f"bash: {comando}: command not found"})



@app.route('/chatbot', methods=['POST'])
def chatbot():
    data = request.get_json()
    output = data.get('output', '')
    comando = data.get('command', '')
    fase = data.get('fase', 'ricognizione').strip().lower()
    prossima_fase = fase_successiva(fase)
    memoria = costruisci_memoria_errori(fase)

    if not output.strip():
        return jsonify({'suggestion': ""})

    # 1. Chiediamo al chatbot un suggerimento per la fase successiva
    ai_response, _ = bot.process_input(
        terminal_output=output,
        current_phase=fase,
        next_phase=prossima_fase,
        comando=comando,
        memoria_errori=memoria
    )

    # DEBUG: stampa la risposta generata
    print("🧠 Risposta grezza dal chatbot:", ai_response)

    # 2. Estrai il comando suggerito tra backtick
    match = re.search(r"`([^`]+)`", ai_response)
    if match:
        cmd_suggerito = match.group(1).strip()
    else:
        # fallback: usa prima riga pulita
        parts = re.split(r"[\$;\|]+", ai_response.strip().split("\n")[0])
        cmd_suggerito = parts[0].strip()

    # 3. Normalizza spazi e lowercase
    cmd_suggerito = re.sub(r"\s+", " ", cmd_suggerito.lower())

    # 4. Confronta con comandi statici e dinamici
    comandi_statici_normalizzati = {k.lower() for k in all_static_outputs.keys()}

    if cmd_suggerito and cmd_suggerito not in comandi_statici_normalizzati and cmd_suggerito not in dynamic_commands:
        # Comando valido e nuovo → lo aggiungiamo
        dynamic_commands[cmd_suggerito] = ""
        return jsonify({'suggestion': cmd_suggerito})

    # 5. Nessun comando nuovo da suggerire
    return jsonify({'suggestion': ""})

def pulisci_output(output_raw):
    """
    Pulisce l'output generato da ByteBoo rimuovendo blocchi markdown inutili.
    Se l'output inizia con ``` allora prende solo il contenuto tra i primi due backtick.
    """
    output = output_raw.strip()

    if output.startswith("```"):
        match = re.search(r"```(?:\w+)?\n(.*?)```", output, re.DOTALL)
        if match:
            return match.group(1).strip()
        else:
            return output.replace("```", "").strip()
    return output


@app.route('/add_command', methods=['POST'])
def add_command():
    comando = request.json.get('command', '').strip().lower()
    fase = request.json.get('fase', 'ricognizione').strip().lower()

    if not comando:
        return jsonify({"status": "error", "message": "comando vuoto"})

    # Se già presente, non rigenerare
    if comando in dynamic_commands and dynamic_commands[comando]:
        return jsonify({"status": "ok", "command": comando})

    # Prompt per generare output realistico
    prompt_output = (
    f"Agisci come un terminale Linux Ubuntu 20.04.\n"
    f"Simula l'esecuzione reale del comando:\n"
    f"$ {comando}\n\n"
    f"Restituisci solo ciò che vedrebbe l'utente sul terminale.\n"
    f"Nessun commento, nessuna spiegazione, nessun altro comando.\n"
    f"Non inserire mai frasi tipo “contributo di...”, “esempio didattico”, “tradotto da”, “lingua: english” o firme. Sei un terminale, non un documento."
    f"Sii fedele al formato e ai contenuti che quel comando produrrebbe davvero."
    )

    # Usiamo process_input con prompt "iniettato" manualmente
    output_simulato, _ = bot.process_input(
        terminal_output="",
        current_phase="output_simulation",
        next_phase="",
        comando=comando,
        memoria_errori="",
        raw_prompt=prompt_output
    )
    output_simulato = pulisci_output(output_simulato)

    dynamic_commands[comando] = output_simulato
    return jsonify({"status": "ok", "command": comando})


@app.route('/feedback', methods=['POST'])
def feedback():
    data = request.get_json()
    fase = data.get('fase', '').strip()
    sbagliato = data.get('suggerimento_errato', '').strip()
    motivo = data.get('motivo', '').strip()

    if not fase or not sbagliato or not motivo:
        return jsonify({"status": "error", "message": "Parametro mancante"}), 400

    fb_obj = {
        "fase": fase,
        "suggerimento_errato": sbagliato,
        "motivo": motivo,
        "timestamp": datetime.datetime.utcnow().isoformat()
    }
    save_feedback(fb_obj)
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
