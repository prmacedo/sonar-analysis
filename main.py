from app.sonarqube_analyzer import SonarQubeAnalyzer

if __name__ == '__main__':
  analyzer = SonarQubeAnalyzer()
  analyzer.execute()