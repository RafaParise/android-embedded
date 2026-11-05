"""settings.json e QWEN.md do kit do Qwen Code no celular (scripts/celular-kit).

Erro real de 31/10/2026 no Termux do A12: o Qwen Code mostrou "Response truncated due to token limits" e "This conversation approached the input
token limit for codigo" porque os combos de NUVEM estavam com janela de 32768 tokens e saida de 4096 (o /effort max gasta a saida em raciocinio e o
CLAUDE.md do projeto enche a janela). Os membros reais dos combos aceitam 128 mil tokens ou mais; estes testes impedem a volta dos numeros pequenos.
"""
import json
import pathlib

RAIZ = pathlib.Path(__file__).resolve().parent.parent.parent
KIT = RAIZ / "scripts" / "celular-kit"
JANELA_MENOR_MEMBRO_DOS_COMBOS = 128_000  # nemotron / muse / gemma nos combos codigo, auditoria e rapido (catalogo do OmniRoute, 31/10)


def provedores():
    dados = json.loads((KIT / "settings.json").read_text(encoding="utf-8"))
    return {p["id"]: p for p in dados["modelProviders"]["openai"]}


def test_settings_e_json_valido_com_os_provedores_esperados():
    ids = set(provedores())
    assert {"codigo", "auditoria", "rapido", "llama3.2-32k", "qwen2.5-coder-32k", "qwen"} <= ids


def test_combos_de_nuvem_tem_janela_e_saida_grandes():
    for nome, saida_minima in (("codigo", 16384), ("auditoria", 16384), ("rapido", 8192)):
        g = provedores()[nome]["generationConfig"]
        janela, saida = g["contextWindowSize"], g["samplingParams"]["max_tokens"]
        assert janela >= 100_000, f"{nome}: janela de {janela} tokens enche com o CLAUDE.md e o prompt do Qwen Code (erro de 31/10)"
        assert janela < JANELA_MENOR_MEMBRO_DOS_COMBOS, f"{nome}: janela acima do menor modelo do combo ({JANELA_MENOR_MEMBRO_DOS_COMBOS}) faz o modelo recusar"
        assert saida >= saida_minima, f"{nome}: max_tokens {saida} corta a resposta quando o modelo raciocina (erro de 31/10)"
        assert saida < janela // 2, f"{nome}: a saida nao pode comer a janela inteira"


def test_rotulos_da_nuvem_dizem_que_o_ia_liga_a_ponte_e_nao_mandam_abrir_na_mao():
    # o rotulo aparece no rodape do Qwen Code; "precisa da chave e da ponte 20128" fazia parecer que faltava algo (31/10)
    nomes = {n: provedores()[n]["name"] for n in ("codigo", "auditoria", "rapido")}
    assert "o comando ia liga a ponte 20128 sozinho" in nomes["codigo"]
    for n, texto in nomes.items():
        assert "precisa da chave" not in texto and "nuvem gratis" in texto, (n, texto)


def test_modelos_pequenos_continuam_com_janela_pequena():
    # o modelo do celular so tem 8 mil tokens de janela de verdade; o Llama e o Qwen2.5-Coder do PC rodam com num_ctx 32768
    assert provedores()["qwen"]["generationConfig"]["contextWindowSize"] == 8192
    for nome in ("llama3.2-32k", "qwen2.5-coder-32k"):
        assert provedores()[nome]["generationConfig"]["contextWindowSize"] == 32768


def test_todo_provedor_pede_chave_pelo_nome_da_variavel_e_nunca_traz_chave():
    texto = (KIT / "settings.json").read_text(encoding="utf-8")
    for p in provedores().values():
        assert p["envKey"] in {"OMNIROUTE_API_KEY", "OLLAMA_API_KEY", "LLAMACPP_API_KEY"}
    assert "Bearer" not in texto and "sk-" not in texto and "nvapi-" not in texto


def test_qwen_md_avisa_que_contexto_cheio_corta_a_resposta_e_que_arquivo_grande_se_le_por_trechos():
    texto = (KIT / "QWEN.md").read_text(encoding="utf-8")
    assert "Response truncated" in texto and "NUNCA leia inteiros" in texto
    assert "rg -n" in texto and "/clear" in texto


# --- travas dos .ps1 do kit (achados powershell-0/4/10/11/12 de 02/11): conferidas no texto, pois a suite roda no Linux sem PowerShell ---
def _ps1(nome):
    return (KIT.parent / nome).read_text(encoding="utf-8")


def test_kit_celular_nao_tira_da_varredura_literal_com_cara_de_segredo():
    t = _ps1("kit-celular.ps1")
    assert "MatchEvaluator" in t and "Find-Segredo $m.Value" in t  # o trecho com cara de segredo fica no texto varrido
    assert "$_ -replace '(?>(?:process" not in t  # a limpeza cega de antes


def test_kit_celular_escolhe_a_versao_do_plugin_pelo_numero():
    t = _ps1("kit-celular.ps1")
    assert "Sort-Object { [version]$_.Name }" in t and "Sort-Object Name | Select-Object -Last 1" not in t


def test_kit_celular_limpa_o_destino_confere_o_codigo_final_e_exige_o_claude_md():
    t = _ps1("kit-celular.ps1")
    assert "rm -r -f --" in t
    assert "a conferencia final no Termux falhou" in t
    assert "-Obrigatorio" in t


def test_termux_copia_confere_o_tar_e_so_aceita_destino_permitido():
    t = _ps1("termux.ps1")
    assert "$codTar" in t and "--force-local -cf" in t and "| `\"$ssh`\"" not in t  # tar a parte, sem "tar | ssh"
    assert "^[~A-Za-z0-9_./-]+$" in t


def test_termux_fechar_pontes_e_pontes_nao_mentem():
    t = _ps1("termux.ps1")
    assert "ATENCAO: a remocao NAO fechou a ponte" in t
    assert "ollama-sem-resposta" in t and "| sed s/^/modelo-no-pc:/ ||" not in t


def test_ponte_pc_manda_o_token_pela_entrada_padrao_e_nao_por_argumento():
    t = _ps1("ponte-pc.ps1")
    assert "-LerEntrada" in t and "base64 -d | bash" not in t
