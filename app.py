import datetime
import os
import json
import re
from flask import Flask, render_template, request, jsonify
from chatbot_model import ChatBot
from chatbot_model import PROMPT_KILLCHAIN_TEMPLATE

def build_tool_section(tool_list, tool_details_dict):
    """
    Genera una sezione testo dettagliata per i tool di una fase, pronta per il prompt.
    """
    descr = []
    for tool in tool_list:
        td = tool_details_dict.get(tool)
        if not td:
            continue  # se manca la descrizione, salta il tool
        esempio = td["esempi"][0] if td.get("esempi") else ""
        riga = f"""Tool: {tool}
- Descrizione: {td['descrizione']}
- Quando usarlo: {td['quando_usarlo']}
- Esempio: {esempio}"""
        descr.append(riga)
    return "\n\n".join(descr)


app = Flask(__name__)
bot = ChatBot()

# Load static commands (ricognizione come base iniziale)
with open("static_commands.json", encoding="utf-8") as f:
    static_scenario = json.load(f)

all_outputs_raw = static_scenario["shopcorp_web"]
tool_details_dict = all_outputs_raw.get("tool_details", {})
all_static_outputs = {}

# Carichiamo tutti gli output_* in un unico dizionario normalizzato
for chiave, diz in all_outputs_raw.items():
    if chiave.startswith("output_"):
        for comando, output in diz.items():
            all_static_outputs[comando.lower()] = output


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
    """
    Payload atteso: {
        "fase": "delivery",
        "comando": "scp payload.elf mario.rossi@shopcorp.local:/tmp",
        "output_sbagliato": "...",
        "output_corretto": "...",
        "motivo": "...",
    }
    """
    data = request.get_json()
    fase = data.get('fase', '').strip()
    comando = data.get('comando', '').strip()
    output_sbagliato = data.get('output_sbagliato', '').strip()
    output_corretto = data.get('output_corretto', '').strip()
    motivo = data.get('motivo', '').strip()

    if not (fase and comando and output_sbagliato and output_corretto and motivo):
        return jsonify({"status": "error", "message": "Parametri mancanti"}), 400

    feedback_obj = {
        "fase": fase,
        "comando": comando,
        "output_sbagliato": output_sbagliato,
        "output_corretto": output_corretto,
        "motivo": motivo,
        "timestamp": datetime.datetime.utcnow().isoformat()
    }
    save_output_feedback(feedback_obj)
    return jsonify({"status": "ok"})

def costruisci_memoria_output_feedback(fase, comando):
    feedbacks = load_output_feedbacks()
    lines = []
    for fb in feedbacks:
        if (
    fb.get("fase", "").strip().lower() == fase.strip().lower() and
    fb.get("comando", "").strip().lower().replace("`", "") == comando.strip().lower().replace("`", "")
            ):
            lines.append(
                f"- In passato l’output “{fb['output_sbagliato']}” è stato corretto così: “{fb['output_corretto']}” (Motivo: {fb['motivo']})"
            )
    if lines:
        return (
            "ATTENZIONE: Queste correzioni sono state fornite in passato per questo comando:\n"
            + "\n".join(lines) + "\n\n"
        )
    return ""


@app.route('/')
def home():
    return render_template("home.html")

@app.route('/livello1')
def livello1():
    return render_template("livello1.html")

@app.route('/terminal', methods=['POST'])
def terminal():
    comando = request.json.get('command', '').strip().lower()
    fase = request.json.get('fase', 'ricognizione').strip().lower()
    fase_info = get_fase_info(static_scenario, fase)
    output_statici = fase_info["output_statici"] if fase_info else {}

    output_statici_norm = {k.lower(): v for k, v in output_statici.items()}

    if comando in output_statici_norm:
        return jsonify({"output": output_statici_norm[comando]})
    if comando in dynamic_commands:
        return jsonify({"output": dynamic_commands[comando]})
    return jsonify({"output": f"bash: {comando}: command not found"})




@app.route('/chatbot', methods=['POST'])
def chatbot():
    data = request.get_json()
    output = data.get('output', '')
    comando = data.get('command', '')
    fase = data.get('fase', 'ricognizione').strip().lower()
    prompt_custom = data.get('prompt_custom', '').strip()
    prossima_fase = fase_successiva(fase)
    memoria = costruisci_memoria_errori(fase)
    fase_info = get_fase_info(static_scenario, fase)
    tool_consentiti = fase_info["tool_consentiti"] if fase_info else []
    descrizioni_tool = build_tool_section(tool_consentiti, tool_details_dict)

    prompt = PROMPT_KILLCHAIN_TEMPLATE
    prompt = prompt.replace("{FASE_CORRENTE}", fase)
    prompt = prompt.replace("{FASE_SUCCESSIVA}", prossima_fase)
    prompt = prompt.replace("{COMANDO_INPUT}", comando or "[nessun comando]")
    prompt = prompt.replace("{OUTPUT_TERMINALE}", output or "[nessun output disponibile]")
    prompt = prompt.replace("{MEMORIA_ERRORI}", memoria or "Nessun errore precedente segnalato.")
    prompt = prompt.replace("{TOOL_CONSENTITI}", ', '.join(tool_consentiti))
    prompt = prompt.replace("{DESCRIZIONI_TOOL}", descrizioni_tool)

    if prompt_custom:
        prompt += f"\nRichiesta utente: {prompt_custom}\n"

    ai_response, _ = bot.process_input(
        terminal_output=output,
        next_phase=prossima_fase,
        current_phase=fase,
        comando=comando,
        memoria_errori=memoria,
        raw_prompt= prompt
    )

    # [Estrarre il comando tra backtick come già fai...]
   ## match = re.search(r"`([^`]+)`", ai_response)
    ##if match:
     ##   cmd_suggerito = match.group(1).strip()
   ## else:
    ##  cmd_suggerito = ai_response.strip().split("\n")[0]
    return jsonify({'suggestion': ai_response})


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
    
    memoria_output = costruisci_memoria_output_feedback(fase, comando)

    # Prompt per generare output realistico
    prompt_output = (
    memoria_output +
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
