#!/usr/bin/env python3
"""Robô de publicação do Instagram @rodtech.ti.

Lê posts.json, publica pela Graph API oficial da Meta os posts cuja hora já
chegou e marca cada um como publicado. Sem dependências externas.

Variáveis de ambiente:
  IG_USER_ID        id da conta do Instagram Business (ex.: 17841456073441533)
  IG_ACCESS_TOKEN   token de acesso (Secret do GitHub; nunca no código)
  GRAPH_API_VERSION versão da Graph API (padrão v25.0)
  MODO_TESTE        "1" valida token e imagens sem publicar nada
  IMAGENS_BASE_URL  URL base das imagens (padrão: raw do próprio repositório)
  POSTS_JSON        caminho do posts.json (padrão: posts.json na raiz)
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTS_JSON = os.environ.get("POSTS_JSON", os.path.join(RAIZ, "posts.json"))
GRAPH = os.environ.get("GRAPH_BASE", "https://graph.facebook.com")
VERSAO = os.environ.get("GRAPH_API_VERSION", "v25.0")
TOKEN = os.environ.get("IG_ACCESS_TOKEN", "").strip()
IG_USER = os.environ.get("IG_USER_ID", "").strip()
MODO_TESTE = os.environ.get("MODO_TESTE", "0") == "1"
REPO = os.environ.get("GITHUB_REPOSITORY", "rodolfodicastro/rodtech-midia")
BASE_IMG = os.environ.get(
    "IMAGENS_BASE_URL", f"https://raw.githubusercontent.com/{REPO}/main/"
)
# Post com mais atraso que isso não é publicado sozinho (evita post de Natal em janeiro).
ATRASO_MAXIMO = timedelta(hours=int(os.environ.get("ATRASO_MAXIMO_HORAS", "12")))


def log(msg):
    print(msg, flush=True)


def api(metodo, caminho, params=None):
    params = dict(params or {})
    params["access_token"] = TOKEN
    url = f"{GRAPH}/{VERSAO}/{caminho}"
    dados = urllib.parse.urlencode(params).encode()
    if metodo == "GET":
        req = urllib.request.Request(f"{url}?{dados.decode()}")
    else:
        req = urllib.request.Request(url, data=dados, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        corpo = e.read().decode(errors="replace")
        try:
            erro = json.loads(corpo).get("error", {})
            msg = erro.get("error_user_msg") or erro.get("message") or corpo
        except ValueError:
            msg = corpo
        raise RuntimeError(f"Graph API {e.code} em {caminho}: {msg}") from None


def esperar_container(cid, limite=180):
    """Espera o Instagram terminar de processar a mídia."""
    fim = time.time() + limite
    while time.time() < fim:
        st = api("GET", cid, {"fields": "status_code,status"})
        code = st.get("status_code")
        if code == "FINISHED":
            return
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram recusou a mídia {cid}: {st.get('status')}")
        time.sleep(3)
    raise RuntimeError(f"Tempo esgotado processando a mídia {cid}")


def url_imagem(nome):
    return nome if nome.startswith("http") else BASE_IMG + urllib.parse.quote(nome)


def checar_imagem(url):
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req, timeout=30) as r:
        tipo = r.headers.get("Content-Type", "")
        if r.status != 200 or "jpeg" not in tipo:
            raise RuntimeError(f"Imagem inválida ({r.status}, {tipo}): {url}")


def publicar(post):
    imagens = [url_imagem(n) for n in post["imagens"]]
    legenda = post.get("legenda", "")
    if len(imagens) == 1:
        c = api("POST", f"{IG_USER}/media", {"image_url": imagens[0], "caption": legenda})
        esperar_container(c["id"])
        criacao = c["id"]
    else:
        if not 2 <= len(imagens) <= 10:
            raise RuntimeError("Carrossel precisa de 2 a 10 imagens")
        filhos = []
        for u in imagens:
            c = api("POST", f"{IG_USER}/media", {"image_url": u, "is_carousel_item": "true"})
            filhos.append(c["id"])
        for f in filhos:
            esperar_container(f)
        c = api(
            "POST",
            f"{IG_USER}/media",
            {"media_type": "CAROUSEL", "children": ",".join(filhos), "caption": legenda},
        )
        esperar_container(c["id"])
        criacao = c["id"]
    pub = api("POST", f"{IG_USER}/media_publish", {"creation_id": criacao})
    return pub["id"]


def salvar(dados):
    with open(POSTS_JSON, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main():
    with open(POSTS_JSON, encoding="utf-8") as f:
        dados = json.load(f)

    if not TOKEN or not IG_USER:
        log("Falta IG_ACCESS_TOKEN ou IG_USER_ID nos Secrets do GitHub. Nada feito.")
        return 1 if MODO_TESTE else 0

    agora = datetime.now(timezone.utc)
    pendentes = [p for p in dados["posts"] if p.get("status") == "pendente"]

    if MODO_TESTE:
        conta = api("GET", IG_USER, {"fields": "username"})
        log(f"Token OK. Conta: @{conta.get('username')}")
        for p in pendentes:
            for n in p["imagens"]:
                checar_imagem(url_imagem(n))
            log(f"OK  {p['data_hora']}  {p['id']}  ({len(p['imagens'])} imagem(ns))")
        log(f"Modo teste: {len(pendentes)} post(s) pendentes conferidos. Nada foi publicado.")
        return 0

    if not dados.get("robo_ativo", False):
        log("robo_ativo = false no posts.json. Nada publicado.")
        return 0

    falhas = 0
    for p in pendentes:
        quando = datetime.fromisoformat(p["data_hora"])
        if quando > agora:
            continue
        if agora - quando > ATRASO_MAXIMO:
            p["status"] = "atrasado"
            p["erro"] = f"Hora passou há mais de {ATRASO_MAXIMO}; não publicado automaticamente."
            log(f"ATRASADO  {p['id']}")
            salvar(dados)
            falhas += 1
            continue
        log(f"Publicando {p['id']} ...")
        try:
            media_id = publicar(p)
        except Exception as e:  # noqa: BLE001
            p["status"] = "erro"
            p["erro"] = str(e)
            log(f"ERRO  {p['id']}: {e}")
            falhas += 1
        else:
            p["status"] = "publicado"
            p["media_id"] = media_id
            p["publicado_em"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            p.pop("erro", None)
            log(f"PUBLICADO  {p['id']}  media_id={media_id}")
        salvar(dados)
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
