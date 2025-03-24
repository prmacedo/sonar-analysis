import os
from dotenv import load_dotenv

load_dotenv(dotenv_path='app/.env')

SONAR_USERNAME=os.getenv('SONAR_USERNAME')
SONAR_PASSWORD=os.getenv('SONAR_PASSWORD')
SONAR_HOST_URL=os.getenv('SONAR_HOST_URL')
COMPOSE_PROJECT_NAME=os.getenv('COMPOSE_PROJECT_NAME')


def print_env():
  print(SONAR_USERNAME, SONAR_PASSWORD, SONAR_HOST_URL, COMPOSE_PROJECT_NAME)


if __name__ == "__main__":
  print_env()