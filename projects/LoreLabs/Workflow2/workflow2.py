from time import time
from prefect import flow, task
from projects.classes.Workflow import Workflow

# Modules
from projects.classes.modules.TopicManager_V1 import TopicManager_V1


myWorkflow = Workflow(
    base_path='volume/output/LoreLabs/Workflow2', # Path were the workflow will create folders/files to store executions
    # execution_id=None, # Will generate a new execution id
    execution_id=0, # Will run an specific execution
    id_path_digits=5, # Number of digits for the id 
)


# Workflow Configuration ==============================================================================
@task(name="workflow-config", description="Configures the workflow as needed")
def config_workflow():
    global myWorkflow
    print("[STEP] Configuring the workflow...") 


# Topic Generation ===================================================================================
@task(name="topic-generation", description="Generates/Selects a topic for each video category.")
@myWorkflow.stored_result('1 - generate_topics/topics.json')
def generate_topics(branch:str = 'cs') -> dict:
    print("[STEP] Generating topics...") 
    topicManager = TopicManager_V1(topics_path=f'projects/LoreLabs/data/topics/topics_{branch}.json',)
    return topicManager.get_next_topics()
   

# Topic Researching ===================================================================================
@task(name="topics-researching", description="Launch a research task for each topic")
def research_multiple_topics(topics:dict) -> list:

    print("[STEP] Researching topics...") 

    categories_topics = list(topics.items())
    num_topics = len(categories_topics)

    research = [
        research_topic(category, topic, stop=(i == num_topics - 1))
        for i, (category, topic) in enumerate(categories_topics)
    ]
        
    return research


@task(name="single-research", description="Research a single topic")
@myWorkflow.stored_result(lambda *a, **kw: f"2 - research_topic/{a[0].replace(' ','_')}.json")
def research_topic(category: str, topic: str, stop:bool = False) -> dict:
    return {
        "category": category,
        "topic": topic,
        "Summary": f"Investigation: sdfsadfasf {category} - {topic} - {stop}",
    }


# Script Generation ===================================================================================
@task(name="scripts-generation", description="Generates a script for each researched topic")
def generate_multiple_scripts(research: list) -> list:
    print("[STEP] Generating scripts...") 

    scripts = [
        generate_script(item['category'], item['topic'], item['Summary'])
        for item in research
    ]
        
    return scripts


@task(name="single-script-generation", description="Generates a script for a single researched topic")
@myWorkflow.stored_result(lambda *a, **kw: f"3 - generate_script/{a[0].replace(' ','_')}.json")
def generate_script(category: str, topic: str, research_summary: str) -> dict:
    return {
        "category": category,
        "topic": topic,
        "script": {
            "title": f"Video about {topic}",
            "description": f"This video covers the topic of {topic} in the category of {category}.",
            "scenes": [
                {"character": "Host", "dialogue": f"Welcome to our video on {topic}.", "image_prompt": f"A welcoming host for a video about {topic}."},
                {"character": "CharA", "dialogue": f"Let's explore  {topic}.", "image_prompt": f"A host explaining key aspects of {topic}."},
                {"character": "CharB", "dialogue": f"Thank you for watching .", "image_prompt": f"A host thanking viewers for watching a video about {topic}."},
            ]
        },
    }


# Search Images ===================================================================================
@task(name="collect-images", description="Launch an image collecter per script")
def collect_images(scripts: list) -> list:
    print("[STEP] Collecting images...") 
    images_per_script = [collect_images_for_script(script) for script in scripts ]
    return images_per_script


@task(name="script-image-collector", description="Search and download images for a single script")
def collect_images_for_script(script: dict) -> dict:
    images = {}
    return images


# Main Workflow ===================================================================================
@flow(name='LoreLabs - Workflow1: Video creation')
def start(branch):

    # Step 0 - Set up workflow
    config_workflow()

    # Step 1 - Generate topics
    topics = generate_topics(branch)

    # Step 2 - Research Topics
    research = research_multiple_topics(topics)

    # Step 3 - Generate Scrips
    scripts = generate_multiple_scripts(research)

    # Step 4 - Search Images
    images = collect_images(scripts)

    # Step 5 - Voices
    voices = None

    # Step 6 - Build Videos
    video = None

    
    
def workflow(branch='cs'):

    print("\n\n\t\t\t *** STARTING THE EXECUTION ***\n")
    global_start = time()

    # Launch workflow
    start(branch)

    print(f"\n[DONE] Complete workflow finished after {time() - global_start:.2f}s")
    print("\n\n\t\t\t *** FINISHING EXECUTION ***\n")