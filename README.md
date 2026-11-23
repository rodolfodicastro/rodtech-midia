# Robô de posts do Instagram @rodtech.ti

Publica sozinho, pela API oficial da Meta, os posts agendados no `posts.json`.
Roda no GitHub Actions a cada 30 minutos, de graça.

## Como agendar um post

1. Suba as imagens (JPEG, formato 4:5 ou quadrado) na pasta `midia/`.
2. Adicione um item em `posts.json`:

```json
{
  "id": "2027-01-05_nome-do-post",
  "data_hora": "2027-01-05T13:00:00-03:00",
  "imagens": ["midia/2027-01-05_nome-do-post_1.jpg", "midia/2027-01-05_nome-do-post_2.jpg"],
  "legenda": "Texto do post\n#hashtags",
  "status": "pendente"
}
```

Uma imagem vira post simples; de 2 a 10 viram carrossel.

## Status

- `pendente`: espera a hora para sair.
- `publicado`: saiu (o `media_id` fica registrado).
- `erro`: deu problema (o motivo fica em `erro`). Corrija e volte para `pendente`.
- `atrasado`: a hora passou há mais de 12 h sem publicar; não sai sozinho.

`robo_ativo: false` desliga todas as publicações.

## Configuração (uma vez)

Secrets do repositório (Settings → Secrets and variables → Actions):

- `IG_USER_ID`: id da conta do Instagram Business.
- `IG_ACCESS_TOKEN`: token de Página sem expiração, com `instagram_basic` e `instagram_content_publish`.

Para testar sem publicar: aba **Actions → Publicar no Instagram → Run workflow** com "Modo teste" marcado.

Se uma publicação falhar, o GitHub manda e-mail avisando.
