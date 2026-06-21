import sys
import os
import platform
import subprocess
from pathlib import Path

# ===== CONFIGURAÇÃO DA PASTA DE LIBS, ISOLADA POR VERSÃO/PLATAFORMA =====
diretorio_atual = os.path.dirname(os.path.abspath(__file__))

# Cria uma "tag" única por versão do Python + SO + arquitetura
# Ex: cp311-windows-amd64, cp312-windows-amd64, cp311-linux-x86_64 etc.
TAG_AMBIENTE = (
    f"cp{sys.version_info.major}{sys.version_info.minor}-"
    f"{platform.system().lower()}-{platform.machine().lower()}"
)

pasta_libs_base = os.path.join(diretorio_atual, "libs")
pasta_libs = os.path.join(pasta_libs_base, TAG_AMBIENTE)

# Pacote pip -> módulo que ele expõe (usado pra detectar e instalar individualmente
# se algo faltar mesmo depois da instalação em lote)
PACOTES = {
    "google-genai": "google.genai",
    "pycryptodome": "Crypto",
}

# Versões fixas (testadas). Se a instalação com essas versões falhar
# (ex: não existe pra essa versão do Python), cai pra versão livre automaticamente.
REQUIREMENTS_FIXADOS = [
    "google-genai>=1.0.0,<2.0.0",
    "pycryptodome>=3.19,<4.0",
]
REQUIREMENTS_LIVRES = list(PACOTES.keys())

EH_MS_STORE = "WindowsApps" in sys.executable


def _rodar_pip(args, timeout=300):
    return subprocess.run(
        [sys.executable, "-m", "pip", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )


def garantir_pip():
    """Garante que o módulo pip existe; se não existir, tenta habilitar via ensurepip."""
    teste = subprocess.run(
        [sys.executable, "-m", "pip", "--version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if teste.returncode == 0:
        return True

    print(
        "[SETUP] pip não encontrado nesse Python. Tentando habilitar via ensurepip..."
    )
    resultado = subprocess.run(
        [sys.executable, "-m", "ensurepip", "--upgrade"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return resultado.returncode == 0


def _instalar(requirements, descricao):
    print(f"[SETUP] Tentando instalar ({descricao}): {', '.join(requirements)}")
    resultado = _rodar_pip(
        [
            "install",
            "--target",
            pasta_libs,
            "--upgrade",
            "--no-user",
            "--no-cache-dir",
            "--ignore-installed",
            *requirements,
        ]
    )
    return resultado


def garantir_libs_instaladas():
    """Instala as dependências na pasta isolada por ambiente, com fallback em camadas."""
    marcador = os.path.join(pasta_libs, ".instalado_ok_v2")

    if os.path.exists(marcador):
        return

    print(f"[SETUP] Primeira execução detectada para o ambiente: {TAG_AMBIENTE}")
    if EH_MS_STORE:
        print(
            "[SETUP] AVISO: Python instalado via Microsoft Store detectado.\n"
            "         Esse Python roda com restrições de sandbox (MSIX) e pode\n"
            "         causar falhas estranhas na instalação de bibliotecas com\n"
            "         binários nativos. Se der erro abaixo, instale o Python\n"
            "         oficial em https://python.org e use ele em vez do da Store."
        )

    os.makedirs(pasta_libs, exist_ok=True)

    if not garantir_pip():
        print(
            "\n[ERRO] Não foi possível habilitar o pip nesse Python.\n"
            "O QUE FAZER:\n"
            "  1. Verifique se o Python foi instalado corretamente (de preferência via python.org).\n"
            "  2. Rode manualmente no terminal: python -m ensurepip --upgrade\n"
            "  3. Se persistir, reinstale o Python marcando a opção 'pip' no instalador.\n"
        )
        sys.exit(1)

    # Tentativa 1: versões fixas (mais confiável e reprodutível entre máquinas)
    resultado = _instalar(REQUIREMENTS_FIXADOS, "versões fixas")

    # Tentativa 2: se falhar (ex: versão não existe pra esse Python), tenta sem fixar versão
    if resultado.returncode != 0:
        print(
            "[SETUP] Instalação com versões fixas falhou. Tentando com versões livres..."
        )
        resultado = _instalar(REQUIREMENTS_LIVRES, "versões mais recentes disponíveis")

    if resultado.returncode != 0:
        erro = resultado.stderr.decode(errors="ignore") if resultado.stderr else "N/A"
        print(
            "\n[ERRO] Não foi possível instalar as dependências automaticamente.\n"
            "DETALHE DO ERRO:\n"
            f"{erro}\n"
            "O QUE FAZER:\n"
            "  1. Verifique sua conexão com a internet.\n"
            "  2. Verifique se não há firewall/antivírus bloqueando o pip.\n"
            "  3. Tente instalar manualmente abrindo o terminal nesta pasta e rodando:\n"
            f'     {sys.executable} -m pip install --target "{pasta_libs}" '
            f"{' '.join(REQUIREMENTS_LIVRES)}\n"
            "  4. Se o erro mencionar 'Microsoft Visual C++', instale o 'Microsoft "
            "Visual C++ Redistributable' (procure no site da Microsoft).\n"
        )
        sys.exit(1)

    with open(marcador, "w") as f:
        f.write("ok")

    print("[SETUP] Dependências instaladas com sucesso.\n")


def garantir_modulo_individual(nome_pacote, nome_modulo):
    """Última linha de defesa: se faltar um módulo específico, tenta instalar só ele."""
    print(
        f"[SETUP] Módulo '{nome_modulo}' não encontrado. Tentando instalar '{nome_pacote}' individualmente..."
    )
    resultado = _rodar_pip(
        [
            "install",
            "--target",
            pasta_libs,
            "--upgrade",
            "--no-cache-dir",
            "--ignore-installed",
            nome_pacote,
        ]
    )
    if resultado.returncode != 0:
        erro = resultado.stderr.decode(errors="ignore") if resultado.stderr else "N/A"
        print(
            f"\n[ERRO] Não consegui instalar '{nome_pacote}' automaticamente.\n"
            "DETALHE DO ERRO:\n"
            f"{erro}\n"
            "O QUE FAZER:\n"
            f"  Abra o terminal nesta pasta e rode manualmente:\n"
            f'  {sys.executable} -m pip install --target "{pasta_libs}" {nome_pacote}\n'
            "  Depois rode o script de novo.\n"
        )
        sys.exit(1)
    print(f"[SETUP] '{nome_pacote}' instalado com sucesso.\n")


# Quando o nome do módulo Python não é igual ao nome do pacote no pip,
# mapeia pra instalar a coisa certa. Pra módulos desconhecidos, tenta
# instalar com o próprio nome do módulo (funciona pra maioria dos casos).
MODULO_PARA_PACOTE = {
    "Crypto": "pycryptodome",
    "google": "google-genai",
}


def importar_com_auto_instalacao(funcao_import, max_tentativas=6):
    """
    Executa uma função que faz import(s). Se faltar qualquer módulo (incluindo
    dependências internas que o pip não trouxe), descobre o nome certo,
    instala e tenta de novo — em cadeia, até resolver tudo ou esgotar tentativas.
    """
    ultimo_erro = None
    for _ in range(max_tentativas):
        try:
            return funcao_import()
        except ModuleNotFoundError as e:
            ultimo_erro = e
            nome_modulo = (e.name or "").split(".")[0]
            if not nome_modulo:
                break
            pacote = MODULO_PARA_PACOTE.get(nome_modulo, nome_modulo)
            garantir_modulo_individual(pacote, nome_modulo)
    # Esgotou as tentativas — deixa o erro real estourar com contexto.
    if ultimo_erro is not None:
        print(
            f"\n[ERRO] Mesmo após tentar instalar automaticamente, o módulo "
            f"'{ultimo_erro.name}' continua faltando.\n"
            "O QUE FAZER:\n"
            f"  Rode manualmente: {sys.executable} -m pip install --target "
            f"\"{pasta_libs}\" {(ultimo_erro.name or '').split('.')[0]}\n"
        )
        raise ultimo_erro


garantir_libs_instaladas()

if pasta_libs not in sys.path:
    sys.path.insert(0, pasta_libs)

# ===== IMPORTS COM AUTO-RECUPERAÇÃO CASO FALTE ALGUMA BIBLIOTECA =====
# ===== IMPORTS COM AUTO-RECUPERAÇÃO CASO FALTE ALGUMA BIBLIOTECA (mesmo dependências internas) =====
import base64
import time
import random


def _import_genai():
    global genai
    from google import genai as _g

    genai = _g


def _import_crypto():
    global AES, pad, unpad
    from Crypto.Cipher import AES as _AES
    from Crypto.Util.Padding import pad as _pad, unpad as _unpad

    AES = _AES
    pad = _pad
    unpad = _unpad


importar_com_auto_instalacao(_import_genai)
importar_com_auto_instalacao(_import_crypto)

# ===== RESTANTE DO SCRIPT =====
CHAVE_CRIPTO = b"66af7ccabb8216426de4ab0c2a875e379537bba86b52946365f8d6b1cdcaf196"[:32]
IV = b"e41ada69ab079e1e"
ARQUIVO_PERGUNTA = os.path.join(diretorio_atual, "questao.txt")
ARQUIVO_SAIDA = os.path.join(diretorio_atual, "resposta.txt")
DOTENV_FILE = Path(diretorio_atual) / ".env"
API_KEY_ENV_VARS = (
    "API_DO_GEMINI",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "GOOGLE_GENAI_API_KEY",
)

MAX_RETRIES = 3
INITIAL_WAIT_TIME = 2
MAX_WAIT_TIME = 30


def carregar_api_key() -> str:
    """Procura a chave em variáveis de ambiente ou em um arquivo .env."""
    for nome in API_KEY_ENV_VARS:
        valor = os.getenv(nome)
        if valor and valor.strip():
            return valor.strip()

    if DOTENV_FILE.is_file():
        for linha in DOTENV_FILE.read_text(encoding="utf-8").splitlines():
            texto = linha.strip()
            if not texto or texto.startswith("#") or "=" not in texto:
                continue
            chave, valor = texto.split("=", 1)
            chave = chave.strip()
            valor = valor.strip().strip('"').strip("'")
            if chave in API_KEY_ENV_VARS and valor:
                os.environ[chave] = valor
                return valor

    return ""


def AES_encrypt(text: str) -> str:
    cipher = AES.new(CHAVE_CRIPTO, AES.MODE_CBC, iv=IV)
    ct = cipher.encrypt(pad(text.encode(), AES.block_size))
    return base64.b64encode(ct).decode()


def AES_decrypt(b64_text: str) -> str:
    ct = base64.b64decode(b64_text.encode())
    cipher = AES.new(CHAVE_CRIPTO, AES.MODE_CBC, iv=IV)
    pt = unpad(cipher.decrypt(ct), AES.block_size)
    return pt.decode()


def main():
    # Evita UnicodeEncodeError em consoles Windows com codepage não-UTF8
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    original_stdout = sys.stdout
    original_stderr = sys.stderr
    stdout_null = None
    stderr_null = None

    try:
        if sys.platform == "win32":
            stdout_null = open(os.devnull, "w", encoding="utf-8")
            stderr_null = open(os.devnull, "w", encoding="utf-8")
            sys.stdout = stdout_null
            sys.stderr = stderr_null

        pergunta = ""
        try:
            with open(ARQUIVO_PERGUNTA, "r", encoding="utf-8", errors="ignore") as f:
                pergunta = f.read().strip()
        except FileNotFoundError:
            original_stderr.write(f"Arquivo {ARQUIVO_PERGUNTA} não existe.\n")
            sys.exit(1)

        if not pergunta:
            original_stderr.write("Arquivo questao.txt vazio.\n")
            sys.exit(1)

        API_KEY = carregar_api_key()
        if not API_KEY:
            original_stderr.write(
                "Variável de ambiente da API não configurada. "
                f"Procure por uma destas chaves: {', '.join(API_KEY_ENV_VARS)} "
                f"ou um arquivo {DOTENV_FILE.name}.\n"
            )
            sys.exit(1)

        resposta_texto = ""
        client = genai.Client(api_key=API_KEY)

        prompt = f"Resolva a seguinte questão: {pergunta}"

        try:
            token_count = client.models.count_tokens(
                model="gemini-2.5-flash", contents=prompt
            )
            original_stdout.write(f"Tokens estimados: {token_count.total_tokens}\n")
            original_stdout.flush()
        except Exception as e:
            original_stderr.write(f"Erro ao contar tokens: {str(e)}\n")
            original_stderr.flush()

        for tentativa in range(MAX_RETRIES):
            try:
                resposta = client.models.generate_content(
                    model="gemini-2.5-flash", contents=prompt
                )
                resposta_texto = resposta.text.strip()
                break
            except Exception as e:
                erro_msg = str(e)
                if tentativa < MAX_RETRIES - 1:
                    wait_time = min(INITIAL_WAIT_TIME * (2**tentativa), MAX_WAIT_TIME)
                    wait_time += random.uniform(0, 1)
                    original_stdout.write(
                        f"Tentativa {tentativa + 1} falhou. Aguardando {wait_time:.1f}s...\n"
                    )
                    original_stdout.flush()
                    time.sleep(wait_time)
                else:
                    resposta_texto = f"ERRO_API_FINAL: {erro_msg}"
                    original_stderr.write(f"{erro_msg}\n")
                    original_stderr.flush()

        pergunta_cript = AES_encrypt(pergunta)
        resposta_cript = AES_encrypt(resposta_texto)

        sys.stdout = original_stdout
        sys.stderr = original_stderr
        print("\n \nPERGUNTA:", pergunta_cript)
        print("RESPOSTA:", resposta_cript)
        print("\nArquivo será salvo em 20 segundos...\n")

        resposta_descriptografada = AES_decrypt(resposta_cript)
        with open(ARQUIVO_SAIDA, "w", encoding="utf-8") as f:
            f.write(resposta_descriptografada)

        time.sleep(20)

        if os.path.exists(ARQUIVO_SAIDA):
            os.remove(ARQUIVO_SAIDA)
    finally:
        if stdout_null is not None:
            stdout_null.close()
        if stderr_null is not None:
            stderr_null.close()
        sys.stdout = original_stdout
        sys.stderr = original_stderr


if __name__ == "__main__":
    main()
