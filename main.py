import ollama
import os
import json
import datetime
import time
import re
import subprocess

# ----- Debug print helper (truncates to 100 chars) -----
def debug_print(msg):
    """Print a debug message, truncated to 100 characters."""
    if len(msg) > 100:
        msg = msg[:97] + "..."
    print(f"DEBUG: {msg}")

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
    debug_print(f"Enter json_file_dump: file_path={file_path}")
    with open(file_path, "r") as f:
        text = f.read()
    debug_print(f"Read {len(text)} chars from {file_path}")
    data = {
        "filename": os.path.basename(file_path),
        "text": text,
    }
    json_str = json.dumps(data, ensure_ascii=True)
    debug_print(f"Exit json_file_dump: json length {len(json_str)}")
    return json_str

def json_folder_dump(folder_path):
    debug_print(f"Enter json_folder_dump: folder_path={folder_path}")
    data = []
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if os.path.isfile(file_path):
            debug_print(f"Processing file: {filename}")
            file_data = json.loads(json_file_dump(file_path))
            data.append(file_data)
    json_str = json.dumps(data, ensure_ascii=True)
    debug_print(f"Exit json_folder_dump: collected {len(data)} files, json length {len(json_str)}")
    return json_str

def json_memory_dump(folder_path):
    debug_print(f"Enter json_memory_dump: folder_path={folder_path}")
    data = []
    for subfolder in os.listdir(folder_path):
        subfolder_path = os.path.join(folder_path, subfolder)
        if os.path.isdir(subfolder_path):
            debug_print(f"Processing subfolder: {subfolder}")
            files_data = json.loads(json_folder_dump(subfolder_path))
            data.append({
                "subfolder": subfolder,
                "files": files_data
            })
    # life_sectors is defined later, but it's global. We'll access it after it's defined.
    # For now we assume it exists when this function is called.
    # We'll handle sorting after life_sectors is defined.
    sorted_data = sorted(data, key=lambda x: life_sectors.index(x["subfolder"]))
    json_str = json.dumps(sorted_data, ensure_ascii=True)
    debug_print(f"Exit json_memory_dump: {len(data)} subfolders processed, json length {len(json_str)}")
    return json_str

def exec_parse(res):
    debug_print(f"Enter exec_parse: response length {len(res)}")
    pattern = r'\$#START#\$(.*?)\$#END#\$'
    debug_print(f"Regex pattern: {pattern}")
    commands = re.findall(pattern, res)
    debug_print(f"Found {len(commands)} command(s)")

    rets = []    
    for idx, cmd in enumerate([cmd.strip() for cmd in commands]):
        debug_print(f"Executing command {idx+1}: {cmd[:50]}...")
        try:
            os.chdir("/workspace/play/")
            result = subprocess.run(cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            ret = f"Command: {cmd}\nOutput: {result.stdout}"
            debug_print(f"Command {idx+1} succeeded, output length {len(result.stdout)}")
        except Exception as e:
            ret = f"Error executing command: {cmd}\n{e}"
            debug_print(f"Command {idx+1} failed: {str(e)[:50]}")
        rets.append(ret)

    json_rets = json.dumps(rets, ensure_ascii=True)
    debug_print(f"Exit exec_parse: returning JSON of {len(json_rets)} chars")
    return json_rets

prefix = lambda soul, memories, curr=None: f"""The contents of your soul = {soul}.\n The contents of your memories = {memories}.{f"\n The contents of your current session = {curr}." if curr != None else ""}\n Obey your soul & remember your memories. You are greenkrill, you may begin/continue your session. """

def run_session():
    debug_print("Enter run_session")
    begin = datetime.datetime.now()
    end = begin + datetime.timedelta(minutes=1)
    begin_str = begin.strftime("%Y-%m-%d--%H_%M_%S")
    debug_print(f"Session start: {begin_str}, end at {end.strftime('%Y-%m-%d--%H_%M_%S')}")

    check_quarts()
    os.chdir("/workspace/")
    soul = json_folder_dump("soul")
    os.chdir("/workspace/life/")
    memories = json_memory_dump("present")
    curr = None

    iteration = 0
    while datetime.datetime.now() < end:
        iteration += 1
        debug_print(f"--- Iteration {iteration} ---")
        while True:
            try:
                debug_print("Calling runner model...")
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
                debug_print(f"Error during generation: {str(e)[:50]}")
                time.sleep(CONSTANTS["response_error_break_seconds"])
                continue
        res = gen.response
        debug_print(f"Runner response length: {len(res)}")
        out = exec_parse(res)
        if curr is None:
            curr = ""
        curr += f"\n\nChat:{res}\n\nResult:{out}"

        # Truncated debug prints (already using debug_print which truncates)
        debug_print(f"Res: {res[:100]}")
        debug_print(f"Out: {out[:100]}")
        time.sleep(CONSTANTS["cpu_break_seconds"])
    
    # 1 minute has passed
    os.chdir("/workspace/life/present/sessions")
    filename = f"{begin_str}.txt"
    with open(filename, "w") as f:
        f.write(curr)
    debug_print(f"Session saved to {filename} (length {len(curr)} chars)")
    debug_print("Exit run_session")

def check_quarts():
    debug_print("Enter check_quarts")
    os.chdir("/workspace/life/present/sessions")
    sessions = os.listdir()
    debug_print(f"Found {len(sessions)} session(s) in present/sessions")
    if len(sessions) >= 15:
        debug_print("Threshold reached (>=15), moving to quarts")
        oldest = min(sessions, key=lambda x: os.path.getmtime(x)).strip(".txt")
        newest = max(sessions, key=lambda x: os.path.getmtime(x)).strip(".txt")
        debug_print(f"Oldest session base: {oldest}, newest: {newest}")

        summary = summarize(json_folder_dump("."), "session", "quart")
        debug_print(f"Summary length: {len(summary)}")
        summary_filename = f"../quarts/{oldest}___{newest}.txt"
        with open(summary_filename, "w") as f:
            f.write(summary)
        debug_print(f"Quart summary written to {summary_filename}")

        for session in sessions:
            debug_print(f"Moving session {session} to past/sessions/")
            os.rename(session, f"../../past/sessions/{session}")
        debug_print("All sessions moved, now calling check_hours")
        check_hours()
    else:
        debug_print("Threshold not met, exiting check_quarts")
    debug_print("Exit check_quarts")

def check_hours():
    debug_print("Enter check_hours")
    os.chdir("/workspace/life/present/quarts")
    quarts = os.listdir()
    debug_print(f"Found {len(quarts)} quart(s) in present/quarts")
    if len(quarts) >= 4:
        debug_print("Threshold reached (>=4), moving to hours")
        oldest = min(quarts, key=lambda x: os.path.getmtime(x)).strip(".txt").split("___")[0]
        newest = max(quarts, key=lambda x: os.path.getmtime(x)).strip(".txt").split("___")[1]
        debug_print(f"Oldest quart base: {oldest}, newest: {newest}")

        summary = summarize(json_folder_dump("."), "quart", "hour")
        debug_print(f"Summary length: {len(summary)}")
        summary_filename = f"../hours/{newest}___{oldest}.txt"
        with open(summary_filename, "w") as f:
            f.write(summary)
        debug_print(f"Hour summary written to {summary_filename}")

        for quart in quarts:
            debug_print(f"Moving quart {quart} to past/quarts/")
            os.rename(quart, f"../../past/quarts/{quart}")
        debug_print("All quarts moved, now calling check_days")
        check_days()
    else:
        debug_print("Threshold not met, exiting check_hours")
    debug_print("Exit check_hours")

def check_days():
    debug_print("Enter check_days")
    os.chdir("/workspace/life/present/hours")
    hours = os.listdir()
    debug_print(f"Found {len(hours)} hour(s) in present/hours")
    if len(hours) >= 24:
        debug_print("Threshold reached (>=24), moving to days")
        oldest = min(hours, key=lambda x: os.path.getmtime(x)).strip(".txt").split("___")[0]
        newest = max(hours, key=lambda x: os.path.getmtime(x)).strip(".txt").split("___")[1]
        debug_print(f"Oldest hour base: {oldest}, newest: {newest}")

        summary = summarize(json_folder_dump("."), "hour", "day")
        debug_print(f"Summary length: {len(summary)}")
        summary_filename = f"../days/{newest}___{oldest}.txt"
        with open(summary_filename, "w") as f:
            f.write(summary)
        debug_print(f"Day summary written to {summary_filename}")

        for hour in hours:
            debug_print(f"Moving hour {hour} to past/hours/")
            os.rename(hour, f"../../past/hours/{hour}")
        debug_print("All hours moved, now calling check_weeks")
        check_weeks()
    else:
        debug_print("Threshold not met, exiting check_days")
    debug_print("Exit check_days")

def check_weeks():
    debug_print("Enter check_weeks")
    os.chdir("/workspace/life/present/days")
    days = os.listdir()
    debug_print(f"Found {len(days)} day(s) in present/days")
    if len(days) >= 7:
        debug_print("Threshold reached (>=7), moving to weeks")
        oldest = min(days, key=lambda x: os.path.getmtime(x)).strip(".txt").split("___")[0]
        newest = max(days, key=lambda x: os.path.getmtime(x)).strip(".txt").split("___")[1]
        debug_print(f"Oldest day base: {oldest}, newest: {newest}")

        summary = summarize(json_folder_dump("."), "day", "week")
        debug_print(f"Summary length: {len(summary)}")
        summary_filename = f"../weeks/{newest}___{oldest}.txt"
        with open(summary_filename, "w") as f:
            f.write(summary)
        debug_print(f"Week summary written to {summary_filename}")

        for day in days:
            debug_print(f"Moving day {day} to past/days/")
            os.rename(day, f"../../past/days/{day}")
        debug_print("All days moved, now calling check_months")
        check_months()
    else:
        debug_print("Threshold not met, exiting check_weeks")
    debug_print("Exit check_weeks")

def check_months():
    debug_print("Enter check_months")
    os.chdir("/workspace/life/present/weeks")
    weeks = os.listdir()
    debug_print(f"Found {len(weeks)} week(s) in present/weeks")
    if len(weeks) >= 4:
        debug_print("Threshold reached (>=4), moving to months")
        oldest = min(weeks, key=lambda x: os.path.getmtime(x)).strip(".txt").split("___")[0]
        newest = max(weeks, key=lambda x: os.path.getmtime(x)).strip(".txt").split("___")[1]
        debug_print(f"Oldest week base: {oldest}, newest: {newest}")

        summary = summarize(json_folder_dump("."), "week", "month")
        debug_print(f"Summary length: {len(summary)}")
        summary_filename = f"../months/{newest}___{oldest}.txt"
        with open(summary_filename, "w") as f:
            f.write(summary)
        debug_print(f"Month summary written to {summary_filename}")

        for week in weeks:
            debug_print(f"Moving week {week} to past/weeks/")
            os.rename(week, f"../../past/weeks/{week}")
        debug_print("All weeks moved, now calling check_years")
        check_years()
    else:
        debug_print("Threshold not met, exiting check_months")
    debug_print("Exit check_months")

def check_years():
    debug_print("Enter check_years")
    os.chdir("/workspace/life/present/months")
    months = os.listdir()
    debug_print(f"Found {len(months)} month(s) in present/months")
    if len(months) >= 12:
        debug_print("Threshold reached (>=12), moving to years")
        oldest = min(months, key=lambda x: os.path.getmtime(x)).strip(".txt").split("___")[0]
        newest = max(months, key=lambda x: os.path.getmtime(x)).strip(".txt").split("___")[1]
        debug_print(f"Oldest month base: {oldest}, newest: {newest}")

        summary = summarize(json_folder_dump("."), "month", "year")
        debug_print(f"Summary length: {len(summary)}")
        summary_filename = f"../years/{newest}___{oldest}.txt"
        with open(summary_filename, "w") as f:
            f.write(summary)
        debug_print(f"Year summary written to {summary_filename}")

        for month in months:
            debug_print(f"Moving month {month} to past/months/")
            os.rename(month, f"../../past/months/{month}")
        debug_print("All months moved")
    else:
        debug_print("Threshold not met, exiting check_years")
    debug_print("Exit check_years")

def summarize(data, term1, term2):
    debug_print(f"Enter summarize: term1={term1}, term2={term2}, data length {len(data)}")
    prompt = f"Summarize the following {term1}(s) as a(n) {term2} in a concise manner, keeping important details:\n\n{data}"
    debug_print(f"Summarizer prompt length: {len(prompt)}")
    while True:
        try:
            debug_print("Calling summarizer model...")
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
            debug_print(f"Error during summarization: {str(e)[:50]}")
            time.sleep(CONSTANTS["response_error_break_seconds"])
            continue
    debug_print(f"Summarizer response length: {len(gen.response)}")
    debug_print(f"Summary: {gen.response[:100]}")
    debug_print("Exit summarize")
    return gen.response

# ----- Global setup (directory creation and life_sectors) -----
os.chdir("/workspace/")
for folder in ["play", "life", "soul"]:
    os.makedirs(folder, exist_ok=True)
debug_print("Created /workspace/play, life, soul directories")

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
debug_print("Created life/past and life/present subdirectories")

# ----- Main loop -----
if __name__ == "__main__":
    debug_print("Entering main infinite loop")
    loop_count = 0
    while True:
        loop_count += 1
        debug_print(f"Main loop iteration {loop_count}")
        run_session()
        time.sleep(CONSTANTS["cpu_break_seconds"])