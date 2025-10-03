import os
import json
import inspect

from projects.classes.TopicManagerOR import TopicManagerOR
from projects.classes.ResearcherLMS import ResearcherLMS

# GLOBALS ---------------------------------------------------------------------------------------
project_name = 'LoreLabs'
workflow_name = 'workflow1'
base_path = f'volume/output/{project_name}/{workflow_name}/'

execution_id = None
workflow_path = None


# UTILS -----------------------------------------------------------------------------------------
def int2id(id: int, digits:int = 4) -> str:
    id_str = str(id)
    if len(id_str) > digits:
        raise ValueError(f"id '{id}' has more than {digits} digits")
    return id_str.zfill(digits)

def check_saved_output(folder_path: str, extensions: None | list[str] = None) -> list[str]:

    files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]

    if extensions is not None:
        files = [f for f in files if any(f.endswith(ext) for ext in extensions)]

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
        with open(output_folder + saved, "r", encoding="utf-8") as f:
            topics_json = json.load(f)

        # Print loaded
        print("[INFO] Loaded topics:")
        for k, v in topics_json.items(): print(f"[INFO] {k} -> {v}")

        return topics_json



def execution():
    print("\n\n\t\t\t *** STARTING THE EXECUTION ***")

    # Set up environment
    set_up_environment(0)
    topics = load_topics()

