import sys
import os

# ===== LINKAR A PASTA LOCAL DE BIBLIOTECAS (DEVE SER ANTES DOS IMPORTS) =====
# Garante que o Python vai buscar as bibliotecas na pasta "libs" ao lado do script
diretorio_atual = os.path.dirname(os.path.abspath(__file__))
pasta_libs = os.path.join(diretorio_atual, "libs")

if pasta_libs not in sys.path:
    sys.path.insert(0, pasta_libs)

# ===== AGORA OS IMPORTS VÃO FUNCIONAR DIRETO DA PASTA LOCAL ====
import base64
import time
import random
from google import genai
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

# ===== CONFIGURAÇÃO =====
CHAVE_CRIPTO = b"66af7ccabb8216426de4ab0c2a875e379537bba86b52946365f8d6b1cdcaf196"[
    :32
]  # 32 bytes AES-256
IV = b"e41ada69ab079e1e"  # 16 bytes
ARQUIVO_PERGUNTA = "questao.txt"
ARQUIVO_SAIDA = "resposta.txt"
API_KEY = os.getenv("API_DO_GEMINI")

# ===== CONFIGURAÇÃO DE RETRY E RATE LIMITING =====
MAX_RETRIES = 3
INITIAL_WAIT_TIME = 2  # segundos
MAX_WAIT_TIME = 30  # segundos


# ===== CRIPTO =====
def AES_encrypt(text: str) -> str:
    """Criptografa texto usando AES-256-CBC."""
    cipher = AES.new(CHAVE_CRIPTO, AES.MODE_CBC, iv=IV)
    ct = cipher.encrypt(pad(text.encode(), AES.block_size))
    return base64.b64encode(ct).decode()


def AES_decrypt(b64_text: str) -> str:
    """Descriptografa texto usando AES-256-CBC."""
    ct = base64.b64decode(b64_text.encode())
    cipher = AES.new(CHAVE_CRIPTO, AES.MODE_CBC, iv=IV)
    pt = unpad(cipher.decrypt(ct), AES.block_size)
    return pt.decode()


# ===== MAIN =====
def main():
    """Função principal."""
    # Salva referência original de stdout/stderr ANTES de redirecionar
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    # Suprime erros pra não aparecer nada
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

    # Verifica se API key existe
    if not API_KEY:
        original_stderr.write("Variável de ambiente API_DO_GEMINI não configurada.\n")
        sys.exit(1)

    # Conecta ao Google e obtém resposta com retry automático
    resposta_texto = ""
    client = genai.Client(api_key=API_KEY)

    prompt = f"Resolva a seguinte questão e retorne APENAS a resposta e se necessário for pergunta que pede pra resolver tipo beecrowd leetcode voce vai passar o codigo da pergunta se uma questão tiver restrições voce tem que seguir ela sem questionar e voce vai fazer codigo nivel iniciante em python e sempre mudando a logica e faça sem cara de ia o codigo: {pergunta}"

    # Tenta contar tokens
    try:
        token_count = client.models.count_tokens(
            model="gemini-2.5-flash", contents=prompt
        )
        original_stdout.write(f"📊 Tokens estimados: {token_count.total_tokens}\n")
        original_stdout.flush()
    except Exception as e:
        original_stderr.write(f"⚠️ Erro ao contar tokens: {str(e)}\n")
        original_stderr.flush()

    # Retry com backoff exponencial
    for tentativa in range(MAX_RETRIES):
        try:
            resposta = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            resposta_texto = resposta.text.strip()
            break  # Sucesso, sai do loop
        except Exception as e:
            erro_msg = str(e)
            if tentativa < MAX_RETRIES - 1:
                # Calcula tempo de espera com backoff exponencial + jitter
                wait_time = min(INITIAL_WAIT_TIME * (2**tentativa), MAX_WAIT_TIME)
                wait_time += random.uniform(0, 1)  # Adiciona aleatoriedade
                original_stdout.write(
                    f"⏳ Tentativa {tentativa + 1} falhou. Aguardando {wait_time:.1f}s...\n"
                )
                original_stdout.flush()
                time.sleep(wait_time)
            else:
                resposta_texto = f"ERRO_API_FINAL: {erro_msg}"
                original_stderr.write(f"❌ {erro_msg}\n")
                original_stderr.flush()

    # Criptografa
    pergunta_cript = AES_encrypt(pergunta)
    resposta_cript = AES_encrypt(resposta_texto)

    # ===== EXIBE NA TELA (APENAS POR 20 SEGUNDOS) =====
    # Restaura stdout original
    sys.stdout = original_stdout
    print("\n \nPERGUNTA:", pergunta_cript)
    print("RESPOSTA:", resposta_cript)
    print("\nArquivo será salvo em 20 segundos...\n")

    # ===== SALVA RESPOSTA DESCRIPTOGRAFADA EM ARQUIVO IMEDIATAMENTE =====
    resposta_descriptografada = AES_decrypt(resposta_cript)
    with open(ARQUIVO_SAIDA, "w", encoding="utf-8") as f:
        f.write(resposta_descriptografada)

    time.sleep(20)

    # ===== APAGA O ARQUIVO APÓS 20 SEGUNDOS =====
    if os.path.exists(ARQUIVO_SAIDA):
        os.remove(ARQUIVO_SAIDA)


if __name__ == "__main__":
    main()
