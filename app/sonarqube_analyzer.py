import csv
import os
import requests
import time
import subprocess
import re
import json
import platform

from datetime import datetime
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth
from slugify import slugify

class SonarQubeAnalyzer:
  def __init__(self):
    self.load_enviroment()
    self.project_key = self.get_project_key(self.project_path)
    self.is_flutter_project = self.detect_flutter_project()
    self.metrics = ['new_technical_debt','analysis_from_sonarqube_9_4','blocker_violations','bugs','classes','code_smells','cognitive_complexity','comment_lines','comment_lines_density','comment_lines_data','class_complexity','file_complexity','function_complexity','complexity_in_classes','complexity_in_functions','branch_coverage','new_branch_coverage','conditions_to_cover','new_conditions_to_cover','confirmed_issues','coverage','new_coverage','critical_violations','complexity','last_commit_date','development_cost','new_development_cost','directories','duplicated_blocks','new_duplicated_blocks','duplicated_files','duplicated_lines','duplicated_lines_density','new_duplicated_lines_density','new_duplicated_lines','duplications_data','effort_to_reach_maintainability_rating_a','executable_lines_data','false_positive_issues','file_complexity_distribution','files','function_complexity_distribution','functions','generated_lines','generated_ncloc','info_violations','violations','line_coverage','new_line_coverage','lines','ncloc','ncloc_language_distribution','lines_to_cover','new_lines_to_cover','sqale_rating','new_maintainability_rating','major_violations','minor_violations','ncloc_data','new_blocker_violations','new_bugs','new_code_smells','new_critical_violations','new_info_violations','new_violations','new_lines','new_major_violations','new_minor_violations','new_security_hotspots','new_vulnerabilities','unanalyzed_c','unanalyzed_cpp','open_issues','quality_profiles','projects','public_api','public_documented_api_density','public_undocumented_api','quality_gate_details','alert_status','reliability_rating','new_reliability_rating','reliability_remediation_effort','new_reliability_remediation_effort','reopened_issues','security_hotspots','security_hotspots_reviewed','new_security_hotspots_reviewed','security_rating','new_security_rating','security_remediation_effort','new_security_remediation_effort','security_review_rating','new_security_review_rating','security_hotspots_reviewed_status','new_security_hotspots_reviewed_status','security_hotspots_to_review_status','new_security_hotspots_to_review_status','skipped_tests','statements']

  def load_enviroment(self):
    load_dotenv(dotenv_path='.env')
    load_dotenv(dotenv_path='app/.env')

    self.sonar_external_host_url = os.getenv('SONAR_EXTERNAL_HOST_URL', 'http://localhost:9000')
    self.sonar_internal_host_url = os.getenv('SONAR_INTERNAL_HOST_URL', 'http://sonarqube:9000')

    self.sonar_username = os.getenv('SONAR_USERNAME')
    self.sonar_password = os.getenv('SONAR_PASSWORD')
    self.output_path = os.getenv('OUTPUT_PATH')
    self.participant = os.getenv('PARTICIPANT')
    self.project_path = os.getenv('PROJECT_PATH')
    
    self.sonar_exclusions = os.getenv('SONAR_EXCLUSIONS', '**/node_modules/**,**/.venv/**,**/venv/**,**/tmp/**,**/build/**,**/__pycache__/**,**/.git/**,**/.idea/**,**/target/**,**/out/**,**/dist/**,**/bin/**,**/obj/**,**/site-packages/**,**/third_party/**')

    self.flutter_coverage_report_path = os.getenv('FLUTTER_COVERAGE_REPORT_PATH', 'coverage/lcov.info')
    self.flutter_analysis_report_path = os.getenv('FLUTTER_ANALYSIS_REPORT_PATH', 'analysis.log')


  def get_project_key(self, project_path):
    if not project_path:
        raise ValueError("PROJECT_PATH não está definido ou está vazio na configuração de ambiente.")
    cleaned_path = project_path.rstrip("\\/")
    return cleaned_path.replace('\\','/').split('/')[-1]

  def detect_flutter_project(self):
    if not self.project_path:
        return False
    pubspec_path = os.path.join(self.project_path, 'pubspec.yaml')
    is_flutter = os.path.exists(pubspec_path)
    if is_flutter:
        print("Projeto Flutter detectado (pubspec.yaml encontrado).")
    else:
        print("Projeto não parece ser Flutter (pubspec.yaml não encontrado).")
    return is_flutter

  def run_command(self, command):
    result = subprocess.run(command, shell=True, capture_output=True, text=True, encoding='utf-8')
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
    max_retries = 30
    retries = 0
    while retries < max_retries:
      try:
        response = requests.get(f"{self.sonar_external_host_url}/api/system/status")
        response.raise_for_status()
        json_response = response.json()
        status = json_response.get("status")
        print(f"Aguardando SonarQube... (status: {status})")
        if status == "UP":
          print("SonarQube está pronto!")
          return True
      except requests.exceptions.RequestException as e:
        print(f"Ocorreu um erro ao contatar o SonarQube: {e}")

      retries +=1
      if retries < max_retries:
          print("Tentando novamente em 10 segundos...")
          time.sleep(10)
      else:
          print("Tempo máximo de espera pelo SonarQube atingido.")
          return False

  def check_flutter_plugin_installed(self):
    if not self.is_flutter_project:
        return True # Não é relevante se não for projeto Flutter

    print("Verificando se o plugin SonarFlutter está instalado...")
    try:
        response = requests.get(
            f"{self.sonar_external_host_url}/api/plugins/installed",
            auth=HTTPBasicAuth(self.sonar_username, self.sonar_password)
        )
        response.raise_for_status()
        plugins_data = response.json()

        flutter_plugin_key = "flutter" # Chave esperada para o plugin insideapp-oss/sonar-flutter

        found_plugin = any(
            plugin['key'] == flutter_plugin_key for plugin in plugins_data.get('plugins', [])
        )

        if found_plugin:
            print(f"Plugin SonarFlutter (key: '{flutter_plugin_key}') encontrado e instalado.")
            return True
        else:
            print(f"ALERTA: Plugin SonarFlutter (key: '{flutter_plugin_key}') NÃO encontrado.")
            print("Certifique-se de que o .jar do plugin está em ./app/plugin e o SonarQube foi reiniciado.")
            return False # Plugin não encontrado, pode ser um problema

    except requests.exceptions.RequestException as e:
        print(f"Erro ao verificar plugins instalados: {e}")
        return False
    except json.JSONDecodeError:
        print(f"Erro ao decodificar resposta JSON da API de plugins: {response.text}")
        return False

  def run_flutter_commands(self):
    """Executa 'flutter analyze' e 'flutter test --coverage' no diretório do projeto,
       de forma compatível com Windows e Linux/macOS."""
    if not self.is_flutter_project:
      return True # Não é um projeto Flutter, não faz nada

    # Determina o nome do comando flutter com base no sistema operacional
    if platform.system() == "Windows":
        flutter_command_name = "flutter.bat"
    else: # Linux, macOS, etc.
        flutter_command_name = "flutter"

    print(f"Iniciando execução de comandos Flutter em: {self.project_path} usando '{flutter_command_name}'")
    print("IMPORTANTE: O Flutter SDK DEVE estar instalado e no PATH do sistema para que esta etapa funcione.")

    reports_generated_successfully = True

    # --- Comando 1: flutter analyze ---
    analysis_report_target_path = os.path.join(self.project_path, self.flutter_analysis_report_path)
    try:
        # Garante que o diretório para o relatório de análise exista
        # Se self.flutter_analysis_report_path for apenas um nome de arquivo, os.path.dirname retornará ''
        # e os.makedirs('', exist_ok=True) não faz nada, o que está correto.
        report_dir = os.path.dirname(analysis_report_target_path)
        if report_dir: # Só cria o diretório se houver um (não é apenas um nome de arquivo na raiz)
             os.makedirs(report_dir, exist_ok=True)
    except FileExistsError:
        pass # O diretório já existe

    print(f"Executando: {flutter_command_name} analyze (saída para '{self.flutter_analysis_report_path}')")
    try:
      process_analyze = subprocess.Popen(
          [flutter_command_name, 'analyze'], # USA A VARIÁVEL AQUI
          cwd=self.project_path,
          stdout=subprocess.PIPE,
          stderr=subprocess.PIPE,
          text=True,
          encoding='utf-8',
          env=os.environ.copy() # Boa prática manter
      )
      stdout_analyze, stderr_analyze = process_analyze.communicate()

      if process_analyze.returncode == 0 or process_analyze.returncode == 1:
        with open(analysis_report_target_path, 'w', encoding='utf-8') as f_analyze:
          f_analyze.write(stdout_analyze)
        print(f"'{flutter_command_name} analyze' concluído (código: {process_analyze.returncode}). Relatório salvo em '{analysis_report_target_path}'.")
        if stderr_analyze:
            print(f"Saída de erro (stderr) de '{flutter_command_name} analyze':\n{stderr_analyze}")
      else:
        print(f"ERRO: '{flutter_command_name} analyze' falhou com código de saída {process_analyze.returncode}.")
        print(f"STDOUT:\n{stdout_analyze}")
        print(f"STDERR:\n{stderr_analyze}")
        reports_generated_successfully = False
        if os.path.exists(analysis_report_target_path):
            try: os.remove(analysis_report_target_path)
            except OSError: pass
    except FileNotFoundError:
      print(f"ERRO CRÍTICO: Comando '{flutter_command_name}' não encontrado. Verifique se o Flutter SDK está instalado e no PATH do sistema.")
      return False
    except Exception as e:
      print(f"Erro inesperado ao executar '{flutter_command_name} analyze': {e}")
      reports_generated_successfully = False

    # --- Comando 2: flutter test --coverage ---
    coverage_lcov_full_path = os.path.join(self.project_path, self.flutter_coverage_report_path)
    try:
        report_dir_coverage = os.path.dirname(coverage_lcov_full_path)
        if report_dir_coverage: # Só cria o diretório se houver um
            os.makedirs(report_dir_coverage, exist_ok=True)
    except FileExistsError:
        pass

    print(f"Executando: {flutter_command_name} test --coverage (espera-se que gere '{self.flutter_coverage_report_path}')")
    try:
      process_test = subprocess.run(
          [flutter_command_name, 'test', '--coverage'], # USA A VARIÁVEL AQUI
          cwd=self.project_path,
          capture_output=True,
          text=True,
          encoding='utf-8',
          check=False,
          env=os.environ.copy() # Boa prática manter
      )
      if process_test.returncode == 0:
        print(f"'{flutter_command_name} test --coverage' concluído com sucesso.")
        if not os.path.exists(coverage_lcov_full_path):
            print(f"ALERTA: '{flutter_command_name} test --coverage' executado, mas o arquivo LCOV '{coverage_lcov_full_path}' não foi encontrado.")
        elif os.path.exists(coverage_lcov_full_path) and os.path.getsize(coverage_lcov_full_path) == 0:
            print(f"ALERTA: Arquivo LCOV '{coverage_lcov_full_path}' foi gerado mas está vazio.")
      else:
        print(f"ALERTA: '{flutter_command_name} test --coverage' falhou com código de saída {process_test.returncode}.")
        print(f"STDOUT de '{flutter_command_name} test --coverage':\n{process_test.stdout}")
        print(f"STDERR de '{flutter_command_name} test --coverage':\n{process_test.stderr}")
        if not os.path.exists(coverage_lcov_full_path):
            print(f"ERRO: Arquivo LCOV '{coverage_lcov_full_path}' não foi gerado devido à falha do '{flutter_command_name} test --coverage'.")
            reports_generated_successfully = False
    except FileNotFoundError:
      print(f"ERRO CRÍTICO: Comando '{flutter_command_name}' não encontrado. Verifique se o Flutter SDK está instalado e no PATH do sistema.")
      return False
    except Exception as e:
      print(f"Erro inesperado ao executar '{flutter_command_name} test --coverage': {e}")
      reports_generated_successfully = False

    if not reports_generated_successfully:
        print("ALERTA GERAL: A geração de um ou mais relatórios Flutter falhou ou teve problemas. A análise SonarQube pode ser incompleta.")

    print("Geração de relatórios Flutter (tentativa) concluída.")
    return True

  def generate_token(self):
    print("Gerando token de acesso...")
    try:
      response = requests.post(
        f"{self.sonar_external_host_url}/api/user_tokens/generate",
        auth=(self.sonar_username, self.sonar_password),
        data={"name": "my_token_python_script"}
      )
      response.raise_for_status()
      return response.json()["token"]
    except requests.exceptions.RequestException as e:
      print(f"Erro ao gerar token: {e}")
      if e.response is not None:
          print(f"Detalhes do erro: {e.response.text}")
      exit(1)

  def run_sonar_scanner(self, token):
    print("Executando Sonar Scanner...")

    absolute_project_path = os.path.abspath(self.project_path)
    if not os.path.exists(absolute_project_path):
        raise FileNotFoundError(f"PROJECT_PATH {absolute_project_path} não existe.")
    if not os.path.isdir(absolute_project_path):
        raise NotADirectoryError(f"PROJECT_PATH {absolute_project_path} não é um diretório.")

    sonar_params = [
        f"-Dsonar.projectKey={self.project_key}",
        f"-Dsonar.projectName={self.project_key}",
        f"-Dsonar.host.url={self.sonar_internal_host_url}",
        f"-Dsonar.login={token}",
        f"-Dsonar.verbose=true",
        f"-Dsonar.scm.disabled=true",
        f"-Dsonar.exclusions={self.sonar_exclusions}"
    ]

    if self.is_flutter_project:
        print("Configurando parâmetros específicos para projeto Flutter...")
        sonar_params.append("-Dsonar.sources=lib")
        sonar_params.append("-Dsonar.tests=test")

        abs_coverage_path = os.path.join(self.project_path, self.flutter_coverage_report_path) # Usar self.project_path aqui
        if os.path.exists(abs_coverage_path):
            print(f"Relatório de cobertura encontrado: {abs_coverage_path}")
            # O caminho para o scanner deve ser relativo à raiz do projeto DENTRO do container
            sonar_params.append(f"-Dsonar.flutter.coverage.reportPath={self.flutter_coverage_report_path}")
        else:
            print(f"ALERTA: Relatório de cobertura LCOV não encontrado em '{abs_coverage_path}' (esperado em '{self.flutter_coverage_report_path}' relativo ao projeto). A análise de cobertura será omitida.")

        abs_analysis_report_path = os.path.join(self.project_path, self.flutter_analysis_report_path) # Usar self.project_path aqui
        if os.path.exists(abs_analysis_report_path):
            print(f"Relatório de análise ('flutter analyze') encontrado: {abs_analysis_report_path}")
            sonar_params.append(f"-Dsonar.flutter.analysis.reportPath={self.flutter_analysis_report_path}")
        else:
            print(f"ALERTA: Relatório de análise ('flutter analyze') não encontrado em '{abs_analysis_report_path}' (esperado em '{self.flutter_analysis_report_path}' relativo ao projeto).")
    else:
        sonar_params.append("-Dsonar.sources=.")

    command_params_str = " ".join(sonar_params)
    command = (
        f"docker-compose run --rm "
        f"-e SONAR_TOKEN={token} "
        f"--workdir /usr/src/{self.project_key} "
        f"-v \"{absolute_project_path}:/usr/src/{self.project_key}\" "
        f"sonar-scanner-cli "
        f"{command_params_str}"
    )
    print(f"Executando comando do scanner: {command}")
    stdout, stderr = self.run_command(command)
    return stdout, stderr

  def get_task_id_from_scanner_log(self, log_output):
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
    max_retries = 30
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
            project_check_url = f"{self.sonar_external_host_url}/api/projects/lookup"
            project_params = {"project": self.project_key}
            project_response = requests.get(project_check_url, params=project_params, auth=HTTPBasicAuth(self.sonar_username, self.sonar_password))
            if project_response.status_code == 200:
                print(f"Projeto {self.project_key} encontrado no SonarQube após a análise.")
                return
            else:
                print(f"Projeto {self.project_key} ainda não encontrado (status: {project_response.status_code}) após o sucesso da tarefa. Verifique o SonarQube.")
                return
          elif status in ["FAILED", "CANCELED"]:
            error_message = task_info.get("errorMessage", "Nenhuma mensagem de erro detalhada.")
            print(f"Tarefa de análise {task_id} FALHOU ou foi CANCELADA. Status: {status}. Erro: {error_message}")
            exit(f"Tarefa {task_id} do Compute Engine do SonarQube falhou. Não é possível coletar métricas.")
        else:
          print(f"Não foi possível obter informações da tarefa para {task_id}. Resposta: {response.text}")
      except requests.exceptions.RequestException as e:
        print(f"Erro ao verificar o status da tarefa de análise: {e}")
      except ValueError as e:
        print(f"Erro ao decodificar resposta JSON para status da tarefa: {e}")

      retries += 1
      if retries < max_retries:
          print("Tentando novamente em 10 segundos...")
          time.sleep(10)
      else:
          print(f"Tempo máximo de espera atingido para a tarefa {task_id}. O projeto pode não estar pronto.")
          exit(f"A tarefa de análise {task_id} não foi concluída com SUCESSO a tempo.")

  def collect_metrics(self, token):
    print("Coletando métricas...")
    url = f"{self.sonar_external_host_url}/api/measures/component"
    params = {"component": self.project_key, "metricKeys": ",".join(self.metrics)}
    auth = HTTPBasicAuth(self.sonar_username, self.sonar_password)

    try:
      response = requests.get(url, params=params, auth=auth)
      response.raise_for_status()
      return response.json()["component"]["measures"]
    except requests.exceptions.RequestException as e:
      print(f"({e.response.status_code if e.response else 'N/A'}) Erro ao coletar métricas: {e.response.text if e.response else e}")
      exit(1)
    except KeyError:
      print(f"Erro ao processar a resposta JSON da coleta de métricas. 'component' ou 'measures' não encontrado. Resposta: {response.text}")
      exit(1)

  def save_to_csv(self, metrics):
    print("Salvando métricas em CSV...")
    if not metrics:
        print("Nenhuma métrica foi coletada. O arquivo CSV não será gerado.")
        return

    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    ts = int(datetime.timestamp(now))
    slug = slugify(self.participant)

    filename = f"{slug}-{ts}.csv"
    directory = os.path.join(self.output_path, 'sonar_analysis_output', date_str)
    filepath = os.path.join(directory, filename)

    if not os.path.exists(directory):
      os.makedirs(directory)

    with open(filepath, "w", newline="", encoding='utf-8') as file:
      writer = csv.writer(file)
      writer.writerow(["Metric", "Value", "Datetime", "Participant"])
      for metric in metrics:
        writer.writerow([metric["metric"], metric.get("value", "N/A"), now, self.participant])
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
      if not self.wait_for_sonarqube():
          raise RuntimeError("SonarQube não iniciou corretamente. Abortando.")

      flutter_plugin_ok = True
      if self.is_flutter_project:
          if not self.check_flutter_plugin_installed():
              print("ALERTA: Plugin Flutter não encontrado ou erro ao verificar. A análise Flutter pode não funcionar como esperado ou falhar.")
              flutter_plugin_ok = False # Permite continuar, mas com alerta. Poderia ser um erro fatal.

          # Executa comandos Flutter para gerar relatórios
          if not self.run_flutter_commands():
              # Se run_flutter_commands retornar False, indica um erro crítico (ex: Flutter SDK não encontrado)
              raise RuntimeError("Falha crítica ao tentar executar comandos Flutter. Abortando.")

      token = self.generate_token()

      scanner_stdout, scanner_stderr = self.run_sonar_scanner(token)
      print("\n--- Saída do Sonar Scanner (STDOUT) ---")
      print(scanner_stdout)
      print("--- Fim do STDOUT do Sonar Scanner ---\n")

      if scanner_stderr:
        print("\n--- Saída de Erro do Sonar Scanner (STDERR) ---")
        print(scanner_stderr)
        print("--- Fim do STDERR do Sonar Scanner ---\n")

      # Checagem básica do log do scanner
      if "EXECUTION SUCCESS" not in scanner_stdout and "EXECUTION SUCCESS" not in scanner_stderr :
          # Se for um projeto flutter e o plugin não estiver ok, o scanner pode falhar por isso.
          if self.is_flutter_project and not flutter_plugin_ok:
              print("ERRO: A análise do Sonar Scanner falhou, possivelmente devido à ausência do plugin Flutter ou configuração incorreta.")
          else:
              print("ALERTA: A análise do Sonar Scanner pode não ter sido bem-sucedida (EXECUTION SUCCESS não encontrado nos logs).")
          # Considerar sair se a falha do scanner for crítica
          # exit("Scanner falhou.")

      task_id = self.get_task_id_from_scanner_log(scanner_stdout)
      if not task_id and scanner_stderr:
          task_id = self.get_task_id_from_scanner_log(scanner_stderr)

      self.wait_for_analysis_completion(task_id)

      metrics = self.collect_metrics(token)
      self.save_to_csv(metrics)
      print("Análise do SonarQube concluída com sucesso!")

    except Exception as e:
        print(f"Ocorreu um erro durante a execução: {e}")
    finally:
      self.stop_docker()