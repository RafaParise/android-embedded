#!/usr/bin/env python3
"""Conversa com a IA local do celular (Qwen2.5 0.5B no Termux, llama-server em 127.0.0.1:8080 DENTRO do aparelho).
O PC chega nela por 'adb forward' (cabo USB): nada fica exposto na rede. Qualquer agente (Claude Code, Hermes)
pode chamar este script: python scripts/ia-celular.py "pergunta"  (ou --estado para so ver se esta no ar).
Sem chave nem segredo. O modelo e pequeno (0,5 bi de parametros): bom para resumir e rascunhar, ruim para fatos."""
import json
import subprocess
import sys
import urllib.request

PORTA = 8080
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]


def adb(*args):
    return subprocess.run(["adb", *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)


def chama(caminho, corpo=None, timeout=180):
    req = urllib.request.Request(f"http://127.0.0.1:{PORTA}{caminho}", data=None if corpo is None else json.dumps(corpo).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    if "SM-A125" not in adb("shell", "getprop ro.product.model").stdout:
        sys.exit("ABORTADO: celular nao encontrado no ADB (cabo, depuracao USB)")
    adb("forward", f"tcp:{PORTA}", f"tcp:{PORTA}")
    try:
        chama("/health", timeout=10)
    except Exception:
        sys.exit("A IA do celular nao esta no ar. No Termux: setsid -f llama-server -m ~/modelos/qwen.gguf --host 127.0.0.1 "
                 "--port 8080 -c 2048 -t 4 > ~/llama.log 2> ~/llama.err")
    if "--estado" in sys.argv:
        print("IA do celular no ar (Qwen2.5 0.5B, http://127.0.0.1:8080 via adb forward)")
        return
    pergunta = " ".join(a for a in sys.argv[1:] if not a.startswith("--"))
    if not pergunta:
        sys.exit('Uso: python scripts/ia-celular.py "pergunta"')
    try:
        r = chama("/v1/chat/completions", {"model": "qwen", "max_tokens": 300, "temperature": 0.3,
                                           "messages": [{"role": "system", "content": "Responda em portugues do Brasil, curto e direto."},
                                                        {"role": "user", "content": pergunta}]})
        resposta = r["choices"][0]["message"]["content"].strip()
    except Exception as e:  # noqa: BLE001 - mostrar erro limpo em vez de traceback (timeout, resposta malformada, etc.)
        sys.exit(f"ERRO ao falar com a IA do celular: {type(e).__name__}: {str(e)[:200]}")
    print(resposta)


if __name__ == "__main__":
    main()
