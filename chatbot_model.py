import os
import json
import logging
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline, BitsAndBytesConfig

# Configura il logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Percorso al prompt di sistema (opzionale, puoi lasciare None o usare un prompt di default)
PROMPT_PATH = "../datasets/prompt.txt"

def load_prompt():
    """
    Carica un prompt di sistema da file, se esistente. Altrimenti ritorna un prompt di default.
    """
    if os.path.exists(PROMPT_PATH):
        with open(PROMPT_PATH, "r", encoding="utf-8") as f:
            return f.read().strip()
    logger.info(f"Prompt di sistema non trovato in {PROMPT_PATH}, uso default.")
    return "Sei un assistente AI esperto di cybersecurity."


def load_pipeline():
    try:
        quantization_config = BitsAndBytesConfig(
            load_in_8bit=True,
            llm_int8_threshold=6.0
        )
        
        # Carica prima il modello con la quantizzazione
        model = AutoModelForCausalLM.from_pretrained(
            "swap-uniba/LLaMAntino-3-ANITA-8B-Inst-DPO-ITA",
            device_map="auto",
            torch_dtype=torch.float16,
            quantization_config=quantization_config
        )
        
        tokenizer = AutoTokenizer.from_pretrained("swap-uniba/LLaMAntino-3-ANITA-8B-Inst-DPO-ITA")

        # Passa il modello già caricato alla pipeline
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
    """
    Classe ChatBot che usa un modello instruction-tuned per fornire consigli di cybersecurity.
    """
    def __init__(self):
        self._pipeline = None
        self.system_prompt = load_prompt()

    def _ensure_pipeline_loaded(self):
        """
        Carica la pipeline se non è già stata caricata.
        """
        if self._pipeline is None:
            self._pipeline = load_pipeline()

    def process_input(self, terminal_output: str,  next_phase: str = "Weaponization"):
        """
        Riceve l'output del terminale simulato, costruisce un prompt guidato,
        genera la risposta e la restituisce.

        Ritorna:
            response (str): testo di risposta del chatbot
            None: placeholder (compatibilità firma)
        """
        self._ensure_pipeline_loaded()

        # Costruzione del prompt guidato
        prompt = (
           "Sei un assistente AI esperto di cybersecurity, seguendo le 7 fasi della Cyber Kill Chain.\n"
        "L'utente ha appena completato la **Fase 1: Ricognizione**, con questo output:\n"
        f"{terminal_output}\n\n"
        f"**Obiettivo**: Passare alla **Fase 2: {next_phase}**.\n"
        "Suggerisci **UN SOLO** comando o tool, tra quelli esistenti in Linux, "
        "da eseguire per iniziare la Weaponization. "
        "Rispondi solo con il comando (es. `msfvenom -p payload ...`), senza spiegazioni aggiuntive."
        )

        # Generazione della risposta
        generated = self._pipeline(
            prompt,
            max_new_tokens=300,
            do_sample=True,
            temperature=0.5,
        )

        full_text = generated[0]["generated_text"]
        # Estrazione della risposta dopo il prompt
        response = full_text[len(prompt):].strip()
        return response, None
