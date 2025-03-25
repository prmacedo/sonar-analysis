import csv
import os
import requests
import time
import subprocess

from datetime import datetime
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth
from slugify import slugify

load_dotenv(dotenv_path='.env')
load_dotenv(dotenv_path='app/.env')

SONAR_HOST_URL=os.getenv('SONAR_HOST_URL')
SONAR_USERNAME=os.getenv('SONAR_USERNAME')
SONAR_PASSWORD=os.getenv('SONAR_PASSWORD')
OUTPUT_PATH=os.getenv('OUTPUT_PATH')
PARTICIPANT=os.getenv('PARTICIPANT')
PROJECT_PATH=os.getenv('PROJECT_PATH')
PROJECT_KEY=PROJECT_PATH.replace('\\','/').split('/')[-1]

METRICS = ['new_technical_debt','analysis_from_sonarqube_9_4','blocker_violations','bugs','classes','code_smells','cognitive_complexity','comment_lines','comment_lines_density','comment_lines_data','class_complexity','file_complexity','function_complexity','complexity_in_classes','complexity_in_functions','branch_coverage','new_branch_coverage','conditions_to_cover','new_conditions_to_cover','confirmed_issues','coverage','new_coverage','critical_violations','complexity','last_commit_date','development_cost','new_development_cost','directories','duplicated_blocks','new_duplicated_blocks','duplicated_files','duplicated_lines','duplicated_lines_density','new_duplicated_lines_density','new_duplicated_lines','duplications_data','effort_to_reach_maintainability_rating_a','executable_lines_data','false_positive_issues','file_complexity_distribution','files','function_complexity_distribution','functions','generated_lines','generated_ncloc','info_violations','violations','line_coverage','new_line_coverage','lines','ncloc','ncloc_language_distribution','lines_to_cover','new_lines_to_cover','sqale_rating','new_maintainability_rating','major_violations','minor_violations','ncloc_data','new_blocker_violations','new_bugs','new_code_smells','new_critical_violations','new_info_violations','new_violations','new_lines','new_major_violations','new_minor_violations','new_security_hotspots','new_vulnerabilities','unanalyzed_c','unanalyzed_cpp','open_issues','quality_profiles','projects','public_api','public_documented_api_density','public_undocumented_api','quality_gate_details','alert_status','reliability_rating','new_reliability_rating','reliability_remediation_effort','new_reliability_remediation_effort','reopened_issues','security_hotspots','security_hotspots_reviewed','new_security_hotspots_reviewed','security_rating','new_security_rating','security_remediation_effort','new_security_remediation_effort','security_review_rating','new_security_review_rating','security_hotspots_reviewed_status','new_security_hotspots_reviewed_status','security_hotspots_to_review_status','new_security_hotspots_to_review_status','skipped_tests','statements',]

def run_command(command):
  result = subprocess.run(command, shell=True, capture_output=True, text=True)
  return result.stdout, result.stderr

def start_docker():
  print("Starting Docker containers...")
  run_command("docker-compose up -d")

def stop_docker():
  print("Removing Docker containers...")
  run_command("docker-compose down")

def wait_for_sonarqube():
  print("Waiting for SonarQube to become available...")
  while True:
    try:
      response = requests.get(f"{SONAR_HOST_URL}/api/system/status")
      
      json_response = response.json()
      status = json_response.get("status")

      print(f"Waiting for SonarQube to become available... (status: {status})")
      if response.status_code == 200 and response.json().get("status") == "UP":
        print("SonarQube is ready!")
        break
    except requests.exceptions.RequestException:
      pass
    time.sleep(10)

def generate_token():
  print("Generating access token...")
  response = requests.post(
    f"{SONAR_HOST_URL}/api/user_tokens/generate",
    auth=(SONAR_USERNAME, SONAR_PASSWORD),
    data={"name": "my_token"}
  )
  if response.status_code == 200:
    return response.json()["token"]
  else:
    print("Error generating token:", response.text)
    exit(1)

def run_sonar_scanner(token):
  print("Running Sonar Scanner...")
  os.environ["SONAR_TOKEN"] = token
  command = f"docker-compose run --rm -v {PROJECT_PATH}:/usr/src/{PROJECT_KEY} sonar-scanner-cli \
    -Dsonar.projectKey={PROJECT_KEY} \
    -Dsonar.projectName={PROJECT_KEY} \
    -Dsonar.sources={PROJECT_KEY} \
    -Dsonar.host.url={SONAR_HOST_URL} \
    -Dsonar.login={token}"
    #  > sonar_analysis.log 2>&1
  run_command(command)

def collect_metrics(token):
  print("Collecting metrics...")

  url = f"{SONAR_HOST_URL}/api/measures/component"
  params = params={"component": PROJECT_KEY, "metricKeys": ",".join(METRICS)}
  auth=HTTPBasicAuth(SONAR_USERNAME, SONAR_PASSWORD)
  # headers={"Authorization": f"Bearer {token}"}

  response = requests.get(url, params=params, auth=auth)

  if response.status_code == 200:
    return response.json()["component"]["measures"]
  else:
    print(f"({response.status_code}) Error collecting metrics: {response.text}")
    exit(1)

def save_to_csv(metrics):
  print("Saving metrics to CSV...")
  
  now = datetime.now()
  date = now.strftime("%Y-%m-%d")
  ts = int(datetime.timestamp(now))
  slug = slugify(PARTICIPANT)

  filename = f"{slug}-{ts}.csv"
  directory = os.path.join(OUTPUT_PATH, 'sonar_analysis_output', date)
  filepath = os.path.join(directory, filename)

  if not os.path.exists(directory):
    os.makedirs(directory)

  with open(filepath, "w", newline="") as file:
    writer = csv.writer(file)
    writer.writerow(["Metric", "Value", "Datetime", "Participant"])
    for metric in metrics:
      writer.writerow([metric["metric"], metric["value"], now, PARTICIPANT])

def main():
  try:
    start_docker()
    wait_for_sonarqube()
    token = generate_token()
    run_sonar_scanner(token)
    metrics = collect_metrics(token)
    save_to_csv(metrics)
  finally:
    stop_docker()

if __name__ == '__main__':
  main()