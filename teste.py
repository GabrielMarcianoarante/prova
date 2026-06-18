import sys
import os
import platform
import subprocess

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

REQUIREMENTS = [
    "google-genai",
    "pycryptodome",
]


def garantir_libs_instaladas():
    """Verifica se a pasta de libs pra esse ambiente existe; se não, instala."""
    marcador = os.path.join(pasta_libs, ".instalado_ok")

    if os.path.exists(marcador):
        return  # já instalado antes pra essa versão de Python, não faz nada

    print(f"[SETUP] Primeira execução detectada para o ambiente: {TAG_AMBIENTE}")
    print(f"[SETUP] Instalando dependências em: {pasta_libs}")
    print("[SETUP] Isso só acontece uma vez por versão de Python/SO. Aguarde...")

    os.makedirs(pasta_libs, exist_ok=True)

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--target",
                pasta_libs,
                "--upgrade",
                "--no-user",
                *REQUIREMENTS,
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as e:
        print("[SETUP] ERRO ao instalar dependências automaticamente.")
        print(
            "[SETUP] STDERR:", e.stderr.decode(errors="ignore") if e.stderr else "N/A"
        )
        print(
            "[SETUP] STDOUT:", e.stdout.decode(errors="ignore") if e.stdout else "N/A"
        )
        sys.exit(1)

    # Cria o marcador de sucesso, pra não tentar reinstalar nas próximas execuções
    with open(marcador, "w") as f:
        f.write("ok")

    print("[SETUP] Dependências instaladas com sucesso.\n")


garantir_libs_instaladas()

if pasta_libs not in sys.path:
    sys.path.insert(0, pasta_libs)

# ===== AGORA OS IMPORTS FUNCIONAM, JÁ GARANTIDOS PRA ESSA VERSÃO DE PYTHON =====
import base64
import time
import random
from google import genai
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

# ===== RESTANTE DO SCRIPT (igual ao original) =====
CHAVE_CRIPTO = b"66af7ccabb8216426de4ab0c2a875e379537bba86b52946365f8d6b1cdcaf196"[:32]
IV = b"e41ada69ab079e1e"
ARQUIVO_PERGUNTA = "questao.txt"
ARQUIVO_SAIDA = "resposta.txt"
API_KEY = os.getenv("API_DO_GEMINI")

MAX_RETRIES = 3
INITIAL_WAIT_TIME = 2
MAX_WAIT_TIME = 30


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
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    if sys.platform == "win32":
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
        sys.stderr = open(os.devnull, "w", encoding="utf-8")

    pergunta = ""
    try:
        with open(ARQUIVO_PERGUNTA, "r", encoding="utf-8", errors="ignore") as f:
            pergunta = f.read().strip()
    except FileNotFoundError:
        original_stderr.write("Arquivo questao.txt não existe.\n")
        sys.exit(1)

    if not pergunta:
        original_stderr.write("Arquivo questao.txt vazio.\n")
        sys.exit(1)

    if not API_KEY:
        original_stderr.write("Variável de ambiente API_DO_GEMINI não configurada.\n")
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
    print("\n \nPERGUNTA:", pergunta_cript)
    print("RESPOSTA:", resposta_cript)
    print("\nArquivo será salvo em 20 segundos...\n")

    resposta_descriptografada = AES_decrypt(resposta_cript)
    with open(ARQUIVO_SAIDA, "w", encoding="utf-8") as f:
        f.write(resposta_descriptografada)

    time.sleep(20)

    if os.path.exists(ARQUIVO_SAIDA):
        os.remove(ARQUIVO_SAIDA)


if __name__ == "__main__":
    main()
