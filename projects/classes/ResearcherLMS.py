import os
import json
from components.LM.LMStudio.LMStudio import LMStudio
from components.Search.GoogleSearchEngine.GoogleSearchEngine import GoogleSearchEngine

class ResearcherLMS:

    def __init__(self, model_id = 'mistralai/magistral-small-2509'):
        self.lms = LMStudio(auto_start=False)
        self.searchClient = GoogleSearchEngine()

        self.active = False
        self.model_id = model_id

    def start(self):
        if self.active: return
        self.lms.start_server()
        self.lms.load_model(self.model_id, config={"contextLength": 8192})
        self.active = True

    def stop(self):
        if not self.active: return
        self.lms.eject_model(self.model_id)
        self.lms.stop_server()
        self.active = False

    
    def get_query(self, category, topic, save_path = None):

        if not self.active: raise RuntimeError('Server has not been start and model has not been loaded')

        messages = [
            {
                "role": "system",
                "content": "You are a reasearch assistant, you will receive categories and questions from a user and you must convert that into research querys. It means you must return a sentece that will be inserted on a web browser in order to find information about what is being ask. You must only return the search query nothing else."
            },
            {
                "role": "user",
                "content": f"Category: {category}\nQuestion: {topic}\nI would like to answer this question investigating on internet. What should I type on my web browser?"
            },
        ]

        params = {
            "temperature": 0.85,
            "top_p": 1.0,
            "max_tokens": 1024,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0,
            "stream": False,
        }

        params["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "qa_schema",
                "schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The research query to be typed on the web browser"
                        }
                    }
                },
                "strict": True
            }
        }
        
        resp = self.lms.generate(messages = messages, parameters=params)
        resp = resp['output']

        if save_path:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(resp, f, indent=2, ensure_ascii=False)

        return resp
    

    def search(self, query, save_path = None):

        results = self.searchClient.search(query['query'], num=4) # list
        answer = { 'web_search': results }

        if save_path:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(answer, f, indent=2, ensure_ascii=False)

        return answer
    
    
    def select_web(self, query, web_results, save_path = None):
        
        if not self.active: raise RuntimeError('Server has not been start and model has not been loaded')

        messages = [
            {
                "role": "system",
                "content": "You are a research assistant and will receive a web search query and a list of results. Web results are a list of dictionaries; each dictionary includes a title, a link, and a snippet. You must help the user select at least one or a maximum of three of these results. These results must be websites where the user can find the most up-to-date information about their search. You must return only the web results JSON file, but only with the selected results."
            },
            {
                "role": "user",
                "content": f"Query: {query}\nWeb Resultus:\n{web_results}\n\nWhich of this results should I select when researching information of the given query?"
            },
        ]

        params = {
            "temperature": 0.6,
            "top_p": 1.0,
            "max_tokens": 2048,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0,
            "stream": False,
        }

        params["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "qa_schema",
                "schema": {
                    "type": "object",
                    "properties": {
                        "selected_results": {
                            "type": "array",
                            "description": "The selected web results",
                            "items": {
                                "type": "object",
                                "properties":{
                                    "title": { "type": "string" },
                                    "link": { "type": "string" },
                                    "snippet": { "type": "string" }
                                },
                                "required": ["title","link","snippet"]
                            },
                            "minItems": 1
                        }
                    },
                    "required": ["selected_results"]
                },
                "strict": True
            }
        }

        resp = self.lms.generate(messages = messages, parameters=params)
        resp = resp['output']

        if save_path:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(resp, f, indent=2, ensure_ascii=False)

        return resp


    def download_htmls(self, selected_results, save_path = None):
        
        resp = {}
        for result in selected_results['selected_results']:
            url = result['link']
            title = result['title']
            try: 
                html = self.searchClient.download_html(url)
            except: 
                print(f'[WARN] Unable to download {url}')
                continue
            resp[title] = html

        if save_path:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(resp, f, indent=2, ensure_ascii=False)

        return resp


    def parse_htmls(self, downloaded_htmls, output_format = "txt", save_path = None):
        
        resp = {}
        for tittle, html in downloaded_htmls.items():
            resp[tittle] = self.searchClient.extract_content(html=html, output_format=output_format) 
        
        if save_path:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(resp, f, indent=2, ensure_ascii=False)

        return resp


    def summarize(self, query, topic, parsed_htmls, timeout=180, save_path = None):

        if not self.active: raise RuntimeError('Server has not been start and model has not been loaded')

        messages = [
            {
                "role": "system",
                "content": (
                    f"You are a professional Research Analyst specialized in synthesizing information. "
                    f"Your task is to create a complete and cohesive summary based on the provided web content. "
                    f"All content is relevant to the general search query: '{query}'.\n\n"
                    f"Your Goal: The final summary must comprehensively address the core topic question: {topic}.\n\n"
                    f"Summary Length and Detail:\n"
                    f"The summary must be concise but comprehensive, limited to 10-15 sentences overall. Do not exceed these limits."
                    f"It must capture all the main points, essential details, and diverse perspectives found across the sources to fully answer the topic question, prioritizing information density over exhaustive detail. \n\n"
                    f"Constraints\n"
                    f"1. Do NOT include any links, URLs, references, or source citations.\n"
                    f"2. Your entire response must be only the summary itself, with no introductory phrases (e.g., 'Here is the summary:') or concluding remarks."
                )
            },
            {
                "role": "user",
                "content": f"Analyze the following parsed website content and generate the summary:\n{parsed_htmls}"
            },
        ]

        params = {
            "temperature": 0.6,
            "top_p": 1.0,
            "max_tokens": 2048,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0,
            "stream": False,
        }

        params["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "qa_schema",
                "schema": {
                    "type": "object",
                    "properties": {
                        "summary": { "type": "string" }
                    },
                    "required": ["summary"]
                },
                "strict": True
            }
        }

        resp = self.lms.generate(messages = messages, parameters=params, timeout=timeout)
        resp = resp['output']

        if save_path:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(resp, f, indent=2, ensure_ascii=False)

        return resp