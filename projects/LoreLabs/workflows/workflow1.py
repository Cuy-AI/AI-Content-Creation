from time import time
from pathlib import Path

# Workflow
from prefect import flow, task
from prefect.cache_policies import NO_CACHE
from classes.Workflow import Workflow
from classes.Workflow import Serializers
from classes.Workflow import PersistentResult
from classes.Workflow import Utils

# Modules
from projects.modules.TopicManager_V1 import TopicManager_V1
from projects.modules.Researcher_V1 import Researcher_V1
from projects.modules.ScriptGenerator_V1 import ScriptGenerator_V1
from projects.modules.ImageCollector_V1 import ImageCollector_V1
from projects.modules.VoiceGenerator_V1 import VoiceGenerator_V1
from projects.modules.VideoBuilder_V1 import VideoBuilder_V1

# Workflow Creation ===================================================================================
LoreLabsWorkflow = Workflow(
    base_path='volume/output/LoreLabs/Workflow 1', # Path were the workflow will create folders/files to store executions
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
def researching_step(topics:dict) -> list:
    print("\n[STEP] Researching topics...") 
    research = [ research_topic(category, topic) for (category, topic) in topics.items()]
    if 'researcher' in globals(): researcher.stop() # Stop only if created
    return research


@task(
    name = "research-topic", 
    description = "Research a single topic",
    task_run_name = "research-{topic}",
    cache_key_fn = lambda context, inputs: f'2 - research_topics/{inputs['category']}.json',
    result_serializer = Serializers.DictionarySerializer(),
    result_storage = LoreLabsWorkflow.result_storage
)
def research_topic(category: str, topic: str) -> dict:

    # Check if researcher exists
    if 'researcher' not in globals(): 
        global researcher
        researcher = Researcher_V1()
        researcher.start()

    summary = researcher.request_research(category, topic)
    return {
        "category": category,
        "topic": topic,
        "summary": summary
    }


# Script Generation ===================================================================================
@task(name="script-generation-step", description="Launch a script generation task for each researched topic", cache_policy=NO_CACHE)
def generate_multiple_scripts(research: list) -> list:
    print("\n[STEP] Generating scripts...") 
    scripts = [ generate_script(item['category'], item['topic'], item['summary']) for item in research]
    if 'scriptGenerator' in globals(): scriptGenerator.stop() # Stop only if created
    return scripts


@PersistentResult.stored_result(
    cache_key = f'{LoreLabsWorkflow.workflow_path}/3 - generate_scripts/{{arg0}}.json',
    loader = PersistentResult.Converters.DictionaryLoader,
    saver = PersistentResult.Converters.DictionarySaver,
)
@task(
    name="script-generation", 
    description="Generates a script for a given category-topic", 
    task_run_name="script-generation: {topic}", 
    cache_policy=NO_CACHE
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


# Image Collection ====================================================================================
@task(name="image-collection-step", description="Collect images for each script", cache_policy=NO_CACHE)
def collect_web_images(scripts: list) -> list:
    print("\n[STEP] Collecting images...") 
    images_per_script = [ # List of dicts
        {
            str(scene["id"]): get_image(script['category'], scene["id"], scene["web_image"]) 
            for scene in script['script']['scenes'] if scene.get("web_image", None)
        }
        for script in scripts
    ]
    return images_per_script



def web_images_solver(cache_key: str, args: tuple, kwargs: dict) -> Path:
    '''Receives a folder as cache key instead of a file'''

    solved_cache_key:Path = PersistentResult.DefaultSolver(cache_key, args, kwargs)

    valid_extensions = ('.png', '.jpg', 'jpeg', 'webp', 'tiff', 'gif')

    parent = solved_cache_key.parent
    file_name = solved_cache_key.name
    
    # Check if folder exists
    if not parent.is_dir(): return solved_cache_key

    # Check files inside the directoy
    for file in parent.iterdir():
        if not file.is_file(): continue
        if file.stem == file_name and file.suffix in valid_extensions: 
            return file
    
    return solved_cache_key


def web_images_verifier(solved_cache_key: Path) -> bool:
    # Check if the path is valid, throw error if not
    Utils.validate_path(solved_cache_key)

    # Return True if path exist and is a file
    return solved_cache_key.exists() and solved_cache_key.is_file()
        

@PersistentResult.stored_result(
    cache_key = f'{LoreLabsWorkflow.workflow_path}/4 - web_images/{{arg0}}/scene-{{arg1}}', # .png / .jpg / .jpeg / ...
    solver = web_images_solver,
    verifier = web_images_verifier,
    # Default loader and saver as None work fine
)
@task(
    name = "collect-single-image", 
    task_run_name="collect-single-image: {category}-{id}", 
    description = "Collect images for a single script", 
    cache_policy=NO_CACHE
)
def get_image(category:str, id:int, query: str) -> str:
    saving_path = LoreLabsWorkflow.workflow_path / Path(f"4 - web_images/{category}/scene-{id}")

    # Check if imageCollector exists
    if 'imageCollector' not in globals(): 
        global imageCollector
        imageCollector = ImageCollector_V1()

    return imageCollector.search_image(query, saving_path, size="Large", ratio="horizontal", min_w=750, n_results = 4)



# Voice Generation ====================================================================================
@task(name = "voice-generation-step", description = "Generates voices for all scripts and scenes", cache_policy=NO_CACHE)
def voice_generation_step(scripts: list):
    print("\n[STEP] Generating Voices...") 
    voices_per_script = [ # List of lists
        [ 
            get_audio(script['category'], scene["id"], scene["dialogue"], scene["character"]) 
            for scene in script['script']['scenes']
        ]
        for script in scripts
    ]
    if 'voiceGenerator' in globals(): voiceGenerator.stop()
    return voices_per_script


@PersistentResult.stored_result(
    cache_key = f'{LoreLabsWorkflow.workflow_path}/5 - generate_audio/{{arg0}}/scene-{{arg1}}.wav',
    # Default loader and saver as None work fine
)
@task(
    name = "generate-voice",
    description = "Generate audio for a single scene",
    task_run_name="generate-voice: {category}-{id}",
    cache_policy=NO_CACHE
)
def get_audio(category:str, id:int, dialogue: str, character:str):

    saving_path = f'{str(LoreLabsWorkflow.workflow_path)}/5 - generate_audio/{category}/scene-{id}.wav'

    # Check if voiceGenerator exists
    if 'voiceGenerator' not in globals(): 
        global voiceGenerator
        voiceGenerator = VoiceGenerator_V1(resource_folder='volume/resources/LoreLabs/voices/')
        voiceGenerator.start()
        voiceGenerator.character_params.update({
            "rick": { "temperature": 0.75, "exaggeration": 0.55, "cfg_weight": 0.5 },
            "morty": { "temperature": 0.65, "exaggeration": 0.55, "cfg_weight": 0.5 },
        })

    result = voiceGenerator.generate_voice(dialogue, character, 'en', saving_path)
    return result['save_path']
    


# Video Builder =======================================================================================
@task(name = "build-video-step", description = "Generates all the videos for each topic", cache_policy=NO_CACHE)
def build_video_step(scripts: list, audios:list, images:list):
    print("\n[STEP] Generating Videos...") 
    voices_per_script = [ 
        build_video(script, audio_list, image_dict) 
        for script, audio_list, image_dict in zip(scripts, audios, images)
    ]
    if 'videoBuilder' in globals(): videoBuilder.stop()
    return voices_per_script


@PersistentResult.stored_result(
    cache_key = lambda *args, **kwargs: f'{LoreLabsWorkflow.workflow_path}/6 - build_video/{args[0]['category']}.mp4',
    # Default loader and saver as None work fine
)
@task(name = "build-video", description = "Generates a single video for a topic", cache_policy=NO_CACHE)
def build_video(script: dict, audio_list:list, image_dict:dict):

    save_path = f'{LoreLabsWorkflow.workflow_path}/6 - build_video/{script['category']}.mp4'

    # Check if videoBuilder exists
    if 'videoBuilder' not in globals(): 
        global videoBuilder
        videoBuilder = VideoBuilder_V1(background_video="volume/resources/videos/background/minecraft/videoplayback.webm")
        videoBuilder.start()

    path = videoBuilder.build_full_video(script['script'], audio_list, image_dict, save_path)
    print(f"[INFO] Video saved at: {path}")
    return path


# Main Workflow =======================================================================================
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
    research = researching_step(topics)

    # Step 3 - Generate Scrips
    scripts = generate_multiple_scripts(research)

    # Step 4 - Search Images
    web_images = collect_web_images(scripts)

    # Step 5 - Voices
    voices = voice_generation_step(scripts)

    # Step 6 - Build Videos
    video = build_video_step(scripts, voices, web_images)

    
    
def workflow(branch='cs'):

    print("\n\n\t\t\t *** STARTING THE EXECUTION ***\n")
    global_start = time()

    # Launch workflow
    start(branch)

    print(f"\n[DONE] Complete workflow finished after {time() - global_start:.2f}s")
    print("\n\n\t\t\t *** FINISHING EXECUTION ***\n")