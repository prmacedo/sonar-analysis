import os
import requests
import subprocess
import time

# from dotenv import load_dotenv

# load_dotenv(dotenv_path='.env')
# load_dotenv(dotenv_path='app/.env')

SONAR_SOURCES=os.getenv('SONAR_SOURCES')
OUTPUT_PATH=os.getenv('OUTPUT_PATH')
SONAR_USERNAME=os.getenv('SONAR_USERNAME')
SONAR_PASSWORD=os.getenv('SONAR_PASSWORD')
SONAR_HOST_URL=os.getenv('SONAR_HOST_URL')
PROJECT_KEY=os.getenv('PROJECT_KEY')

def run_command(command):
  result = subprocess.run(command, shell=True, capture_output=True, text=True)
  return result.stdout, result.stderr

def start_docker():
  print('Iniciando os containers Docker...')
  run_command("docker compose up -d")

def stop_docker():
  print("Removendo containers Docker...")
  run_command("docker-compose down")

def wait_for_sonarqube():
  print("Aguardando o SonarQube ficar disponível...")
  while True:
    try:
      response = requests.get(f"{SONAR_HOST_URL}/api/system/status")
      if response.status_code == 200 and response.json().get("status") == "UP":
        print("SonarQube está pronto!")
        break
    except requests.exceptions.RequestException:
      pass
    time.sleep(5)

def generate_token():
  print("Gerando token de acesso...")
  response = requests.post(
    f"{SONAR_HOST_URL}/api/user_tokens/generate",
    auth=(SONAR_USERNAME, SONAR_PASSWORD),
    data={"name": "my_token"}
  )
  if response.status_code == 200:
    return response.json()["token"]
  else:
    print("Erro ao gerar token:", response.text)
    exit(1)

def run_sonar_scanner(token):
  print("Executando Sonar Scanner...")
  os.environ["SONAR_TOKEN"] = token
  command = f"docker compose run --rm -v {SONAR_SOURCES}:/usr/src/{PROJECT_KEY} sonar-scanner-cli \
    -Dsonar.projectKey={PROJECT_KEY} \
    -Dsonar.projectName={PROJECT_KEY} \
    -Dsonar.sources={PROJECT_KEY} \
    -Dsonar.host.url={SONAR_HOST_URL} \
    -Dsonar.login={token} \
    -Dsonar.exclusions=**/*.java \
    > sonar_analysis.log 2>&1"
  run_command(command)

def collect_metrics(token):
  print("Coletando métricas...")
  metric_keys = ['bugs', 'new_bugs', 'vulnerabilities', 'new_vulnerabilities', 'code_smells', 'new_code_smells', 'high_impact_accepted_issues', 'new_blocker_violations', 'new_critical_violations', 'new_major_violations', 'new_minor_violations', 'new_info_violations', 'blocker_violations', 'critical_violations', 'major_violations', 'minor_violations', 'info_violations', 'security_hotspots', 'complexity', 'cognitive_complexity', 'coverage', 'line_coverage', 'branch_coverage', 'ncloc', 'lines','files', 'functions', 'statements', 'comment_lines','comment_lines_density', 'software_quality_blocker_issues', 'software_quality_high_issues', 'software_quality_info_issues', 'software_quality_medium_issues', 'software_quality_low_issues', 'software_quality_maintainability_issues', 'software_quality_reliability_issues', 'software_quality_security_issues', 'new_software_quality_blocker_issues', 'new_software_quality_high_issues', 'new_software_quality_info_issues', 'new_software_quality_medium_issues', 'new_software_quality_low_issues', 'new_software_quality_maintainability_issues', 'new_software_quality_reliability_issues', 'new_software_quality_security_issues']

  METRICS=','.join(metric_keys)
  
  response = requests.get(
    f"{SONAR_HOST_URL}/api/measures/component", 
    params={"component": PROJECT_KEY, "metricKeys": METRICS},
    headers={"Authorization": f"Bearer {token}"}
  )
  if response.status_code == 200:
    return response.json()["component"]["measures"]
  else:
    print("Erro ao coletar métricas:", response.text)
    exit(1)

def main():
  try:
    start_docker()
    wait_for_sonarqube()
    token = generate_token()
    run_sonar_scanner(token)
    metrics = collect_metrics(token)
    print(metrics)
  finally:
    stop_docker()

if __name__ == "__main__":
    main()