import os
import json
import logging
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline, BitsAndBytesConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROMPT_PATH = "../datasets/prompt.txt"

# Template aggiornato per la Cyber Kill Chain
PROMPT_KILLCHAIN_TEMPLATE = '''
Sei un assistente AI esperto in cybersecurity e simulazione di attacchi secondo il modello delle 7 fasi della Cyber Kill Chain.

Stai collaborando con un utente che sta simulando un attacco. Attualmente si trova nella fase **{FASE_CORRENTE}** della kill chain. L’obiettivo è proseguire logicamente verso la prossima fase: **{FASE_SUCCESSIVA}**.

### Informazioni contestuali
- Comando eseguito: `{COMANDO_INPUT}`
- Output ricevuto:
{OUTPUT_TERMINALE}

### Istruzioni per la risposta
- Suggerisci **un solo comando** utile, realistico, coerente con la fase attuale.
- Scrivilo racchiuso **in un solo paio di backtick**. Esempio: `nmap -sV target.com`
- ❌ Non ripetere il simbolo backtick.
- ❌ Non generare testo vuoto o decorativo.
- ✅ Il comando deve essere preciso, utile e collegato alla fase successiva.

### Errori da evitare (memoria):
{MEMORIA_ERRORI}

Rispondi con un solo comando tra backtick:
'''

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
            prompt = PROMPT_KILLCHAIN_TEMPLATE.replace("{FASE_CORRENTE}", current_phase)
            prompt = prompt.replace("{FASE_SUCCESSIVA}", next_phase)
            prompt = prompt.replace("{COMANDO_INPUT}", comando or "[nessun comando]")
            prompt = prompt.replace("{OUTPUT_TERMINALE}", terminal_output or "[nessun output disponibile]")
            prompt = prompt.replace("{MEMORIA_ERRORI}", memoria_errori or "Nessun errore precedente segnalato.")

        generated = self._pipeline(
            prompt,
            max_new_tokens=150,
            do_sample=True,
            temperature=0.5,
            top_p=0.9
        )

        full_text = generated[0]["generated_text"]
        response = full_text[len(prompt):].strip()
        return response, None