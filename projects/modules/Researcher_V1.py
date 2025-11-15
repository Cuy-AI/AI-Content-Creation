import time

from prefect import task
from prefect import get_run_logger
from prefect.cache_policies import NO_CACHE

from components.LM.LMStudio.LMStudio import LMStudio
from components.Search.DuckDuckGoSearch.DuckDuckGoSearch import DuckDuckGoSearch


class Researcher_V1:

    def __init__(self,  model_id = 'qwen/qwen3-4b-2507'):
        self.lms = LMStudio(auto_start=False)
        self.searchClient = DuckDuckGoSearch()

        self.active = False
        self.model_id = model_id
        self.timeout = 200  # Timeout for LM responses in seconds

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
                    f"You are an elite technical researcher specialized in {category}.\n"
                    f"Your task is to perform deep, high-value research about the following topic:\n"
                    f"Topic: {topic}\n\n"
                    f"--- YOUR GOAL ---\n"
                    f"Produce an information-dense, highly engaging report full of insights that even "
                    f"{category} professionals and senior students would find surprising, valuable, and worth sharing.\n"
                    f"This report must feel like:\n"
                    f"- A mix of expert breakdown + insider industry context\n"
                    f"- Dense with non-obvious facts, mechanisms, examples, historical notes, failures, edge cases, and {current_year} updates\n"
                    f"- Content that grabs attention because it's something people *didn't know they wanted to know*\n"
                    f"- Focused on depth, nuance, and real-world impact, NOT beginner explanations\n\n"
                    f"--- STYLE REQUIREMENTS ---\n"
                    f"- No fluff, no filler, no generic definitions\n"
                    f"- Every sentence must carry meaningful, specific information\n"
                    f"- Use clear, precise, technical language\n"
                    f"- Avoid emojis, links, tables, citations, or lists of URLs\n"
                    f"- Plain text only\n\n"
                    f"--- WEB RESEARCH INSTRUCTIONS ---\n"
                    f"- It's mandatory to run up to TWO (3) web_research calls (NO MORE). Each call must:\n"
                    f"- target highly credible sources\n"
                    f"- use num_results=2\n"
                    f"- look for: modern papers, industry engineering blogs, architecture deep dives, "
                    f"incident reports, benchmarks, scaling stories, new vulnerabilities, or recent breakthroughs\n"
                    f"- If web_research returns invalid or low-quality results, ignore them and rely on your own knowledge.\n\n"
                    f"--- CONTENT REQUIREMENTS ---\n"
                    f"Your final report MUST include:\n"
                    f"1. A short, high-impact introduction that immediately hooks the reader with why this topic is deeper than it looks.\n"
                    f"2. The underlying mechanisms, principles, or math behind the idea.\n"
                    f"3. Modern {current_year} developments, ongoing research directions, or changes in industry practice.\n"
                    f"4. At least one real-world example involving major companies, systems, protocols, or failures.\n"
                    f"5. At least one counterintuitive insight or misconception that people commonly get wrong.\n"
                    f"6. Future implications or open problems that experts still debate.\n"
                    f"7. Close with a crisp summary of the most surprising takeaways.\n\n"
                    f"--- OUTPUT ---\n"
                    f"Only output the final report.\n"
                    f"It should read like a mini-whitepaper: tight, insightful, and packed with useful technical content.\n"
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
            except Exception as e:
                log = get_run_logger()
                log.warning(f"Couldn't downloading HTML for {url}: {str(e)}")
        return htmls
    
    @task(name="extract-contents", description="Extract contents from a list of HTMLs", cache_policy=NO_CACHE)
    def extract_contents(self, htmls: dict) -> dict:
        """Tool function to extract main content from a list of HTMLs using trafilatura."""
        contents = { title: self.searchClient.extract_content(html, output_format="txt") for title, html in htmls.items() }
        return contents


    @task(
        name="web-research",
        description="Perform web research for a given query", 
        task_run_name = "web-research: {query}",
        cache_policy=NO_CACHE
    )
    def web_research(self, query: str, num_results: int = 3) -> str:
        """
        Tool function to perform web research using DuckDuckGo.
        Uses the stored_result decorator from the workflow
        """

        urls = self.collect_urls(query, num_results=num_results)
        htmls = self.download_htmls(urls)
        content = self.extract_contents(htmls)

        combined_content = ""
        for title, cont in content.items(): combined_content += f"TITLE: {title}\nCONTENT:\n{cont}\n\n"

        return combined_content


    def request_research(self, category: str, topic:str) -> str:

        if not self.active: raise RuntimeError('Server has not been started and model has not been loaded')

        messages = self.generate_messages(category, topic)

        # Set up parameters
        params = {}

        # Set up mcp tool for web research
        mcp_tools = self.get_mcp_tools()
        resp = self.lms.generate(messages=messages, parameters=params, mcp_tools=mcp_tools, timeout=self.timeout)

        return resp['output']
    