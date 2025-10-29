from time import time

# Workflow
from prefect import flow, task
from prefect.cache_policies import NO_CACHE
from projects.classes.Workflow import Workflow
from projects.classes.Workflow import Serializers
from projects.classes.Workflow import Converters

# Modules
from projects.classes.modules.TopicManager_V1 import TopicManager_V1
from projects.classes.modules.Researcher_V1 import Researcher_V1
from projects.classes.modules.ScriptGenerator_V1 import ScriptGenerator_V1

# Workflow Creation ===================================================================================
LoreLabsWorkflow = Workflow(
    base_path='volume/output/LoreLabs/Workflow2', # Path were the workflow will create folders/files to store executions
    # execution_id=None, # Will generate a new execution id
    execution_id=0, # Will run an specific execution
    storage_block_name='lorelabs-workflow1-storage', # Prefect storage block
    id_path_digits=5, # Number of digits for the id 
)


# Workflow Configuration ==============================================================================
@task(name="workflow-config", description="Configures the workflow as needed", cache_policy=NO_CACHE)
def config_workflow():
    print("\n[STEP] Configuring the workflow...") 


# Topic Generation ====================================================================================
@task(
    name = "topic-generation", 
    description = "Generates or Selects a topic for each video category.",
    cache_key_fn = lambda context, inputs: '1 - generate_topics/topics.json',
    result_serializer = Serializers.DictionarySerializer(),
    result_storage = LoreLabsWorkflow.result_storage
)
def generate_topics(branch:str = 'cs') -> dict:
    print("\n[STEP] Generating topics...") 
    topicManager = TopicManager_V1(topics_path=f'projects/LoreLabs/data/topics/topics_{branch}.json',)
    return topicManager.get_next_topics()
   

# Topic Researching ===================================================================================
@task(name="researching-step", description="Launch a research task for each topic", cache_policy=NO_CACHE)
def research_multiple_topics(topics:dict) -> list:
    print("\n[STEP] Researching topics...") 
    research = [ research_topic(category, topic) for (category, topic) in topics.items()]
    if 'researcher' in globals(): researcher.stop() # Stop only if created
    return research


@task(
    name = "research-topic", 
    description = "Research a single topic",
    cache_key_fn = lambda context, inputs: f'2 - research_topics/4 - summaries/{inputs['category'].replace(' ','_')}.json',
    result_serializer = Serializers.DictionarySerializer(),
    result_storage = LoreLabsWorkflow.result_storage
)
def research_topic(category: str, topic: str) -> dict:

    # Check if researcher exists
    if 'researcher' not in globals(): 
        global researcher
        researcher = Researcher_V1(workflow=LoreLabsWorkflow)
        researcher.start()

    summary = researcher.request_research(category, topic)
    return {
        "category": category,
        "topic": topic,
        "summary": summary
    }


# Script Generation ===============================================================================
@task(name="script-generation-step", description="Launch a script generation task for each researched topic", cache_policy=NO_CACHE)
def generate_multiple_scripts(research: list) -> list:
    print("\n[STEP] Generating scripts...") 
    scripts = [ generate_script(item['category'], item['topic'], item['summary']) for item in research]
    if 'scriptGenerator' in globals(): scriptGenerator.stop() # Stop only if created
    return scripts


@LoreLabsWorkflow.stored_result(
    path = lambda *a, **kw: f'3 - generate_scripts/{a[0].replace(" ","_")}.json',
    converter = Converters.DictionaryConverter
)
def generate_script(category: str, topic: str, summary: str) -> dict:

    # Check if scriptGenerator exists
    if 'scriptGenerator' not in globals(): 
        global scriptGenerator
        scriptGenerator = ScriptGenerator_V1()
        scriptGenerator.start()

    script = scriptGenerator.generate_script(category, topic, summary)
    return {
        "category": category,
        "topic": topic,
        "script": script
    }


# Main Workflow ===================================================================================
@flow(
    name='LoreLabs - Workflow1',
    description="An end-to-end workflow to create educational videos using AI.",
    flow_run_name=f"LoreLabs-Workflow1-{LoreLabsWorkflow.execution_id}"
)
def start(branch):

    # Step 0 - Set up workflow
    config_workflow()

    # Step 1 - Generate topics
    topics = generate_topics(branch)

    # Step 2 - Research Topics
    research = research_multiple_topics(topics)

    # # Step 3 - Generate Scrips
    scripts = generate_multiple_scripts(research)

    # # Step 4 - Search Images
    # images = collect_images(scripts)

    # # Step 5 - Voices
    # voices = None

    # # Step 6 - Build Videos
    # video = None

    
    
def workflow(branch='cs'):

    print("\n\n\t\t\t *** STARTING THE EXECUTION ***\n")
    global_start = time()

    # Launch workflow
    start(branch)

    print(f"\n[DONE] Complete workflow finished after {time() - global_start:.2f}s")
    print("\n\n\t\t\t *** FINISHING EXECUTION ***\n")