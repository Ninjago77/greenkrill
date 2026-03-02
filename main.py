import ollama
import os
import json
import datetime
import time
import re
import subprocess

CONSTANTS = {
    "cpu_break_seconds": .5,
    "response_error_break_seconds": 5,
}

OLLAMA_MODEL_HOSTS = {
    "runner":{
        # "ollama_host": "http://192.168.1.2:11436",
        # "ollama_model_name": "qwen3:4b",
        "ollama_host": "http://192.168.1.2:11435",
        "ollama_model_name": "llama3.2:1b",
        "options_temperature": 1.8,
        "options_top_p": 0.9,
    },
    "summarizer":{
        "ollama_host": "http://192.168.1.2:11435",
        "ollama_model_name": "llama3.2:1b",
        "options_temperature": 0.3,
        # "options_top_p": 0.9, Uncomment in `def summarizer()` too
    }
}

for model_name, model_info in OLLAMA_MODEL_HOSTS.items():
    ollama_host = model_info["ollama_host"]
    OLLAMA_MODEL_HOSTS[model_name]["ollama_client"] = ollama.Client(host=ollama_host)

def json_file_dump(file_path):
    with open(file_path, "r") as f:
        text = f.read()
    data = {
        "filename": os.path.basename(file_path),
        "text": text,
    }
    return json.dumps(data, ensure_ascii=True)

def json_folder_dump(folder_path):
    data = []
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if os.path.isfile(file_path):
            data.append(json.loads(json_file_dump(file_path)))
    return json.dumps(data, ensure_ascii=True)

def json_memory_dump(folder_path):
    data = []
    for subfolder in os.listdir(folder_path):
        subfolder_path = os.path.join(folder_path, subfolder)
        if os.path.isdir(subfolder_path):
            data.append({
                "subfolder": subfolder,
                "files": json.loads(json_folder_dump(subfolder_path))
            })
    return json.dumps(sorted(data, key=lambda x: life_sectors.index(x["subfolder"])), ensure_ascii=True)

os.chdir("/workspace/")
for folder in ["play", "life", "soul"]:
    os.makedirs(folder, exist_ok=True)

life_sectors = [
    "years",
    "months",
    "weeks",
    "days",
    "hours",
    "quarts",
    "sessions",
]

os.chdir("/workspace/life")
for folder in ["past", "present"]:
    os.makedirs(folder, exist_ok=True)
    for sector in life_sectors:
        os.makedirs(os.path.join(folder, sector), exist_ok=True)

def exec_parse(res):
    # Regex breakdown:
    # \$#START#\$ : Matches the literal start tag (escaping the '$')
    # (.*?)       : Captures everything in between (non-greedy)
    # \$#END#\$   : Matches the literal end tag
    pattern = r'\$#START#\$(.*?)\$#END#\$'
    
    # findall returns all matches in order as a list
    commands = re.findall(pattern, res)

    rets = []    
    # Optional: Strip whitespace from the results
    for cmd in [cmd.strip() for cmd in commands]:
        try:
            # Execute the command and capture output
            os.chdir("/workspace/play/")
            result = subprocess.run(cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            ret = f"Command: {cmd}\nOutput: {result.stdout}"
        except Exception as e:
            ret = f"Error executing command: {cmd}\n{e}"
        rets.append(ret)

    return json.dumps(rets, ensure_ascii=True)
        

prefix = lambda soul, memories, curr=None: f"""The contents of your soul = {soul}.\n The contents of your memories = {memories}.{f"\n The contents of your current session = {curr}." if curr != None else ""}\n Obey your soul & remember your memories. You are greenkrill, you may begin/continue your session. """

def run_session():
    begin = datetime.datetime.now()
    end = begin + datetime.timedelta(minutes=1)
    begin_str = begin.strftime("%Y-%m-%d--%H_%M_%S")
    
    check_quarts()
    os.chdir("/workspace/")
    soul = json_folder_dump("soul")
    os.chdir("/workspace/life/")
    memories = json_memory_dump("present")
    curr = None

    while datetime.datetime.now() < end:
        while True:
            try:
                gen = OLLAMA_MODEL_HOSTS["runner"]["ollama_client"].generate(
                    model=OLLAMA_MODEL_HOSTS["runner"]["ollama_model_name"],
                    prompt=prefix(soul, memories, curr),
                    options={
                        "temperature": OLLAMA_MODEL_HOSTS["runner"]["options_temperature"],
                        "top_p": OLLAMA_MODEL_HOSTS["runner"]["options_top_p"],
                    }
                )
                break
            except Exception as e:
                print(f"Error during generation: {e}")
                time.sleep(CONSTANTS["response_error_break_seconds"])
                continue
        res = gen.response
        out = exec_parse(res)
        if curr == None: curr = ""
        curr += f"\n\nChat:{res}\n\nResult:{out}"

        print(f"Res: {res[:100]}")
        print(f"Out: {out[:100]}")
        time.sleep(CONSTANTS["cpu_break_seconds"])
    
    #1 minute has passed
    os.chdir("/workspace/life/present/sessions")
    with open(f"{begin_str}.txt", "w") as f:
        f.write(curr)
    

def check_quarts():
    os.chdir("/workspace/life/present/sessions")
    sessions = os.listdir()
    if len(sessions) >= 15:
        oldest = min(sessions, key=lambda x: os.path.getmtime(x)).strip(".txt")
        newest = max(sessions, key=lambda x: os.path.getmtime(x)).strip(".txt")

        summary = summarize(json_folder_dump("."), "session", "quart")
        with open(f"../quarts/{oldest}___{newest}.txt", "w") as f:
            f.write(summary)

        for session in sessions:
            os.rename(session, f"../../past/sessions/{session}")

        check_hours()


def check_hours():
    os.chdir("/workspace/life/present/quarts")
    quarts = os.listdir()
    if len(quarts) >= 4:
        oldest = min(quarts, key=lambda x: os.path.getmtime(x)).strip(".txt").split("___")[0]
        newest = max(quarts, key=lambda x: os.path.getmtime(x)).strip(".txt").split("___")[1]

        summary = summarize(json_folder_dump("."), "quart", "hour")
        with open(f"../hours/{newest}___{oldest}.txt", "w") as f:
            f.write(summary)
        
        for quart in quarts:
            os.rename(quart, f"../../past/quarts/{quart}")

        check_days()

def check_days():
    os.chdir("/workspace/life/present/hours")
    hours = os.listdir()
    if len(hours) >= 24:
        oldest = min(hours, key=lambda x: os.path.getmtime(x)).strip(".txt").split("___")[0]
        newest = max(hours, key=lambda x: os.path.getmtime(x)).strip(".txt").split("___")[1]

        summary = summarize(json_folder_dump("."), "hour", "day")
        with open(f"../days/{newest}___{oldest}.txt", "w") as f:
            f.write(summary)

        for hour in hours:
            os.rename(hour, f"../../past/hours/{hour}")
        
        check_weeks()



def check_weeks():
    os.chdir("/workspace/life/present/days")
    days = os.listdir()
    if len(days) >= 7:
        oldest = min(days, key=lambda x: os.path.getmtime(x)).strip(".txt").split("___")[0]
        newest = max(days, key=lambda x: os.path.getmtime(x)).strip(".txt").split("___")[1]

        summary = summarize(json_folder_dump("."), "day", "week")
        with open(f"../weeks/{newest}___{oldest}.txt", "w") as f:
            f.write(summary)

        for day in days:
            os.rename(day, f"../../past/days/{day}")

        check_months()

def check_months():
    os.chdir("/workspace/life/present/weeks")
    weeks = os.listdir()
    if len(weeks) >= 4:
        oldest = min(weeks, key=lambda x: os.path.getmtime(x)).strip(".txt").split("___")[0]
        newest = max(weeks, key=lambda x: os.path.getmtime(x)).strip(".txt").split("___")[1]

        summary = summarize(json_folder_dump("."), "week", "month")
        with open(f"../months/{newest}___{oldest}.txt", "w") as f:
            f.write(summary)
        
        for week in weeks:
            os.rename(week, f"../../past/weeks/{week}")

        check_years()

def check_years():
    os.chdir("/workspace/life/present/months")
    months = os.listdir()
    if len(months) >= 12:
        oldest = min(months, key=lambda x: os.path.getmtime(x)).strip(".txt").split("___")[0]
        newest = max(months, key=lambda x: os.path.getmtime(x)).strip(".txt").split("___")[1]

        summary = summarize(json_folder_dump("."), "month", "year")
        with open(f"../years/{newest}___{oldest}.txt", "w") as f:
            f.write(summary)

        for month in months:
            os.rename(month, f"../../past/months/{month}")


def summarize(data, term1, term2):
    prompt = f"Summarize the following {term1}(s) as a(n) {term2} in a concise manner, keeping important details:\n\n{data}"
    while True:
        try:
            gen = OLLAMA_MODEL_HOSTS["summarizer"]["ollama_client"].generate(
                model=OLLAMA_MODEL_HOSTS["summarizer"]["ollama_model_name"],
                prompt=prompt,
                options={
                    "temperature": OLLAMA_MODEL_HOSTS["summarizer"]["options_temperature"],
                    # "top_p": OLLAMA_MODEL_HOSTS["summarizer"]["options_top_p"],
                }
            )
            break
        except Exception as e:
            print(f"Error during summarization: {e}")
            time.sleep(CONSTANTS["response_error_break_seconds"])
            continue
    print (f"Summary: {gen.response[:100]}")
    return gen.response

if __name__ == "__main__":
    while True:
        run_session()
        time.sleep(CONSTANTS["cpu_break_seconds"])