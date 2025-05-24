from pathlib import Path

ENV_KEYS = ["PROJECT_PATH", "OUTPUT_PATH", "PARTICIPANT"]

def read_env_file(file_path=".env"):
  env = {}
  if not Path(file_path).exists():
    return env
  with open(file_path, "r", encoding="utf-8") as f:
    for line in f:
      if line.strip() and not line.startswith("#") and "=" in line:
        key, value = line.strip().split("=", 1)
        env[key] = value
  return env

def prompt_env_variable(var_name, current_value=None):
  if current_value:
    prompt = f"{var_name} [current: {current_value}] (press Enter to keep): "
  else:
    prompt = f"{var_name}: "

  value = input(prompt).strip()

  if not value:
    if current_value:
      value = current_value
    else:
      raise ValueError(f"{var_name} is required and cannot be empty.")

  if var_name in ("PROJECT_PATH", "OUTPUT_PATH"):
    path = Path(value).expanduser().resolve()
    if not path.is_dir():
      raise FileNotFoundError(f"{var_name} must be an existing folder. '{path}' does not exist.")
    value = str(path)

  return value

def setup_env():
  current_env = read_env_file()
  updated = False

  for key in ENV_KEYS:
    current_value = current_env.get(key)

    try:
      new_value = prompt_env_variable(key, current_value)
      current_env[key] = new_value
      updated = True

    except Exception as e:
      print(f"Error: {e}")
      raise

  if updated:
    with open(".env", "w", encoding="utf-8") as f:
      for key in ENV_KEYS:
        value = current_env.get(key, "")
        f.write(f"{key}={value}\n")
    print(".env file updated successfully.")

if __name__ == '__main__':
  setup_env()
