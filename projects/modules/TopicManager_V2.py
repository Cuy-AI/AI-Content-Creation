import json
import unicodedata
from prefect import task
from prefect.cache_policies import NO_CACHE
from classes.ContainerManager import ContainerManager


class Sanitizer:
    '''
    GPT usually return characters like: ‑ ’
    And when GPT reads those characters.. it crashes xdn't
    Sanitize whatever you send/receive to/from GPT 
    '''
    @staticmethod
    def sanitize_text(s: str) -> str:
        if not isinstance(s, str):
            return s

        replacements = {
            "\u2011": "-",  # non-breaking hyphen
            "\u2013": "-",  # en-dash
            "\u2014": "-",  # em-dash
            "\u2018": "'",  # left single quote
            "\u2019": "'",  # right single quote
            "\u201c": '"',  # left double quote
            "\u201d": '"',  # right double quote
        }

        for bad, good in replacements.items():
            s = s.replace(bad, good)

        return s
    
    @staticmethod
    def sanitize_obj(obj) -> dict:
        if isinstance(obj, dict):
            return {Sanitizer.sanitize_obj(k): Sanitizer.sanitize_obj(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [Sanitizer.sanitize_obj(x) for x in obj]
        elif isinstance(obj, str):
            return Sanitizer.sanitize_text(obj)
        else:
            return obj
        


class TopicManager_V2:

    def __init__(self, topics_path: str = None, model_name:str = "gpt-5-mini"):
        
        # Start Container
        self.openai_container = ContainerManager(image="openai:latest", port=8000, use_gpu = False)

        # Set a model
        self.model_name = model_name

        # Set topics path
        self.topics_path = topics_path

        # Set base schema
        self.base_topics_schema = {
            "type": "object",
            "properties": { },
            "additionalProperties": False
        }
    
   

    def load_stored_topics(self, topics_path: str = None) -> dict:
        topics_path = topics_path or self.topics_path
        with open(topics_path, "r", encoding="utf-8") as f:
            topics_json = json.load(f)
        return Sanitizer.sanitize_obj(topics_json)
    
    def update_stored_topics(self, topics_json: dict, topics_path: str = None) -> None:
        topics_path = topics_path or self.topics_path
        sanitized = Sanitizer.sanitize_obj(topics_json)
        with open(topics_path, "w", encoding="utf-8") as f:
            json.dump(sanitized, f, indent=2, ensure_ascii=False)


    @task(name = "request-new-topics", description = "Generate topics with GPT", cache_policy=NO_CACHE)
    def extend_topics_prompt(self, topics_json: dict, n:int) -> str:
        """
        Build the prompt to generate new topics.
        This method can be overridden to customize the prompt.
        Input:
          - topics_json: existing topics dictionary
          - n: number of topics to generate per category
        """
        category_list = list(topics_json.keys())

        memory_limit = 10
        existing_by_cat = { category: list(topics_dict.keys())[:memory_limit] for category, topics_dict in topics_json.items() }
        prompt = (
            f"You are an AI that generates highly engaging, curiosity-driven short-form educational video topics.\n"
            f"Goal:\n"
            f"- For each of these categories: {category_list}\n"
            f"- Suggest up to {n} highly compelling, specific, researchable topics.\n"
            f"- Topics should NOT be generic questions. They should feel like:\n"
            f"  * surprising mechanisms\n"
            f"  * counterintuitive truths\n"
            f"  * hidden complexity\n"
            f"  * real-world systems explained\n"
            f"  * unresolved mysteries or debates\n"
            f"  * shocking comparisons\n"
            f"- The topics must be short and concise, but NOT plain or boring.\n"
            f"- Each topic must be something people would *immediately* want to click on because it reveals something they didn't know they wanted to know.\n\n"
            f"Constraints:\n"
            f"- Avoid all existing topics in the dataset:\n"
            f"{existing_by_cat}\n"
            f"- Do NOT generate vague questions like 'What is X?' or 'How does X work?'\n"
            f"- Do NOT generate jokes or over-the-top titles.\n"
            f"- Every topic must be factual, researchable, and answerable in ~60 seconds.\n"
            f"Style:\n"
            f"- Make topics punchy, intriguing, and full of implied complexity.\n"
            f"- Prefer formats like:\n"
            f"  'Why ___ happens even though it shouldn't'\n"
            f"  'The hidden ___ behind ___'\n"
            f"  'Why ___ is harder than it looks'\n"
            f"  'The unexpected reason ___ works'\n"
            f"  'What makes ___ possible at massive scale'\n\n"
            f"Output:\n"
            f"- For each category, output a list of topics.\n"
            f"- Keep each topic under one sentence.\n"
            f"- Ensure each topic stands out as fascinating from first reading."
        )
        return prompt


    def extend_topics(self, topics_path: str = None, n: int = 5) -> bool:
        """
        Generate new topics for ALL categories in a single LLM call.
        Output must follow the schema:
        {
            "Category A": ["Question 1?", "Question 2?"],
            "Category B": ["Question 1?", "Question 2?"]
        }
        """

        topics_path = topics_path or self.topics_path
        topics_json = self.load_stored_topics(topics_path)

        # Flatten existing categorys
        category_list = list(topics_json.keys())

        # Build unified prompt
        prompt = self.extend_topics_prompt(topics_json, n)

        # Create the OpenAI container
        self.openai_container.start()
        openai_client = self.openai_container.create_client()

        # Set params
        openai_client.set_model_name(model_name=self.model_name)
        openai_client.set_params(max_completion_tokens=2048)

        # Build schema
        schema = self.base_topics_schema
        for cat in category_list:
            schema["properties"][cat] = {
                "type": "array",
                "items": { "type": "string" },
                "minItems": n
            }
        schema["required"] = category_list
        openai_client.set_schema(schema=self.base_topics_schema)

        # Generate response
        # print(f"\nSending prompt:\n{prompt}")
        # print(f"\nSending schema:\n{schema}")
        try:
            response = openai_client.generate(prompt=prompt, client_timeout=300)
            response = response['answer']['output']
            # print(f"\nResponse2: {response}")
        except Exception as e:
            print("[ERROR] LLM generation failed:", str(e))
            return False
        
        # Stop container
        self.openai_container.stop()

        # Try parse items
        if not isinstance(response, dict):
            print("[ERROR] LLM response is not a valid dictionary.")
            return False

        # Merge back into topics_json
        for category, ideas in response.items():
            for idea in ideas:
                if idea not in topics_json[category]:
                    topics_json[category][idea] = False

        # Save updated JSON
        self.update_stored_topics(topics_json)

        return True

    
    def check_missing_topics(self, topics):
        for _, raw_topics in topics.items():
            available_topics = [k for k in raw_topics.keys() if raw_topics[k] == False]
            if len(available_topics) == 0: return True
        return False


    def get_next_topics(self, extent_topics = False, extension_count = 5):

        # Open topics
        topics_json = self.load_stored_topics(self.topics_path)
        
        # Check if its necessary to extend topics 
        if self.check_missing_topics(topics_json) or extent_topics: 
            
            # Extend topics & Open again after extending
            self.extend_topics(n=extension_count)
            topics_json = self.load_stored_topics(self.topics_path)


        # Select the topics that has not been used
        next_topics = {}
        for category, topics_dict in topics_json.items():
            
            # Create list of available topics
            available_topics = [k for k, v in topics_dict.items() if not v]

            # Select the first available topic or warn
            if len(available_topics) > 0: next_topics[category] = available_topics[0]
            else: print(f"[WARN] No available topics in category {category}")

        # Mark selected topics as used and save updated JSON
        for category, topic in next_topics.items(): topics_json[category][topic] = True

        # Update stored topics
        self.update_stored_topics(topics_json)

        # Return the next topics
        return next_topics
