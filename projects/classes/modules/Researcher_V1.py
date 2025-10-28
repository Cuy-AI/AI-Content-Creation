import json
import time

from prefect import task
from prefect.cache_policies import NO_CACHE
from projects.classes.Workflow import Workflow
from projects.classes.Workflow import Converters

from components.LM.LMStudio.LMStudio import LMStudio
from components.Search.DuckDuckGoSearch.DuckDuckGoSearch import DuckDuckGoSearch


class Researcher_V1:

    def __init__(self, workflow: Workflow, model_id = 'qwen/qwen3-4b-2507'):
        self.lms = LMStudio(auto_start=False)
        self.searchClient = DuckDuckGoSearch()
        self.workflow = workflow # Reference the workflow to use it's decorator

        self.current_category = "."
        self.active = False
        self.model_id = model_id
        self.timeout = 180  # Timeout for LM responses in seconds

    def start(self):
        if self.active: return
        self.lms.start_server()
        self.lms.load_model(self.model_id, config={"contextLength": 24000}) # Requires larger context for research & summary
        self.lms.set_mcp_tool(self.web_research)
        self.active = True

    def stop(self):
        if not self.active: return
        self.lms.eject_model(self.model_id)
        self.lms.stop_server()
        self.active = False


    def generate_messages(self, category: str, topic:str) -> list:
        """
        Generate the message list for the research request.
        This method can be overridden to customize the messages.
        """
        current_year = time.localtime().tm_year
        messages = [
            {
                "role": "user",
                "content": (
                    f"You are an expert researcher and explainer specialized in {category} topics.\n"
                    f"Your task is to search the web and produce a concise and well-structured report about:\n"
                    f"Topic: {topic}\n\n"
                    f"Your Goal:"
                    f"Provide useful, non-trivial knowledge that would inform someone who already understands the basics of {category} but wants to gain deeper, practical, or conceptual insight.\n"
                    f"Avoid beginner-level explanations. Your objective public are {category} college students and {category} seniors.\n"
                    f"Write in a tone that's clear and information-dense, suitable for use in educational content.\n"
                    f"To make the topic even more interesting, include up-to-date {current_year} information, news about the topic, real world examples, etc.\n"
                    f"If web_research returns invalid content, create your report with your own knowledge."
                    f"Only output the report. Don't include emojis, links, external references or tables. Just text."
                )
            },
        ]
        return messages


    def get_mcp_tools(self) -> list:
        """Return the list of MCP tools used by the researcher."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "web_research",
                    "description": "Perform a web search to gather information on a given query",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The search query string"
                            },
                            "num_results": {
                                "type": "integer",
                                "description": "Number of search results to retrieve",
                                "default": 3
                            }
                        },
                        "required": ["query"]
                    }
                }
            }
        ]


    @task(name="collect-urls", description="Collect URLs for a given research query", cache_policy=NO_CACHE)
    def collect_urls(self, query:str, num_results: int = 4) -> dict:
        """Tool function to collect URLs for a given query using DuckDuckGo."""
        results = self.searchClient.search_web(query, num_results=num_results)
        return { r['title']: r['url'] for r in results }

    @task(name="download-htmls", description="Download HTMLs for a set of urls", cache_policy=NO_CACHE)
    def download_htmls(self, urls: dict) -> dict:
        """Tool function to download HTML content from a given URL."""
        htmls = {} 
        for title, url in urls.items():
            try: htmls[title] = self.searchClient.download_html(url)
            except Exception as e: print(f"Error downloading HTML for {url}: {str(e)}")
        return htmls
    
    @task(name="extract-contents", description="Extract contents from a list of HTMLs", cache_policy=NO_CACHE)
    def extract_contents(self, htmls: dict) -> dict:
        """Tool function to extract main content from a list of HTMLs using trafilatura."""
        contents = { title: self.searchClient.extract_content(html, output_format="txt") for title, html in htmls.items() }
        return contents


    @task(name="web-research", description="Perform web research for a given query", cache_policy=NO_CACHE)
    def web_research(self, query: str, num_results: int = 3) -> str:
        """
        Tool function to perform web research using DuckDuckGo.
        Uses the stored_result decorator from the workflow
        """

        urls = self.workflow.stored_result(
            path = f'2 - research_topics/1 - urls/{self.current_category}.json', 
            converter = Converters.DictionaryConverter
        )(self.collect_urls)(query, num_results=num_results)

        htmls = self.workflow.stored_result(
            path = f'2 - research_topics/2 - htmls/{self.current_category}.json',
            converter = Converters.DictionaryConverter
        )(self.download_htmls)(urls)

        content = self.workflow.stored_result(
            path = f'2 - research_topics/3 - content/{self.current_category}.json',
            converter = Converters.DictionaryConverter
        )(self.extract_contents)(htmls)

        combined_content = ""
        for title, cont in content.items(): combined_content += f"TITLE: {title}\nCONTENT:\n{cont}\n\n"

        return combined_content


    def request_research(self, category: str, topic:str) -> str:

        if not self.active: raise RuntimeError('Server has not been started and model has not been loaded')

        self.current_category = category.replace(' ','_') # The stored_result decorators will use this to store results
        messages = self.generate_messages(category, topic)

        # Set up parameters
        params = {}

        # Set up mcp tool for web research
        mcp_tools = self.get_mcp_tools()
        resp = self.lms.generate(messages=messages, parameters=params, mcp_tools=mcp_tools, timeout=self.timeout)

        return resp['output']
    