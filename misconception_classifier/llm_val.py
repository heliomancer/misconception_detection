import os
import json
import time
import pandas as pd
import openai
from dotenv import load_dotenv

# Load environment variables from a .env file (for local execution)
# GitHub Actions will automatically inject secrets into os.environ
load_dotenv()

# ==========================================
# CONSTANTS AND PARAMETERS
# ==========================================
GROQ_LARGE = ['openai/gpt-oss-120b', 'qwen/qwen3-32b']
GROQ_MEDIUM = ['openai/gpt-oss-20b', 'llama-3.1-8b-instant', 'llama-3.3-70b-versatile']

# Determine absolute paths dynamically based on where the script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
PROMPTS_DIR = os.path.join(BASE_DIR, "prompts")

VAL_DATA_PATH = os.path.join(DATA_DIR, "val_BLvsLLM.csv")
RESULTS_PATH = os.path.join(DATA_DIR, "llm_val.csv")

# ==========================================
# CONFIGURATION TOGGLE
# ==========================================
# Options: "rulebook", "few_shot", "zero_shot"
PROMPT_STRATEGY = "rulebook" 
# ==========================================


# ==========================================
# HELPER FUNCTIONS
# ==========================================
def get_client():
    """Initializes and returns the OpenAI client configured for Groq."""
    api_key = os.environ.get('THESIS_API_KEY')
    if not api_key:
        raise ValueError("API Key not found! Please set THESIS_API_KEY in your .env or GitHub Secrets.")
    
    return openai.OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=api_key,
    )

def load_prompt_template(filename: str) -> str:
    """Loads a text file from the prompts directory."""
    filepath = os.path.join(PROMPTS_DIR, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()

def get_remaining_data(val_path: str, results_path: str) -> pd.DataFrame:
    """Reads the dataset and filters out rows that have already been processed."""
    val_df = pd.read_csv(val_path)
    
    if os.path.exists(results_path):
        results_df = pd.read_csv(results_path)
        processed_indices = set(results_df['index_id'].tolist())
        last_idx = max(processed_indices) if processed_indices else "None"
        print(f"Resuming session. Found {len(processed_indices)} completed rows.")
        print(f"Last processed index was: {last_idx}")
    else:
        processed_indices = set()
        print("Starting fresh evaluation session.")

    # Slice the DataFrame to only contain un-processed rows
    remaining_df = val_df[~val_df.index.isin(processed_indices)]
    print(f"Rows remaining to process: {len(remaining_df)} / {len(val_df)}")
    
    return remaining_df, val_df

def build_payload(strategy: str, problem: str, ans: str, exp: str, classes_str: str) -> list:
    """
    Constructs the exact message payload based on the selected prompt strategy.
    
    Strategies:
      - "rulebook": Loads system.md (hardcoded classes/examples) + user.md (dynamic row data).
      - "few_shot": Loads few_shot.md (injects classes + row data).
      - "zero_shot": Loads zero_shot.md (injects classes + row data).
    """
    
    if strategy == "rulebook":
        # 1. Load the split templates
        sys_msg = load_prompt_template("rulebook/system.md") # No injection needed here!
        usr_tmpl = load_prompt_template("rulebook/user.md")

        # 2. Inject row variables into the user template
        usr_msg = usr_tmpl.replace("[PROBLEM_TEXT]", problem)\
                          .replace("[STUDENT_ANS]", ans)\
                          .replace("[STUDENT_EXP]", exp)

        return [
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": usr_msg}
        ]
        
    elif strategy in ["few_shot", "zero_shot"]:
        # 1. Load the single combined template
        tmpl = load_prompt_template(f"{strategy}.md")
        
        # 2. Inject BOTH the dynamic classes string and the row variables
        msg = tmpl.replace("[VALID_CLASSES]", classes_str)\
                  .replace("[PROBLEM_TEXT]", problem)\
                  .replace("[STUDENT_ANS]", ans)\
                  .replace("[STUDENT_EXP]", exp)
                         
        return [{"role": "user", "content": msg}]
        
    else:
        raise ValueError(f"Unknown PROMPT_STRATEGY: '{strategy}'!")


# ==========================================
# MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    
    # 1. Initialize dependencies
    client = get_client()
    remaining_df, full_df = get_remaining_data(VAL_DATA_PATH, RESULTS_PATH)
    
    # Generate the class string dynamically (if required by your templates)
    valid_classes_str = "\n".join([f"- {c}" for c in full_df['Misconception'].unique()])

    print(f"\nBeginning Groq queries. (USE_SYSTEM_PROMPT = {USE_SYSTEM_PROMPT})")
    print("Press Ctrl+C to manually pause the script.")

    new_rows_this_session =[]
    stop_processing = False

    # 2. Main Processing Loop
    for index, row in remaining_df.iterrows():
        if stop_processing:
            break

        # Extract strings safely
        problem_text = str(row.get('QuestionText', ''))
        student_ans = str(row.get('MC_Answer', ''))
        student_exp = str(row.get('StudentExplanation', ''))

        # Build payload using the helper function
        messages_payload = build_payload(
            strategy=PROMPT_STRATEGY,
            problem=problem_text,
            ans=student_ans,
            exp=student_exp,
            classes_str=valid_classes_str
        )

        current_result = {
            'index_id': index,
            'True_Misconception': row['Misconception']
        }

        # 3. Query Models Loop
        for model_name in GROQ_LARGE:  # Fixed lowercase groq_large to uppercase GROQ_LARGE
            time.sleep(3)  # Space out requests to respect standard API limits
            
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=messages_payload, 
                    response_format={"type": "json_object"},
                    max_tokens=600,   
                    temperature=0.0   
                )
                
                # Extract and parse JSON safely
                output_content = response.choices[0].message.content
                pred = 'Unclassified Error' # Default fallback
                
                if output_content:
                    try:
                        pred = json.loads(output_content).get('prediction', 'Unclassified Error')
                    except json.JSONDecodeError:
                        print(f"[-] {model_name} returned mangled JSON. Defaulting to Unclassified.")
                
                current_result[model_name] = pred

            except openai.RateLimitError:
                print(f"\n[!] 🛑 RATE LIMIT HIT ON {model_name}. Halting session.")
                stop_processing = True
                break 

            except openai.BadRequestError as e:
                if "json_validate_failed" in str(e):
                    print(f"\n[-] {model_name} failed Groq JSON validation. Defaulting to Unclassified.")
                    current_result[model_name] = 'Unclassified Error'
                else:
                    print(f"\n[!] ❌ BAD REQUEST ON {model_name}: {str(e)}")
                    stop_processing = True
                    break

            except Exception as e:
                print(f"\n[!] ❌ UNEXPECTED ERROR ON {model_name}: {str(e)}")
                stop_processing = True
                break

        # 4. Check if we had to abort mid-row
        if stop_processing:
            print("Aborting before saving this incomplete row.")
            break 

        # 5. Row completed successfully! Add to buffer.
        new_rows_this_session.append(current_result)
        print(f"Processed row index {index} successfully across models.")

        # 6. Periodically save to disk (every 5 rows)
        if len(new_rows_this_session) >= 5:
            temp_df = pd.DataFrame(new_rows_this_session)
            # If file exists, append without headers. Otherwise, create new with headers.
            write_mode = 'a' if os.path.exists(RESULTS_PATH) else 'w'
            write_header = not os.path.exists(RESULTS_PATH)
            
            temp_df.to_csv(RESULTS_PATH, mode=write_mode, header=write_header, index=False)
            new_rows_this_session = []


