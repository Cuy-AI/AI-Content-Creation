import json
from classes.ContainerManager import ContainerManager

class TopicManager_V1:

    def __init__(self, topics_path: str = None, model_name:str = "meta-llama/llama-3.3-70b-instruct:free"):
        
        # Start Container
        self.openRouter_container = ContainerManager(image="openrouter:latest", port=8000, use_gpu = False)

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
        return topics_json
    
    def update_stored_topics(self, topics_json: dict, topics_path: str = None) -> None:
        topics_path = topics_path or self.topics_path
        with open(topics_path, "w", encoding="utf-8") as f:
            json.dump(topics_json, f, indent=2, ensure_ascii=False)


    def next_topics_prompt(self, topics_json: dict, n:int) -> str:
        """
        Build the prompt to generate new topics.
        This method can be overridden to customize the prompt.
        Input:
          - topics_json: existing topics dictionary
          - n: number of topics to generate per category
        """
        category_list = list(topics_json.keys())
        existing_by_cat = { category: list(topics_dict.keys()) for category, topics_dict in topics_json.items() }
        prompt =  f"You are an assistant generating researchable short-form video topics.\n"
        prompt += f"Task:\n"
        prompt += f"- For each of these categories: {category_list}"
        prompt += f"- Suggest up to {n} unique, specific, and concise video topics in the form of **very short questions**.\n"
        prompt += f"- Each topic must be precise enough that someone could research and create a clear, factual 60 second video answer.\n"
        prompt += f"- If the category is 'Competitive Programming', generate only algorithm, data structure, or coding problem questions.\n"
        prompt += f"- Avoid these existing topics per category:\n"
        prompt += f"{existing_by_cat}\n"
        prompt += f"- Do not generate vague or generic ideas, catchy titles, slogans, or clickbait.\n"
        prompt += f"- Ensure each question has potential to grab attention and spark discussion."
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
        prompt = self.next_topics_prompt(topics_json, n)

        # Call LLM (OpenRouter)
        self.openRouter_container.start()
        self.openRouter_client = self.openRouter_container.create_client()
        self.openRouter_client.set_model_name(model_name=self.model_name)
        self.openRouter_client.set_params(temperature=0.9, max_tokens=2048)

        # Build schema
        schema = self.base_topics_schema
        for cat in category_list:
            schema["properties"][cat] = {
                "type": "array",
                "items": { "type": "string" },
                "minItems": n
            }
        schema["required"] = category_list
        self.openRouter_client.set_schema(schema=schema)

        # Generate response
        try:
            response = self.openRouter_client.generate(prompt=prompt, client_timeout=300)
            response = response['answer']['output']
        except Exception as e:
            print("[ERROR] LLM generation failed:", str(e))
            return False
        
        # Stop container
        self.openRouter_container.stop()

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


    def get_next_topics(self, extent_topics = True, extension_count = 5):

        # Open topics
        topics_json = self.load_stored_topics(self.topics_path)
        
        # Check if its necessary to extend topics 
        if self.check_missing_topics(topics_json) and extent_topics: 
            
            # Extend topics & Open again after extending
            self.extend_topics(extension_count)
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
