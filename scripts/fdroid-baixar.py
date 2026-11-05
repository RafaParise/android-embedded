#!/usr/bin/env python3
"""Baixa APKs da F-Droid conferindo a cadeia de confianca do repositorio e, com --instalar, instala por ADB.

  python -I scripts/fdroid-baixar.py --pasta <DIR_PROPRIO_E_VAZIO> [--instalar] [pacote ...]

Cadeia: (1) o index-v1.jar precisa estar assinado pelo certificado cuja impressao SHA-256 e a oficial
(f-droid.org/en/docs/Release_Channels_and_Signing_Keys/), com assinatura valida (OpenSSL) e digests do JAR batendo;
(2) o SHA-256 de cada APK baixado precisa ser igual ao do indice assinado. A F-Droid assina cada app com uma chave
propria, entao o certificado do APK so e exibido (para comparar em atualizacoes futuras), nao usado como prova.
Sem pacotes usa a lista FOSS do script original. Escolhe a variante com arm64-v8a ou sem codigo nativo.
"""
import argparse
import base64
import hashlib
import json
import pathlib
import re
import struct
import subprocess
import sys
import urllib.request
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

CHAVE_FDROID = "43238d512c1e5eb2d6569f4a3afbf5523418b82e0a3ed1552770abb9a9c9ccab"
OPENSSL = r"C:\Program Files\Git\usr\bin\openssl.exe"
PADRAO = ["net.sourceforge.opencamera", "app.organicmaps", "org.fossify.gallery", "org.fossify.filemanager",
          "org.videolan.vlc", "com.gitlab.mudlej.MjPdfReader", "helium314.keyboard", "com.junkfood.seal"]
UA = {"User-Agent": "Mozilla/5.0 (fdroid-baixar.py; uso pessoal)"}
SDK_DO_APARELHO = 31  # Android 12


def http(url, timeout=120):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout)


def baixar_arquivo(url, destino):
    with http(url) as r, open(destino, "wb") as f:
        while True:
            bloco = r.read(1 << 20)
            if not bloco:
                break
            f.write(bloco)


def openssl(*args):
    r = subprocess.run([OPENSSL, *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout + r.stderr).strip()


def digest_b64(dados, alg):
    return base64.b64encode(hashlib.new(alg, dados).digest()).decode()


def indice_verificado(pasta):
    jar = pasta / "index-v1.jar"
    if not jar.exists():
        baixar_arquivo("https://f-droid.org/repo/index-v1.jar", jar)
    with zipfile.ZipFile(jar) as z:
        nomes = z.namelist()
        rsa = next(n for n in nomes if n.startswith("META-INF/") and n.upper().endswith((".RSA", ".DSA", ".EC")))
        sf = rsa.rsplit(".", 1)[0] + ".SF"
        d_rsa, d_sf, d_mf, d_json = z.read(rsa), z.read(sf), z.read("META-INF/MANIFEST.MF"), z.read("index-v1.json")
    (pasta / "idx.rsa").write_bytes(d_rsa)
    (pasta / "idx.sf").write_bytes(d_sf)
    rc, saida = openssl("smime", "-verify", "-binary", "-inform", "DER", "-in", str(pasta / "idx.rsa"),
                        "-content", str(pasta / "idx.sf"), "-noverify", "-out", str(pasta / "idx.out"))
    if rc != 0:
        sys.exit(f"INDICE REPROVADO: assinatura do JAR invalida ({saida[:120]})")
    openssl("pkcs7", "-inform", "DER", "-in", str(pasta / "idx.rsa"), "-print_certs", "-out", str(pasta / "idx.pem"))
    # um certificado so: o smime -noverify aceita quem assinou com QUALQUER certificado embutido, e o x509 abaixo so olha o primeiro.
    # Com dois, um indice falso assinado pelo segundo passaria mostrando o oficial da F-Droid em primeiro (revisao de 02/11).
    if (pasta / "idx.pem").read_text(encoding="utf-8", errors="replace").count("-----BEGIN CERTIFICATE-----") != 1:
        sys.exit("INDICE REPROVADO: o JAR nao traz exatamente um certificado")
    _, fp = openssl("x509", "-in", str(pasta / "idx.pem"), "-noout", "-fingerprint", "-sha256")
    fp = fp.split("=", 1)[-1].replace(":", "").lower()
    if fp != CHAVE_FDROID:
        sys.exit(f"INDICE REPROVADO: certificado {fp[:16]}... nao e o oficial da F-Droid")
    sf_txt = d_sf.decode("utf-8", "replace").replace("\r\n ", "").replace("\n ", "")
    mf_txt = d_mf.decode("utf-8", "replace").replace("\r\n ", "").replace("\n ", "")
    m = re.search(r"(SHA-256|SHA1)-Digest-Manifest:\s*(\S+)", sf_txt)
    if not m or m.group(2) != digest_b64(d_mf, "sha256" if m.group(1) == "SHA-256" else "sha1"):
        sys.exit("INDICE REPROVADO: digest do MANIFEST.MF nao confere com o .SF")
    m = re.search(r"Name: index-v1\.json\s+(SHA-256|SHA1)-Digest:\s*(\S+)", mf_txt)
    if not m or m.group(2) != digest_b64(d_json, "sha256" if m.group(1) == "SHA-256" else "sha1"):
        sys.exit("INDICE REPROVADO: digest do index-v1.json nao confere com o MANIFEST.MF")
    print(f"indice F-Droid verificado: assinado pela chave oficial {CHAVE_FDROID[:8]}...{CHAVE_FDROID[-8:]}, "
          f"{len(d_json) / 1e6:.0f} MB", flush=True)
    return json.loads(d_json)


def u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def certificados(dados):
    """DER dos certificados do bloco de assinatura v2/v3 do APK (so para exibir a impressao digital)."""
    i = dados.rfind(b"PK\x05\x06")
    if i < 0:
        return []
    cd = struct.unpack_from("<I", dados, i + 16)[0]
    if dados[cd - 16:cd] != b"APK Sig Block 42":
        return []
    tam = struct.unpack_from("<Q", dados, cd - 24)[0]
    pos, fim, saida = cd - tam, cd - 24, []
    while pos < fim:
        ln = struct.unpack_from("<Q", dados, pos)[0]
        pid = struct.unpack_from("<I", dados, pos + 8)[0]
        if pid in (0x7109871a, 0xf05368c0, 0x1b93ad61):
            val = dados[pos + 12:pos + 8 + ln]
            n, o = u32(val, 0), 4
            while o < 4 + n:
                sl = u32(val, o)
                signer = val[o + 4:o + 4 + sl]
                o += 4 + sl
                sd = signer[4:4 + u32(signer, 0)]
                co = 4 + u32(sd, 0)
                blob = sd[co + 4:co + 4 + u32(sd, co)]
                p = 0
                while p < len(blob):
                    c = u32(blob, p)
                    saida.append(blob[p + 4:p + 4 + c])
                    p += 4 + c
        pos += 8 + ln
    return saida


def escolher(indice, pkg):
    app = next((a for a in indice["apps"] if a["packageName"] == pkg), None)
    versoes = indice["packages"].get(pkg)
    if not app or not versoes:
        raise RuntimeError("pacote fora do indice")
    sug = next((v for v in versoes if str(v["versionCode"]) == str(app.get("suggestedVersionCode"))), versoes[0])
    iguais = sorted((v for v in versoes if v["versionName"] == sug["versionName"]), key=lambda v: -v["versionCode"])
    for v in iguais:
        nativo = v.get("nativecode") or []
        if (not nativo or "arm64-v8a" in nativo) and int(v.get("minSdkVersion", 1)) <= SDK_DO_APARELHO:
            return v
    raise RuntimeError("nenhuma variante com arm64-v8a e minSdk <= 31")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pasta", required=True)
    ap.add_argument("--instalar", action="store_true")
    ap.add_argument("pacotes", nargs="*")
    a = ap.parse_args()
    pasta = pathlib.Path(a.pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    indice = indice_verificado(pasta)

    falhas = 0
    for pkg in (a.pacotes or PADRAO):
        try:
            v = escolher(indice, pkg)
            apk = pasta / v["apkName"]
            if not apk.exists() or hashlib.sha256(apk.read_bytes()).hexdigest() != v["hash"]:
                baixar_arquivo(f"https://f-droid.org/repo/{v['apkName']}", apk)
            dados = apk.read_bytes()
            h = hashlib.sha256(dados).hexdigest()
            ok = v.get("hashType", "sha256") == "sha256" and h == v["hash"]
            certs = sorted({hashlib.sha256(c).hexdigest()[:16] for c in certificados(dados)})
            print(f"{'ok    ' if ok else 'FALHOU'} {pkg:<34} {v['versionName']:<22} {len(dados) / 1e6:6.1f} MB "
                  f"hash={'confere com o indice' if ok else 'DIFERENTE do indice'} cert={','.join(certs)}", flush=True)
            if not ok:
                falhas += 1
                continue
            if a.instalar:
                r = subprocess.run(["adb", "install", "-r", str(apk)], capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", timeout=300)
                saida = (r.stdout + r.stderr).strip().splitlines()
                print(f"       instalar: {saida[-1] if saida else '(sem saida)'}", flush=True)
                falhas += 0 if "Success" in r.stdout else 1
        except Exception as e:  # noqa: BLE001 - mostrar e seguir para o proximo pacote
            falhas += 1
            print(f"FALHOU {pkg:<34} {type(e).__name__}: {str(e)[:100]}", flush=True)
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
