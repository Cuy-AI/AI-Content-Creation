import os
import json
import inspect

from projects.classes.TopicManagerOR import TopicManagerOR
from projects.classes.ResearcherLMS import ResearcherLMS
from projects.classes.ScriptGenerator import ScriptGenerator
from projects.classes.VoiceGenerator import VoiceGenerator
from projects.classes.ImageDownloader import ImageDownloader

# GLOBALS ---------------------------------------------------------------------------------------
project_name = 'LoreLabs'
workflow_name = 'workflow1'
base_path = f'volume/output/{project_name}/{workflow_name}/'

execution_id = None
workflow_path = None

researcher = None
scriptGenerator = None
voiceGenerator = None
imageDownloader = None


# UTILS -----------------------------------------------------------------------------------------
def int2id(id: int, digits:int = 4) -> str:
    id_str = str(id)
    if len(id_str) > digits:
        raise ValueError(f"id '{id}' has more than {digits} digits")
    return id_str.zfill(digits)

def check_saved_output(folder_path: str, extensions: None | list[str] = None, full_path:bool = True) -> list[str]:

    files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]

    if extensions is not None:
        files = [f for f in files if any(f.endswith(ext) for ext in extensions)]

    if full_path: 
        files = [folder_path + f for f in files]

    return files

# STEPS -----------------------------------------------------------------------------------------

def set_up_environment(exe_id: None|int|str = None):

    global execution_id
    global workflow_path

    print('\n[STEP] Set up environment')

    if exe_id is not None: # If execution id is provided

        # If int, convert to string
        if isinstance(exe_id, int): exe_id = int2id(exe_id)

        # Set up environment
        execution_id = exe_id
        workflow_path = base_path + execution_id + '/'
        os.makedirs(workflow_path, exist_ok=True)

    else: # If execution id is not provided

        # Check for all existing folders (ids) inside basepath 
        folders = [f for f in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, f))]

        if not folders: # If not folders, use id = 0
            execution_id = int2id(0)
        else: # Find the highest existing id and increment
            max_id = max(int(f) for f in folders if f.isdigit())
            execution_id = int2id(max_id + 1)

        workflow_path = base_path + execution_id + '/'
        os.makedirs(workflow_path, exist_ok=True)

    print(f'[INFO] Execution ID  = {execution_id}')
    print(f'[INFO] Workflow Path = {workflow_path}')


def load_topics(branch:str = 'cs'):

    print("\n[STEP] Load topics")

    # Set up output directory
    function_name = inspect.currentframe().f_code.co_name # Get function name
    output_folder = workflow_path + function_name + '/'

    # Check if already saved output
    if os.path.exists(output_folder): # If output folder exist, check what is inside
        saved = check_saved_output(output_folder, extensions=['.json'])
    else: # If not, create it and execute step
        os.makedirs(output_folder, exist_ok=True)
        saved = []


    if len(saved) > 1: # Do not accept multiple files as saved output
        print("[ERROR] This step doesn't accept multiple output files")
        raise ValueError(f"Should only be a topic json file, found {saved}")

    elif len(saved) == 0: # Not saved output. Get / Generate new topics
        
        print("[INFO] Getting/Generating topics...")        

        full_topics = f'projects/LoreLabs/topics/topics_{branch}.json'
        output_path = output_folder + 'topics.json'

        topicManager = TopicManagerOR()
        topics_json = topicManager.get_next_topics(topics_path=full_topics, extend=7)
        
        if topics_json is None: # Fail
            print("[ERROR] TopicManager failed to generate new topics for each category...")
            raise RuntimeError("TopicManager failed to generate new topics for each category")
        
        # Save step output
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(topics_json, f, indent=2, ensure_ascii=False)

        print("[INFO] Generated topics:")
        for k, v in topics_json.items(): print(f"[INFO] {k} -> {v}")
        
        # return step output
        return topics_json
    
    else: # Saved output found
        
        # There is only one file (step saved output)
        saved = saved[0]

        # load saved topics.json file
        with open(saved, "r", encoding="utf-8") as f:
            topics_json = json.load(f)

        # Print loaded
        print("[INFO] Loaded topics:")
        for k, v in topics_json.items(): print(f"[INFO] {k} -> {v}")

        return topics_json



def research_topics(category:str, topic: str, stop: bool = False):

    global researcher

    print(f"\n[STEP] Researching: {category} - {topic}...")

    # Replace or remove characters that are invalid in file paths
    invalid_chars = r'\/:*"<> '
    fixed_cat = ''.join(c if c not in invalid_chars else '_' for c in category.lower()).replace("?", "").replace("'", "")
    
    # Set up output directory
    function_name = inspect.currentframe().f_code.co_name # Get function name
    output_folder = workflow_path + function_name + f"/{fixed_cat}/"

    # Check if already saved output
    if os.path.exists(output_folder): # If output folder exist, check what is inside
        saved = check_saved_output(output_folder, extensions=['.json'])
    else: # If not, create it and execute step
        os.makedirs(output_folder, exist_ok=True)
        saved = []


    # Sub step 1 - Create google search query ---------------------
    save_path = output_folder + '1 - query.json'
    if save_path not in saved:
        print('[INFO] Generating query...')

        # Start the researcher class
        if researcher is None:
            researcher = ResearcherLMS(model_id='mistralai/magistral-small-2509')
            researcher.start()

        researcher.get_query(category=category, topic=topic, save_path=save_path)    
    
    with open(save_path, "r", encoding="utf-8") as f:
        query = json.load(f)

    print(f'[INFO] Query: {query['query']}')


    # Sub step 2 - Perform search and collect url's ---------------------
    save_path = output_folder + '2 - web_results.json'
    if save_path not in saved:
        print('[INFO] Searching query...')
        researcher.search(query=query, save_path=save_path)
    
    with open(save_path, "r", encoding="utf-8") as f:
        web_results = json.load(f)

    print(f'[INFO] Web results loaded/saved successfully')
    # for ele in web_results['web_search']: print(f"[INFO] {ele}")


    # Sub step 3 - Selecting the urls to search ---------------------
    save_path = output_folder + '3 - search_selection.json'
    if save_path not in saved:
        print('[INFO] Selecting web...')

        # Start the researcher class
        if researcher is None:
            researcher = ResearcherLMS(model_id='mistralai/magistral-small-2509')
            researcher.start()

        researcher.select_web(query=query['query'], web_results=web_results, save_path=save_path)
    
    with open(save_path, "r", encoding="utf-8") as f:
        selected_results = json.load(f)

    print(f'[INFO] Selected results loaded/saved successfully')
    # for ele in selected_results['selected_results']: print(f"[INFO] {ele['link']}")


    # Sub step 4 - Download html of selected websites ---------------------
    save_path = output_folder + '4 - htmls.json'
    if save_path not in saved:
        print("[INFO] Downlaoding htmls...")
        researcher.download_htmls(selected_results=selected_results, save_path=save_path)

    with open(save_path, "r", encoding="utf-8") as f:
        downloaded_htmls = json.load(f)

    print(f'[INFO] Htmls were loaded/saved successfully')


    # Sub step 5 - Parse downloaded htmls ---------------------
    save_path = output_folder + '5 - parsed_htmls.json'
    if save_path not in saved:
        print('[INFO] Parsing htmls...')
        researcher.parse_htmls(downloaded_htmls=downloaded_htmls, save_path=save_path)
    
    with open(save_path, "r", encoding="utf-8") as f:
        parsed_htmls = json.load(f)

    print(f'[INFO] Html parsed content was loaded/saved successfully')


    # Sub step 6 - Summarize information from the website ---------------------
    save_path = output_folder + '6 - summarize.json'
    if save_path not in saved:
        print('[INFO] Summarizing information...')

        # Start the researcher class
        if researcher is None:
            researcher = ResearcherLMS(model_id='mistralai/magistral-small-2509')
            researcher.start()

        researcher.summarize(category=category, topic=topic, query=query['query'], parsed_htmls=parsed_htmls, timeout=240, save_path=save_path)
    
    with open(save_path, "r", encoding="utf-8") as f:
        summary = json.load(f)

    print(f'[INFO] Summaries were saved successfully')


    # Stop researcher
    if stop and researcher is not None: 
        researcher.stop()
        researcher = None

    # Return summary
    return summary



def generate_script(summary: dict, stop: bool = False):

    global scriptGenerator

    topic = summary['topic']
    category = summary['category']
    print(f"\n[STEP] Generating Script for: {category} - {topic}...")

    # Replace or remove characters that are invalid in file paths
    invalid_chars = r'\/:*"<> '
    fixed_cat = ''.join(c if c not in invalid_chars else '_' for c in category.lower()).replace("?", "").replace("'", "")
    
    # Set up output directory
    function_name = inspect.currentframe().f_code.co_name # Get function name
    output_folder = workflow_path + function_name + "/"
    output_path = output_folder + fixed_cat + '.json'

    # Check if already saved output
    if os.path.exists(output_folder): # If output folder exist, check what is inside
        saved = check_saved_output(output_folder, extensions=['.json'])
    else: # If not, create it and execute step
        os.makedirs(output_folder, exist_ok=True)
        saved = []


    if output_path not in saved: # No saved output
        
        print('[INFO] Generating script...')

        # Start the script generator class
        if scriptGenerator is None:
            scriptGenerator = ScriptGenerator()
            scriptGenerator.start()

        # Generate script
        script = scriptGenerator.generate_script(summary=summary, save_path=output_path)
        
    else: # Saved output found

        # load saved topics.json file
        with open(output_path, "r", encoding="utf-8") as f:
            script = json.load(f)

        # Print loaded
        print("[INFO] Script was loaded successfully")
        

    # Stop ScriptGenerator
    if stop and scriptGenerator is not None: 
        scriptGenerator.stop()
        scriptGenerator = None

    return script



def generate_voices(script: dict, stop: bool = False):
    
    global voiceGenerator

    topic = script['topic']
    category = script['category']
    print(f"\n[STEP] Generating audios: {category} - {topic}...")

    # Replace or remove characters that are invalid in file paths
    invalid_chars = r'\/:*"<> '
    fixed_cat = ''.join(c if c not in invalid_chars else '_' for c in category.lower()).replace("?", "").replace("'", "")
    
    # Set up output directory
    function_name = inspect.currentframe().f_code.co_name # Get function name
    output_folder = workflow_path + function_name + f"/{fixed_cat}/"

    # Check if already saved output
    if os.path.exists(output_folder): # If output folder exist, check what is inside
        saved = check_saved_output(output_folder, extensions=['.json'])
    else: # If not, create it and execute step
        os.makedirs(output_folder, exist_ok=True)
        saved = []

    
    # Check if there is 1 json file on saved. Save that file path into a var
    if len(saved) == 1:
        with open(saved[0], "r", encoding="utf-8") as f:
            audios_paths = json.load(f)

        saved_output_check = True
        for audio_path in audios_paths['scenes']:
            if not os.path.exists(audio_path): 
                print(f'[WARN] Audio {audio_path} was not found.')
                print(f'[WARN] Regenerating all audios for this step.')
                saved_output_check = False
                break

        if saved_output_check:
            print('[INFO] Audios and metadata were loaded sucessfully')
            return audios_paths


    print('[INFO] Generating audios...')

    if voiceGenerator is None:
        voiceGenerator = VoiceGenerator()
        voiceGenerator.start()

    audios_paths = voiceGenerator.generate_voice(
        topic=topic, 
        category=category, 
        scenes=script['scenes'], 
        save_folder=output_folder
    )

    if stop and voiceGenerator is not None:
        voiceGenerator.stop()

    return audios_paths



def search_images(script:dict):

    global imageDownloader
    
    topic = script['topic']
    category = script['category']
    print(f"\n[STEP] Searching and downloading images: {category} - {topic}...")

    # Replace or remove characters that are invalid in file paths
    invalid_chars = r'\/:*"<> '
    fixed_cat = ''.join(c if c not in invalid_chars else '_' for c in category.lower()).replace("?", "").replace("'", "")

    # Set up output directory
    function_name = inspect.currentframe().f_code.co_name # Get function name
    output_folder = workflow_path + function_name + f"/{fixed_cat}/"

    # Check if already saved output
    if os.path.exists(output_folder): # If output folder exist, check what is inside
        saved = check_saved_output(
            output_folder, 
            extensions=['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.svg', '.jfif', '.pjpeg', '.pjp', '.ico', '.heic', '.heif']
        )
    else: # If not, create it and execute step
        os.makedirs(output_folder, exist_ok=True)
        saved = []

    
    if imageDownloader is None:
        imageDownloader = ImageDownloader()

    
    # Sub step 1 - Search images ---------------------
    save_path = output_folder + '1 - images_urls.json'
    if save_path not in saved:
        print('[INFO] Searching images...')
        imageDownloader.search_images(script=script, save_path=save_path)    
    
    with open(save_path, "r", encoding="utf-8") as f:
        images_urls = json.load(f)

    print(f'[INFO] Images urls saved sucessfully.')


    # Sub step 2 - Download images ---------------------
    save_folder = output_folder + '2 - download_images/'
    if os.path.exists(save_folder):
        saved_meta = check_saved_output(output_folder, extensions=['.json'])
        if len(saved_meta) == 1:

            # Check if all images are downloaded
            with open(saved_meta[0], "r", encoding="utf-8") as f:
                downloaded_images = json.load(f)

            saved_output_check = True
            for path in downloaded_images.values():
                if not os.path.exists(path):
                    saved_output_check = False
                    break
            
            if saved_output_check:
                print('[INFO] Images were loaded successfully')
                return downloaded_images


    print('[INFO] Downloading images...')

    meta_path = save_folder + 'metadata.json'
    imageDownloader.download_images(images_urls=images_urls, save_folder=save_folder)
    
    with open(meta_path, "r", encoding="utf-8") as f:
        downloaded_images = json.load(f)

    print(f'[INFO] Images were downloaded successfully')
    
    return downloaded_images


def execution():
    print("\n\n\t\t\t *** STARTING THE EXECUTION ***")

    # Step 0: Set up environment
    set_up_environment(0)

    # Step 1: Load topics
    topics = load_topics()

    # Step 2: Research (step is being executed multiple times, one per topic)
    categories_topics = list(topics.items())
    num_topics = len(categories_topics)
    research = [
        research_topics(
            category, 
            topic, 
            stop=(i == num_topics - 1)
        ) 
        for i, (category, topic) in enumerate(categories_topics)
    ]

    # Step 3: Generate video script (step is being executed multiple times, one per research result)
    num_summaries = len(research)
    scripts = [
        generate_script(
            summary, 
            stop=(i == num_summaries - 1)
        ) 
        for i, summary in enumerate(research)
    ]


    # Step 4: Generate voices (step is being executed multiple times, one per script)
    num_scripts = len(scripts)
    voices = [
        generate_voices(
            script, 
            stop=(i == num_scripts - 1)
        ) 
        for i, script in enumerate(scripts)
    ]

    # Step 5: Search for images (step is being executed multiple times, one per script)
    images = [
        search_images(script) 
        for i, script in enumerate(scripts)
    ]
