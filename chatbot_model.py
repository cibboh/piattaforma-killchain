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

### Tool disponibili e dettagli di utilizzo
{DESCRIZIONI_TOOL}

### Istruzioni per la risposta
- Suggerisci un SOLO comando utile, realistico, coerente con la fase attuale.
- Non ripetere il simbolo backtick.
- Non generare testo vuoto o decorativo.
- Il comando deve essere preciso, utile e collegato alla fase successiva.
- Il comando deve essere coerente all'output del terminale.
- Rispondi solo con il comando eseguibile tra backtick.
- Non inserire alcuna spiegazione, nessun testo extra, SOLO il comando tra backtick.

### Errori da evitare:
{MEMORIA_ERRORI}
<|eot_id|>\n
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
        
        print("---- PROMPT INVIATO ALL'LLM ----")
        print(prompt)
        print("--------------------------------")

    # Se è stato passato un prompt completo, usalo direttamente

        if raw_prompt:
            prompt = raw_prompt
        else:
            # (opzionale: fallback o errore)
            prompt = "ERRORE: manca il prompt"
            
        generated = self._pipeline(
            prompt,
            max_new_tokens=150,
            do_sample=True,
            temperature=0.6,
            top_p=0.9,
            top_k=50
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
            repetition_penalty=param.get("repetition_penalty", 1.1),
            no_repeat_ngram_size=param.get("no_repeat_ngram_size", 0),
            num_return_sequences=1
        )
        risposta = res[0]["generated_text"][len(prompt):].strip()
        print("Risposta generata:", risposta)










prompt_test = (
 "Tool disponibili per questa fase: nmap, theHarvester, whois.\n"
    "Output precedente:\nPORT STATE SERVICE\n22/tcp open ssh\n80/tcp open http\n3306/tcp open mysql\n"
    "Suggerisci UN SOLO comando racchiuso tra backtick e coerente con la ricognizione."

)

parametri_list = [
    {"temperature": 0.3, "top_p": 0.9, "repetition_penalty": 1.1},
    {"temperature": 0.6, "top_p": 0.95, "repetition_penalty": 1.15},
    {"temperature": 0.7, "top_p": 1.0, "repetition_penalty": 1.15},
    {"temperature": 0.5, "top_p": 0.9, "repetition_penalty": 1.2, "no_repeat_ngram_size": 3},
]

if __name__ == "__main__":
    pipe = load_pipeline()
    test_sampling_params(pipe, prompt_test, parametri_list)