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
        current_date = time.strftime("%d %B %Y")
        messages = [
            {
                "role": "user",
                "content": (
                    f"You are an LLM specialized in {category}.\n"
                    f"Your sole task is to update your knowledge using very recent information related to:\n"
                    f"Topic: {topic}\n\n"
                    f"--- PRIMARY OBJECTIVE ---\n"
                    f"Perform focused research on *recent news, updates, incidents, releases, discoveries, "
                    f"or shifts* related to this topic. Do NOT produce a full historical or conceptual deep-dive. "
                    f"Your job is to refresh your understanding based strictly on the newest credible developments."
                    f"You should research everything from current year updates to the latest news. Current date: {current_date}\n\n"
                    f"--- WEB RESEARCH RULES ---\n"
                    f"- You may run up to TWO (2) web_research calls only.\n"
                    f"- Each must:\n"
                    f"  • use num_results=2\n"
                    f"  • target high-quality, recent sources\n"
                    f"  • search for: breaking news, regulatory changes, new vulnerabilities, outages, "
                    f"    academic papers, product launches, strategic industry moves, funding shifts, "
                    f"    technological breakthroughs, or major company announcements\n"
                    f"- If results are irrelevant or low quality, discard them.\n\n"
                    f"--- REPORT REQUIREMENTS ---\n"
                    f"Produce a highly informative update with only what is *new* and why it matters.\n"
                    f"Your report must include:\n"
                    f"- A summary of the most relevant recent news or developments.\n"
                    f"- The technical or strategic implications of what changed.\n"
                    f"--- STYLE GUIDELINES ---\n"
                    f"- Write like a professional intelligence brief.\n"
                    f"- No fluff, no filler, no beginner explanations.\n"
                    f"- Every sentence must deliver new, meaningful information.\n"
                    f"- Use precise technical language.\n"
                    f"- Do NOT use emojis, links, tables, or lists of URLs.\n"
                    f"- Plain text only.\n\n"
                    f"--- OUTPUT ---\n"
                    f"Only output the final report.\n"
                    f"It should have 400 words aprox, and must be modern, and focused entirely on updating your knowledge with the latest information.\n"
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
    