from flask import Flask, render_template, request, jsonify
import json, re
from chatbot_model import ChatBot

app = Flask(__name__)

# Inizializza chatbot
bot = ChatBot()

# Carica comandi statici da file JSON
with open("static_commands.json", encoding="utf-8") as f:
    scenari = json.load(f)
static_commands = scenari["shopcorp_web"]["output_reconnaissance"]

# Dizionario per comandi dinamici (in memoria)
dynamic_commands = {}


def byteboo_response(prompt: str) -> str:
    """
    Passa un prompt a ByteBoo e restituisce la risposta testuale.
    """
    response, _ = bot.process_input(prompt)
    return response


def suggest_command(comando: str) -> str:
    """
    Chiede al chatbot di suggerire un comando Linux appropriato per l'input non riconosciuto.
    Restituisce il nome del comando suggerito oppure None.
    """
    prompt = (
        f"L'utente ha digitato '{comando}', che non è riconosciuto. "
        "Suggerisci un comando Linux appropriato e racchiudilo tra virgolette, p.es. 'ls -la'."
    )
    risposta = byteboo_response(prompt)
    match = re.search(r"'([^']+)'", risposta)
    return match.group(1) if match else None


@app.route('/')
def home():
    return render_template("home.html")

@app.route('/ricognizione')
def fase_ricognizione():
    return render_template("index.html")

@app.route('/livelli')
def livelli():
    return render_template("livelli.html")

@app.route('/livello1')
def livello1():
    return render_template("livello1.html")

@app.route('/livello2')
def livello2():
    return render_template("livello2.html")

@app.route('/livello3')
def livello3():
    return render_template("livello3.html")

@app.route('/terminal', methods=['POST'])
def terminal():
    comando = request.json.get('command', '').strip().lower()
    # 1) Comando statico
    if comando in static_commands:
        return jsonify({"output": static_commands[comando]})
    # 2) Comando dinamico
    if comando in dynamic_commands:
        return jsonify({"output": dynamic_commands[comando]})
    # 3) Comando sconosciuto: richiedi suggerimento
    suggestion = suggest_command(comando)
    if suggestion:
        return jsonify({"suggestion": suggestion})
    # 4) fallback
    return jsonify({"output": "Comando non riconosciuto. Digita `help`."})

@app.route('/add_command', methods=['POST'])
def add_command():
    comando = request.json.get('command', '').strip().lower()
    # Genera output simulato per il nuovo comando
    prompt = (
        "Simula un terminale Linux Ubuntu 20.04. "
        "L'utente ha digitato questo comando:\n"
        f"$ {comando}\n"
        "Restituisci solo l'output, senza spiegazioni né prefissi.\n"
        "Output:"
        )
    output_simulato = byteboo_response(prompt)
    # Registra in memoria
    dynamic_commands[comando] = output_simulato
    return jsonify({"status": "ok", "command": comando})

@app.route('/chatbot', methods=['POST'])
def chatbot():
    data = request.get_json()
    terminal_output = data.get('output', '')
    response = byteboo_response(terminal_output)
    return jsonify({'response': response})

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_msg = data.get('message', '').strip()
    if not user_msg:
        return jsonify({"response": ""})
    # Manda il messaggio diretto al chatbot senza wrapper di fase
    response = byteboo_response(user_msg)
    return jsonify({"response": response})

if __name__ == "__main__":
    app.run(debug=True)
