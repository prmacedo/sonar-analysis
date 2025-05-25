import csv
import os
import requests
import time
import subprocess
import re # Importar re para regex

from datetime import datetime
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth
from slugify import slugify

class SonarQubeAnalyzer:
  def __init__(self):
    self.load_enviroment()
    self.project_key = self.get_project_key(self.project_path)
    self.metrics = ['new_technical_debt','analysis_from_sonarqube_9_4','blocker_violations','bugs','classes','code_smells','cognitive_complexity','comment_lines','comment_lines_density','comment_lines_data','class_complexity','file_complexity','function_complexity','complexity_in_classes','complexity_in_functions','branch_coverage','new_branch_coverage','conditions_to_cover','new_conditions_to_cover','confirmed_issues','coverage','new_coverage','critical_violations','complexity','last_commit_date','development_cost','new_development_cost','directories','duplicated_blocks','new_duplicated_blocks','duplicated_files','duplicated_lines','duplicated_lines_density','new_duplicated_lines_density','new_duplicated_lines','duplications_data','effort_to_reach_maintainability_rating_a','executable_lines_data','false_positive_issues','file_complexity_distribution','files','function_complexity_distribution','functions','generated_lines','generated_ncloc','info_violations','violations','line_coverage','new_line_coverage','lines','ncloc','ncloc_language_distribution','lines_to_cover','new_lines_to_cover','sqale_rating','new_maintainability_rating','major_violations','minor_violations','ncloc_data','new_blocker_violations','new_bugs','new_code_smells','new_critical_violations','new_info_violations','new_violations','new_lines','new_major_violations','new_minor_violations','new_security_hotspots','new_vulnerabilities','unanalyzed_c','unanalyzed_cpp','open_issues','quality_profiles','projects','public_api','public_documented_api_density','public_undocumented_api','quality_gate_details','alert_status','reliability_rating','new_reliability_rating','reliability_remediation_effort','new_reliability_remediation_effort','reopened_issues','security_hotspots','security_hotspots_reviewed','new_security_hotspots_reviewed','security_rating','new_security_rating','security_remediation_effort','new_security_remediation_effort','security_review_rating','new_security_review_rating','security_hotspots_reviewed_status','new_security_hotspots_reviewed_status','security_hotspots_to_review_status','new_security_hotspots_to_review_status','skipped_tests','statements']

  def load_enviroment(self):
    load_dotenv(dotenv_path='.env')
    load_dotenv(dotenv_path='app/.env') # app/.env terá precedência se as vars estiverem em ambos

    # URL para comunicação host-para-container (chamadas de API do script)
    self.sonar_external_host_url = os.getenv('SONAR_EXTERNAL_HOST_URL', 'http://localhost:9000')
    # URL para comunicação container-para-container (scanner para sonarqube)
    self.sonar_internal_host_url = os.getenv('SONAR_INTERNAL_HOST_URL', 'http://sonarqube:9000') #

    self.sonar_username = os.getenv('SONAR_USERNAME')
    self.sonar_password = os.getenv('SONAR_PASSWORD')
    self.output_path = os.getenv('OUTPUT_PATH')
    self.participant = os.getenv('PARTICIPANT')
    self.project_path = os.getenv('PROJECT_PATH')

  def get_project_key(self, project_path):
    if not project_path: # Adicionar verificação para project_path nulo ou vazio
        raise ValueError("PROJECT_PATH não está definido ou está vazio na configuração de ambiente.")
    cleaned_path = project_path.rstrip("\\/")
    return cleaned_path.replace('\\','/').split('/')[-1]

  def run_command(self, command):
    result = subprocess.run(command, shell=True, capture_output=True, text=True, encoding='utf-8') # Adicionar encoding
    return result.stdout, result.stderr

  def start_docker(self):
    print("Iniciando contêineres Docker...")
    stdout, stderr = self.run_command("docker compose up -d")
    print("Docker start STDOUT:", stdout)
    if stderr:
      print("Docker start STDERR:", stderr)

  def stop_docker(self):
    print("Removendo contêineres Docker...")
    stdout, stderr = self.run_command("docker compose down")
    print("Docker stop STDOUT:", stdout)
    if stderr:
      print("Docker stop STDERR:", stderr)

  def wait_for_sonarqube(self):
    print(f"Aguardando SonarQube ficar disponível em {self.sonar_external_host_url}...")
    while True:
      try:
        response = requests.get(f"{self.sonar_external_host_url}/api/system/status")
        json_response = response.json()
        status = json_response.get("status")
        print(f"Aguardando SonarQube... (status: {status})")
        if response.status_code == 200 and status == "UP":
          print("SonarQube está pronto!")
          break
      except requests.exceptions.RequestException as e:
        print(f"Ocorreu um erro ao contatar o SonarQube: {e}")
      print("Tentando novamente em 10 segundos...")
      time.sleep(10)

  def generate_token(self):
    print("Gerando token de acesso...")
    try:
      response = requests.post(
        f"{self.sonar_external_host_url}/api/user_tokens/generate",
        auth=(self.sonar_username, self.sonar_password),
        data={"name": "my_token_python_script"} # Nome do token um pouco mais descritivo
      )
      response.raise_for_status() # Levanta exceção para códigos de erro HTTP
      return response.json()["token"]
    except requests.exceptions.RequestException as e:
      print(f"Erro ao gerar token: {e}")
      if e.response is not None:
          print(f"Detalhes do erro: {e.response.text}")
      exit(1)

  def run_sonar_scanner(self, token):
    print("Executando Sonar Scanner...")

    # Garante que project_path é um caminho absoluto para montagem de volume Docker
    absolute_project_path = os.path.abspath(self.project_path)
    if not os.path.exists(absolute_project_path):
        raise FileNotFoundError(f"PROJECT_PATH {absolute_project_path} não existe.")
    if not os.path.isdir(absolute_project_path):
        raise NotADirectoryError(f"PROJECT_PATH {absolute_project_path} não é um diretório.")

    # O workdir dentro do container será /usr/src/{self.project_key}
    # sonar.sources=. significa que as fontes estão no diretório de trabalho atual do scanner
    command = (
        f"docker compose run --rm "
        f"-e SONAR_TOKEN={token} " # Passar token como var de ambiente, embora sonar.login seja o principal
        f"--workdir /usr/src/{self.project_key} " # Define o diretório de trabalho dentro do container
        f"-v \"{absolute_project_path}:/usr/src/{self.project_key}\" " # Monta o projeto
        f"sonar-scanner-cli " # Nome do serviço do scanner no docker-compose.yml
        f"-Dsonar.projectKey={self.project_key} "
        f"-Dsonar.projectName={self.project_key} "
        f"-Dsonar.sources=. " # Analisa o diretório de trabalho atual
        f"-Dsonar.host.url={self.sonar_internal_host_url} " # URL interna para comunicação container-container
        f"-Dsonar.login={token} "
        f"-Dsonar.verbose=true " # Habilita logs detalhados do scanner
        f"-Dsonar.scm.disabled=true " # Desabilita SCM para evitar erros se .git não estiver presente ou configurado
    )
    print(f"Executando comando do scanner: {command}")
    stdout, stderr = self.run_command(command)
    return stdout, stderr

  def get_task_id_from_scanner_log(self, log_output):
    # Exemplo de log: INFO: More information about the report processing at http://sonarqube:9000/api/ce/task?id=AY শ্রদ্ধେୟ-RANDOM_ID
    match = re.search(r"ce/task\?id=([^\s]+)", log_output)
    if match:
      task_id = match.group(1)
      print(f"ID da tarefa do Compute Engine encontrado: {task_id}")
      return task_id
    print("ID da tarefa do Compute Engine não encontrado no log do scanner.")
    return None

  def wait_for_analysis_completion(self, task_id):
    if not task_id:
      print("Nenhum ID de tarefa do Compute Engine. A análise pode não ter sido enviada ou o log não continha o ID.")
      print("Aguardando 30 segundos como fallback antes de coletar métricas...")
      time.sleep(30)
      return

    print(f"Aguardando a tarefa de análise {task_id} do SonarQube ser concluída...")
    max_retries = 30 # Aproximadamente 5 minutos (30 * 10s)
    retries = 0
    while retries < max_retries:
      try:
        response = requests.get(
          f"{self.sonar_external_host_url}/api/ce/task",
          params={"id": task_id},
          auth=HTTPBasicAuth(self.sonar_username, self.sonar_password)
        )
        response.raise_for_status()
        task_info = response.json().get("task")

        if task_info:
          status = task_info.get("status")
          print(f"Status da tarefa de análise {task_id}: {status}")
          if status == "SUCCESS":
            print("Tarefa de análise concluída com sucesso.")
            # Verificação adicional se o projeto existe após o SUCESSO da tarefa
            project_check_url = f"{self.sonar_external_host_url}/api/projects/lookup"
            project_params = {"project": self.project_key}
            project_response = requests.get(project_check_url, params=project_params, auth=HTTPBasicAuth(self.sonar_username, self.sonar_password))
            if project_response.status_code == 200:
                print(f"Projeto {self.project_key} encontrado no SonarQube após a análise.")
                return # Sucesso
            else:
                print(f"Projeto {self.project_key} ainda não encontrado (status: {project_response.status_code}) após o sucesso da tarefa. Verifique o SonarQube.")
                # Mesmo que a tarefa CE seja bem-sucedida, pode haver um atraso ou problema na visibilidade do projeto.
                # Neste ponto, podemos decidir sair ou tentar coletar métricas de qualquer maneira.
                # Para este exemplo, vamos prosseguir, mas um tratamento de erro mais robusto pode ser necessário.
                return

          elif status in ["FAILED", "CANCELED"]:
            error_message = task_info.get("errorMessage", "Nenhuma mensagem de erro detalhada.")
            print(f"Tarefa de análise {task_id} FALHOU ou foi CANCELADA. Status: {status}. Erro: {error_message}")
            exit(f"Tarefa {task_id} do Compute Engine do SonarQube falhou. Não é possível coletar métricas.")
        else:
          print(f"Não foi possível obter informações da tarefa para {task_id}. Resposta: {response.text}")

      except requests.exceptions.RequestException as e:
        print(f"Erro ao verificar o status da tarefa de análise: {e}")
      except ValueError as e: # Lida com erros de decodificação JSON
        print(f"Erro ao decodificar resposta JSON para status da tarefa: {e}")

      retries += 1
      if retries < max_retries:
          print("Tentando novamente em 10 segundos...")
          time.sleep(10)
      else:
          print(f"Tempo máximo de espera atingido para a tarefa {task_id}. O projeto pode não estar pronto.")
          exit(f"A tarefa de análise {task_id} não foi concluída com SUCESSO a tempo.")


  def collect_metrics(self, token): # Token não é usado aqui, mas mantido por consistência se mudar a autenticação
    print("Coletando métricas...")
    url = f"{self.sonar_external_host_url}/api/measures/component"
    params = {"component": self.project_key, "metricKeys": ",".join(self.metrics)}
    auth = HTTPBasicAuth(self.sonar_username, self.sonar_password)

    try:
      response = requests.get(url, params=params, auth=auth)
      response.raise_for_status() # Levanta exceção para códigos de erro HTTP
      return response.json()["component"]["measures"]
    except requests.exceptions.RequestException as e:
      print(f"({e.response.status_code if e.response else 'N/A'}) Erro ao coletar métricas: {e.response.text if e.response else e}")
      exit(1)
    except KeyError:
      print(f"Erro ao processar a resposta JSON da coleta de métricas. 'component' ou 'measures' não encontrado. Resposta: {response.text}")
      exit(1)


  def save_to_csv(self, metrics):
    print("Salvando métricas em CSV...")
    if not metrics: # Adicionar verificação se metrics está vazio
        print("Nenhuma métrica foi coletada. O arquivo CSV não será gerado.")
        return

    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d") # Renomeado para date_str para evitar conflito com 'date'
    ts = int(datetime.timestamp(now))
    slug = slugify(self.participant)

    filename = f"{slug}-{ts}.csv"
    directory = os.path.join(self.output_path, 'sonar_analysis_output', date_str)
    filepath = os.path.join(directory, filename)

    if not os.path.exists(directory):
      os.makedirs(directory)

    with open(filepath, "w", newline="", encoding='utf-8') as file: # Adicionar encoding
      writer = csv.writer(file)
      writer.writerow(["Metric", "Value", "Datetime", "Participant"])
      for metric in metrics:
        writer.writerow([metric["metric"], metric.get("value", "N/A"), now, self.participant]) # Usar .get para "value"
    print(f"Métricas salvas em: {filepath}")

  def execute(self):
    if not self.output_path:
      raise ValueError("OUTPUT_PATH não está definido ou está vazio")
    if not self.participant:
      raise ValueError("PARTICIPANT não está definido ou está vazio")
    if not self.project_path:
      raise ValueError("PROJECT_PATH não está definido ou está vazio")

    try:
      self.start_docker()
      self.wait_for_sonarqube()
      token = self.generate_token()

      scanner_stdout, scanner_stderr = self.run_sonar_scanner(token)
      print("\n--- Saída do Sonar Scanner (STDOUT) ---")
      print(scanner_stdout)
      print("--- Fim do STDOUT do Sonar Scanner ---\n")

      if scanner_stderr:
        print("\n--- Saída de Erro do Sonar Scanner (STDERR) ---")
        print(scanner_stderr)
        print("--- Fim do STDERR do Sonar Scanner ---\n")

      # Verificar se a análise foi bem-sucedida no log do scanner
      # Esta é uma verificação básica; logs mais detalhados podem ser necessários para falhas complexas
      if "EXECUTION SUCCESS" not in scanner_stdout and "EXECUTION SUCCESS" not in scanner_stderr :
          print("ALERTA: A análise do Sonar Scanner pode não ter sido bem-sucedida (EXECUTION SUCCESS não encontrado nos logs).")
          # Você pode querer sair aqui ou adicionar uma lógica mais robusta de tratamento de falhas
          # Por exemplo: if "ANALYSIS SUCCESSFUL" not in scanner_stdout: exit("Análise falhou")

      task_id = self.get_task_id_from_scanner_log(scanner_stdout)
      if not task_id and scanner_stderr: # Tenta obter do stderr se não estiver no stdout
          task_id = self.get_task_id_from_scanner_log(scanner_stderr)

      self.wait_for_analysis_completion(task_id)

      metrics = self.collect_metrics(token)
      self.save_to_csv(metrics)
      print("Análise do SonarQube concluída com sucesso!")

    except Exception as e:
        print(f"Ocorreu um erro durante a execução: {e}")
    finally:
      self.stop_docker()