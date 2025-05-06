# Sonar Analysis

## Preparação do ambiente

1. Instalar python e docker

2. Criar e ativar ambiente virtual do python (venv)

3. Instalar dependências `pip install -r requirements.txt`

4. Rodar o comando `python setup.py` para configurar o caminho da raiz do projeto a ser analisado nas variáveis `PROJECT_PATH` e `OUTPUT_PATH` no arquivo `.env`, além de se identificar na variável `PARTICIPANT`

5. Rodar comando `python main.py`

## Criação e ativação de venv

### Criar venv

Execute o seguinte comando para criar a venv: `python3 -m venv nome_da_venv`

### Ativar a venv:

Após criar a venv, você precisa ativá-la para começar a usar o ambiente isolado.

- No Linux/macOS: Para ativar a venv, use o comando: `source nome_da_venv/bin/activate`

- No Windows: Para ativar a venv, use o seguinte comando: `.\nome_da_venv\Scripts\activate`

## TODO

Adicionar plugin de Flutter e ajustar o código para rodar em projetos Flutter
