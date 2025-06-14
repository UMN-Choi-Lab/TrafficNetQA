import os
import json
import subprocess
from typing import Optional
from langchain_core.language_models.llms import LLM
from pydantic import Field
from langchain_ollama import OllamaLLM


class LlamaCppLLM(LLM):
    model_path: str = Field()
    context_size: int = Field(default=65536) 
    gpu: int = Field(default=0)

    def _call(self, prompt: str, stop: Optional[list] = None) -> str:
        env = os.environ.copy()
        env["CUDA_VISIBLE_DEVICES"] = str(self.gpu) 
        result = subprocess.run([
            "/path/your/llama-cli",
            "-m", self.model_path,
            "-c", str(self.context_size),
            "-n", "64",
            "--single-turn",    
            "-ngl", "99",
            "-p", prompt.strip(),
            "-r", "Answer:"
        ], capture_output=True, text=True, env=env)

        return result.stdout.strip()

    @property
    def _llm_type(self) -> str:
        return "llama.cpp"


class NetworkQA:
    def __init__(self, model_choice, prompt_path, gpu_id=0):
        self.llm = self.load_llm(model_choice, gpu_id)
        self.file_content = ""
        self.prompt_template = self.load_prompt(prompt_path)

    def load_llm(self, model_choice, gpu_id):
        if model_choice.endswith(".gguf"):
            return LlamaCppLLM(model_path=model_choice, gpu=gpu_id)
        else:
            return OllamaLLM(model=model_choice)

    def load_prompt(self, path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()

    def load_file(self, file_path):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            self.file_content = f.read()
        print(f"✅ File loaded ({len(self.file_content):,} characters).")

    def ask(self, question):
        prompt = self.prompt_template.format(
            file_content=self.file_content,
            question=question
        )

        return self.llm.invoke(prompt).strip()

    def log_response(self, qid, question, ground_truth, model_answer, filetype, question_category, model_used, aug_model_name):
        
        category_qid = f"{question_category}_{qid}"
        entry = {
            "model": model_used,
            "id": category_qid,
            "question": question,
            "ground_truth": ground_truth,
            "model_answer": model_answer,
            "score": None
        }
        output_path = f"/output/qa{aug_model_name}_log_{filetype}_{question_category}.jsonl"
        with open(output_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":

    input_model = input("Choose model ( llama3.2:3b, qwen2.5:3b, gemma3:4b, ...): ").strip()
    
    if input_model == "llama3.2:3b":
        model_choice = "/path/your/llama3.2-3b-q5_k_m.gguf"
        aug_model_name = "Llama"
    # You can add more models here
    else:
        print("Invalid model choice. Please enter a valid model name or path.")
        
    gpu_id = int(input("Select GPU index (0–3): ").strip())

    filetype = "xml" # 'xml', 'xml_simple', 'osm'
    set_for_exp = [['Basic', 8], ['Path', 6], ['Scene', 12]] 

    for question_category, q_idx in set_for_exp:
        
        for q_idx in range(1, q_idx + 1):
            
            file_path = f"./network/net_forQA_{filetype}.xml"
            prompt_path = "./task_prompt.txt"
            questions_path = f"./QAdataset/home/test1/22_LLMnetBench_answer/QAset_{filetype}_{question_category}_Q{q_idx}.json"
            
            qa = NetworkQA(model_choice, prompt_path, gpu_id)
            qa.load_file(file_path)

            with open(questions_path, "r", encoding="utf-8") as f:
                questions = json.load(f)

            for q in questions:
                print(f"< Q > {q['id']}: {q['question']}")
        
                try:
                    answer = qa.ask(q["question"])
                except Exception as e:
                    answer = f"[ERROR] {e}"
                
                
                idx = answer.find("Answer:")
                if idx != -1:
                    processd_answer = answer[idx + len("Answer:"):].strip()
                else:
                    processd_answer = answer.strip()   
                
                print(f'< A > {processd_answer}')

                qa.log_response(q["id"], q["question"], q["ground_truth"], processd_answer, filetype, question_category, input_model, aug_model_name)
