import json
from classes.ContainerManager import ContainerManager


class TopicManagerOR:

    def __init__(self, model_name:str = "meta-llama/llama-3.3-70b-instruct:free"):
        
        # Start Container
        self.openRouter_container = ContainerManager(image="openrouter:latest", port=8000, use_gpu = False)

        # Set a model
        self.model_name = model_name

        # Set base schema
        self.base_topics_schema = {
            "type": "object",
            "properties": {
                "topics": {
                    "type": "object",
                    "properties": { }
                }
            },
            "required": ["topics"],
            "additionalProperties": False
        }
    
    
    def get_categories(self, topics_path):
        with open(topics_path, "r", encoding="utf-8") as f:
            topics_json = json.load(f)
        return [cat for cat in topics_json.keys()]


    def extend_topics(self, topics_path, n=5):
        """
        Generate new topics for ALL categories in a single LLM call.
        Output must follow the schema:
        {
            "topics": {
                "Category A": ["Question 1?", "Question 2?"],
                "Category B": ["Question 1?", "Question 2?"]
            }
        }
        """

        with open(topics_path, "r", encoding="utf-8") as f:
            topics_json = json.load(f)

        # Flatten existing topics by category
        existing_by_cat = {
            category: list(cat_topics.keys())
            for category, cat_topics in topics_json.items()
        }

        # Build unified prompt
        prompt = f"""
        You are an assistant generating researchable short-form video topics.

        Task:
        - For each of these categories: {list(topics_json.keys())}
        - Suggest up to {n} unique, specific, and concise video topics in the form of **very short questions**.
        - Each topic must be precise enough that someone could research and create a clear, factual 30–60 second video answer.
        - If the category is "Competitive Programming", generate only algorithm, data structure, or coding problem questions.
        - Avoid these existing topics per category: {existing_by_cat}.
        - Do not generate vague or generic ideas, catchy titles, slogans, or clickbait.
        - Ensure each question has potential to grab attention and spark discussion.

        Output rules:
        - Return ONLY valid JSON.
        - Follow this schema exactly:
        {{
        "topics": {{
            "CategoryName": ["Question 1?", "Question 2?"],
            "AnotherCategory": ["Question 1?", "Question 2?"]
        }}
        }}
        """.replace("\t", "").strip()

        # Call LLM (OpenRouter)
        self.openRouter_container.start()
        self.openRouter_client = self.openRouter_container.create_client()
        self.openRouter_client.set_model_name(model_name=self.model_name)
        self.openRouter_client.set_params(temperature=0.9, max_tokens=2048)

        categories = self.get_categories(topics_path)
        schema = self.base_topics_schema
        for cat in categories:
            schema["properties"]["topics"]["properties"][cat] = {
                "type": "array",
                "items": { "type": "string" },
                "minItems": n
            }
        schema["properties"]["topics"]["required"] = categories
        self.openRouter_client.set_schema(schema=schema)

        resp = self.openRouter_client.generate(prompt=prompt, client_timeout=300)
        resp = resp['answer']['output']
        self.openRouter_container.stop()

        # Parse response
        new_topics = resp["topics"]

        # Merge back into topics_json
        for category, ideas in new_topics.items():
            for idea in ideas:
                if idea not in topics_json[category]:
                    topics_json[category][idea] = False

        # Save updated JSON
        with open(topics_path, "w", encoding="utf-8") as f:
            json.dump(topics_json, f, indent=2, ensure_ascii=False)

        return resp
    

    def check_missing_topics(self, topics):
        for _, raw_topics in topics.items():
            available_topics = [k for k in raw_topics.keys() if raw_topics[k] == False]
            if len(available_topics) == 0: return True
        return False


    def get_next_topics(self, topics_path, extend=5):

        # Open topics
        with open(topics_path, "r", encoding="utf-8") as f:
            topics_json = json.load(f)
        
        # Check if its necessary to extend topics 
        if self.check_missing_topics(topics_json):

            # Extend topics
            self.extend_topics(topics_path, extend)

            # Open again after extending
            with open(topics_path, "r", encoding="utf-8") as f:
                topics_json = json.load(f)

        # Select the topics that has not been used
        next_topics = {}
        for category, raw_topics in topics_json.items():
            available_topics = [k for k in raw_topics.keys() if raw_topics[k] == False]
            if len(available_topics) == 0: return None # Failed to generate new topics
            next_topics[category] = available_topics[0]

        # Return the next topics
        return next_topics
