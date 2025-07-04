import datetime
import os
import json
import re
from flask import Flask, render_template, request, jsonify
from chatbot_model import ChatBot
from chatbot_model import PROMPT_KILLCHAIN_TEMPLATE


PROMPT_OUTPUT_SIMULATION_TEMPLATE = """
<|start_header_id|>system<|end_header_id|>
Agisci come un terminale Linux Ubuntu 20.04. Simula in modo realistico l’esecuzione di un comando dell’utente. Restituisci SOLO l’output che apparirebbe nel terminale. Nessun commento, nessuna spiegazione, nessun altro comando.

<|start_header_id|>user<|end_header_id|>

### Contesto
- Obiettivo: generare l’output realistico per un comando ricevuto.
- Comando: {COMANDO_INPUT}


{MEMORIA_ERRORI}

### Istruzioni
- Non inserire testo decorativo.
- Non scrivere spiegazioni.
- NON ripetere il comando (`{COMANDO_INPUT}`).
- Simula ciò che appare su un terminale REALE Linux 20.04.
- Nessun blocco markdown (no ```)
- L’output deve essere coerente, realistico e fedele al comportamento reale del comando.

Rispondi con il solo output:
"""

def build_tool_section(tool_list, tool_details_dict):
    """
    Genera una sezione testo per i tool consentiti in una fase,
    includendo SOLO nome, descrizione e quando usarlo (senza esempi).
    """
    descr = []
    for tool in tool_list:
        td = tool_details_dict.get(tool)
        if not td:
            continue
        riga = f"""Tool: {tool}
- Descrizione: {td['descrizione']}
- Quando usarlo: {td['quando_usarlo']}"""
        descr.append(riga)
    return "\n\n".join(descr)


output_storici = []
output_temporaneo = {}

app = Flask(__name__)
bot = ChatBot()

# Load static commands (ricognizione come base iniziale)
with open("static_commands.json", encoding="utf-8") as f:
    static_scenario = json.load(f)

    tool_details_dict = static_scenario["shopcorp_web"].get("tool_details", {})



dynamic_commands = {}
FEEDBACK_FILE = "feedback.json"
FEEDBACK_OUTPUT_FILE = "feedback_output.json"

PHASES = [
    "ricognizione",
    "weaponization",
    "delivery",
    "exploit",
    "installation",
    "command_and_control",
    "actions_on_objectives"
]

def get_fase_info(static_scenario, fase_nome):
    for fase in static_scenario["shopcorp_web"]["kill_chain"]:
        if fase["fase"].lower() == fase_nome.lower():
            return fase
    return None

def fase_successiva(fase_attuale):
    try:
        idx = PHASES.index(fase_attuale.lower())
        return PHASES[idx + 1] if idx + 1 < len(PHASES) else PHASES[-1]
    except ValueError:
        return PHASES[0]
    
#Feedback suggerimenti
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

#Feedback output generati
def load_output_feedbacks():
    if not os.path.isfile(FEEDBACK_OUTPUT_FILE):
        with open(FEEDBACK_OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
    with open(FEEDBACK_OUTPUT_FILE, encoding="utf-8") as f:
        return json.load(f)
    
def save_output_feedback(feedback_obj):
    fb_list = load_output_feedbacks()
    fb_list.append(feedback_obj)
    with open(FEEDBACK_OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(fb_list, f, indent=2, ensure_ascii=False)


@app.route('/feedback_output', methods=['POST'])
def feedback_output():
    data = request.get_json()
    fase = data.get('fase', '').strip()
    comando = data.get('comando', '').strip()
    output_sbagliato = data.get('output_sbagliato', '').strip()
    motivo = data.get('motivo', '').strip()

    # Ora non controlli più output_corretto!
    if not (fase and comando and output_sbagliato and motivo):
        return jsonify({"status": "error", "message": "Parametri mancanti"}), 400

    feedback_obj = {
        "fase": fase,
        "comando": comando,
        "output_sbagliato": output_sbagliato,
        "motivo": motivo,
        "timestamp": datetime.datetime.utcnow().isoformat()
    }
    save_output_feedback(feedback_obj)

    nuovo_output = genera_output_command(comando, fase)  # Genera e salva output

    # Restituisci il NUOVO output al frontend!
    return jsonify({"status": "ok", "nuovo_output": nuovo_output})



def tokenize_cmd(cmd):
    """
    Trasforma un comando in un set di token, ignorando apici, backtick, parentesi e spazi multipli.
    """
    s = cmd.strip().lower()
    s = re.sub(r"[`'\"\(\)]", "", s)
    s = re.sub(r"\s+", " ", s)  # sostituisce spazi multipli con uno solo
    return set(s.split())

def tokens_similar(set1, set2, threshold=0.8):
    """
    Ritorna True se la similarità Jaccard tra i due set supera la soglia.
    threshold=1.0: solo match perfetti
    threshold più basso: tollera opzioni in più/in meno
    """
    inter = set1 & set2
    union = set1 | set2
    if not union:
        return False
    return len(inter) / len(union) >= threshold

def costruisci_memoria_output_feedback(fase, comando):
    feedbacks = load_output_feedbacks()
    lines = []
    token_cmd = tokenize_cmd(comando)
    for fb in feedbacks:
        if (
            fb.get("fase", "").strip().lower() == fase.strip().lower()
            and tokens_similar(token_cmd, tokenize_cmd(fb.get("comando", "")), 0.6)
        ):
            lines.append(
                f"↪ Guida: {fb['motivo'].strip()}"
            )
    if lines:
        return "### guida su come produrre un output realistico per questo comando:\n" + "\n\n".join(lines) + "\n"
    return ""

@app.route('/')
def home():
    return render_template("home.html")


@app.route('/livello1')
def livello1():
    global output_storici, output_temporaneo, dynamic_commands
    output_storici = []
    output_temporaneo = {}
    dynamic_commands = {}
    return render_template("livello1.html")


def costruisci_output_cumulativo():
    testo = "### Output delle fasi precedenti:\n"
    for elem in output_storici:
        testo += f"[{elem['fase']}] $ {elem['comando']}\n{elem['output']}\n\n"
    return testo

def get_ultimo_output_valido(fase_corrente):
    # Cerca l'ultimo output confermato per questa fase
    for elem in reversed(output_storici):
        if elem["fase"] == fase_corrente:
            return elem["output"]
    # Altrimenti prendi l'ultimo in assoluto (es. output di una fase precedente)
    if output_storici:
        return output_storici[-1]["output"]
    return "[nessun output disponibile]"


def conferma_output_automaticamente():
    global output_temporaneo
    if output_temporaneo:
        comando_temp = output_temporaneo["comando"].strip().lower()
        fase_temp = output_temporaneo["fase"]

        # Rimuovi TUTTI gli output storici per stesso comando e fase (case insensitive!)
        output_storici[:] = [
            o for o in output_storici
            if not (
                o["fase"] == fase_temp and
                o["comando"].strip().lower() == comando_temp
            )
        ]
        
        # Aggiungi il nuovo output pulito
        output_storici.append(output_temporaneo)

        # Aggiorna sempre dynamic_commands
        dynamic_commands[output_temporaneo["comando"]] = output_temporaneo["output"]
        output_temporaneo = {}


@app.route('/terminal', methods=['POST'])
def terminal():
    comando = request.json.get('command', '').strip().lower()
    fase = request.json.get('fase', 'ricognizione').strip().lower()
    fase_info = get_fase_info(static_scenario, fase)
    if comando in dynamic_commands:
     output = dynamic_commands[comando]
    else:
        output = genera_output_command(comando, fase) 

    return jsonify({"output": output})



@app.route('/chatbot', methods=['POST'])
def chatbot():
    data = request.get_json()
    comando = data.get('command', '')
    fase = data.get('fase', 'ricognizione').strip().lower()
    prompt_custom = data.get('prompt_custom', '').strip()
    prossima_fase = fase_successiva(fase)
    memoria = costruisci_memoria_errori(fase)
    fase_info = get_fase_info(static_scenario, fase)
    tool_consentiti = fase_info["tool_consentiti"] if fase_info else []
    descrizioni_tool = build_tool_section(tool_consentiti, tool_details_dict)

    prompt_cumulativo = costruisci_output_cumulativo()

    # Usa sempre ultimo output valido
    ultimo_output_valido = get_ultimo_output_valido(fase)

    prompt = PROMPT_KILLCHAIN_TEMPLATE
    prompt = prompt.replace("{FASE_CORRENTE}", fase)
    prompt = prompt.replace("{FASE_SUCCESSIVA}", prossima_fase)
    prompt = prompt.replace("{COMANDO_INPUT}", comando or "[nessun comando]")
    prompt = prompt.replace("{OUTPUT_TERMINALE}", ultimo_output_valido)
    prompt = prompt.replace("{MEMORIA_ERRORI}", memoria or "Nessun errore precedente segnalato.")
    prompt = prompt.replace("{TOOL_CONSENTITI}", ', '.join(tool_consentiti))
    prompt = prompt.replace("{DESCRIZIONI_TOOL}", descrizioni_tool)

    prompt = prompt_cumulativo + "\n" + prompt

    if prompt_custom:
        prompt += f"\nRichiesta utente: {prompt_custom}\n"

    ai_response, _ = bot.process_input(
        terminal_output=ultimo_output_valido,
        next_phase=prossima_fase,
        current_phase=fase,
        comando=comando,
        memoria_errori=memoria,
        raw_prompt=prompt
    )

    return jsonify({'suggestion': ai_response})


def pulisci_output(output_raw):
    """
    Pulisce l'output generato da ByteBoo/Llama rimuovendo blocchi markdown inutili,
    backtick multipli e righe vuote ripetute.
    """
    output = output_raw.strip()

    # Rimuove tutti i backtick multipli
    output = re.sub(r"```[\w]*\n?", "", output)
    # Rimuove backtick rimasti (solitari o ripetuti)
    output = output.replace("```", "")
    # Rimuove righe vuote multiple
    output = re.sub(r'\n{3,}', '\n\n', output)
    return output.strip()

def genera_output_command(comando, fase):
    memoria_output = costruisci_memoria_output_feedback(fase, comando)

    prompt_output = PROMPT_OUTPUT_SIMULATION_TEMPLATE \
    .replace("{COMANDO_INPUT}", comando) \
    .replace("{MEMORIA_ERRORI}", memoria_output or "Nessuna correzione segnalata.")


    output_simulato, _ = bot.process_input(
        terminal_output="",
        current_phase="output_simulation",
        next_phase="",
        comando=comando,
        memoria_errori="",
        raw_prompt=prompt_output
    )
    output_simulato = pulisci_output(output_simulato)

    global output_temporaneo
    output_temporaneo = {
        "fase": fase,
        "comando": comando,
        "output": output_simulato
    }
    conferma_output_automaticamente()
    return output_simulato

@app.route('/add_command', methods=['POST'])
def add_command():
    comando = request.json.get('command', '').strip().lower()
    fase = request.json.get('fase', 'ricognizione').strip().lower()

    if not comando:
        return jsonify({"status": "error", "message": "comando vuoto"})

    # Se già presente, non rigenerare
    if comando in dynamic_commands and dynamic_commands[comando]:
        return jsonify({"status": "ok", "command": comando})
    
    # Chiamata centralizzata
    genera_output_command(comando, fase)
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
