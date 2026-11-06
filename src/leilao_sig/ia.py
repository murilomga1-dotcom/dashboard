"""Chamada à API do Claude: edital + planilha -> ExtracaoEdital (JSON validado)."""

from __future__ import annotations

import json
import logging
from functools import lru_cache

import anthropic

from leilao_sig import config
from leilao_sig.modelos import ExtracaoEdital
from leilao_sig.planilha import Bem
from leilao_sig.util import fmt_valor

log = logging.getLogger(__name__)

SERVICO_CHAVE = "LeilaoSIG"  # nome no Cofre de Credenciais do Windows
BETA_FALLBACK = "server-side-fallback-2026-07-01"


class ErroIA(Exception):
    pass


@lru_cache
def prompt_sistema() -> str:
    p = config.PASTA_PROMPTS
    return (
        (p / "sistema.md").read_text(encoding="utf-8")
        .replace("{{CABECALHO_FRASES}}", (p / "cabecalho-frases.md").read_text(encoding="utf-8"))
        .replace("{{LOTES}}", (p / "lotes.md").read_text(encoding="utf-8"))
    )


def chave_api() -> str | None:
    """Chave guardada no cofre do sistema (keyring). Sem ela, o SDK usa ANTHROPIC_API_KEY."""
    try:
        import keyring

        return keyring.get_password(SERVICO_CHAVE, "anthropic_api_key")
    except Exception:  # keyring ausente ou sem backend (Linux sem cofre)
        return None


def salvar_chave_api(chave: str) -> None:
    import keyring

    keyring.set_password(SERVICO_CHAVE, "anthropic_api_key", chave)


def cliente() -> anthropic.Anthropic:
    chave = chave_api()
    return anthropic.Anthropic(api_key=chave) if chave else anthropic.Anthropic()


def _planilha_para_texto(bens: list[Bem]) -> str:
    linhas = [
        {
            "processo": b.processo,
            "vistoria": b.vistoria,
            "tipo": b.tipo,
            "avaliacao": fmt_valor(b.avaliacao) if b.avaliacao is not None else None,
            "lance_minimo": fmt_valor(b.lance_minimo) if b.lance_minimo is not None else None,
            "descricao": b.descricao,
        }
        for b in bens
    ]
    return json.dumps(linhas, ensure_ascii=False, indent=1)


def extrair(texto_edital: str, bens: list[Bem], suspeitas: tuple[str, ...] = (), client: anthropic.Anthropic | None = None) -> tuple[ExtracaoEdital, dict]:
    """Devolve (extração validada, uso de tokens)."""
    cfg = config.app()
    client = client or cliente()
    aviso = ""
    if suspeitas:
        aviso = (
            "\n\nAtenção: o texto contém termos típicos de editais fora do padrão "
            f"({', '.join(suspeitas)}). Classifique `tipo_edital` com cuidado."
        )
    conteudo = (
        f"<edital>\n{texto_edital}\n</edital>\n\n"
        f"<planilha_bens>\n{_planilha_para_texto(bens)}\n</planilha_bens>{aviso}"
    )
    try:
        with client.beta.messages.stream(
            model=cfg["modelo"],
            max_tokens=64000,
            system=[{"type": "text", "text": prompt_sistema(), "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": conteudo}],
            thinking={"type": "adaptive"},
            output_config={"effort": cfg.get("esforco", "high")},
            output_format=ExtracaoEdital,
            betas=[BETA_FALLBACK],
            fallbacks="default",
        ) as stream:
            msg = stream.get_final_message()
    except anthropic.AuthenticationError as e:
        raise ErroIA("Chave da API do Claude inválida ou ausente. Configure em Configurações.") from e
    except anthropic.RateLimitError as e:
        raise ErroIA("Limite de uso da API atingido. Tente de novo em alguns minutos.") from e
    except anthropic.APIStatusError as e:
        raise ErroIA(f"Erro da API do Claude ({e.status_code}): {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise ErroIA("Sem conexão com a API do Claude. Verifique a internet.") from e

    if msg.stop_reason == "refusal":
        raise ErroIA("A IA recusou processar este edital. Cadastre manualmente.")
    if msg.stop_reason == "max_tokens":
        raise ErroIA("A resposta da IA foi cortada (edital grande demais). Divida o edital.")
    uso = {
        "modelo": msg.model,
        "entrada": msg.usage.input_tokens,
        "saida": msg.usage.output_tokens,
        "cache_lido": getattr(msg.usage, "cache_read_input_tokens", 0) or 0,
    }
    log.info("IA: %s", uso)
    for bloco in msg.content:
        if bloco.type == "text":
            parsed = getattr(bloco, "parsed_output", None)
            if isinstance(parsed, ExtracaoEdital):
                return parsed, uso
            try:
                return ExtracaoEdital.model_validate_json(bloco.text), uso
            except Exception as e:
                raise ErroIA(f"Resposta da IA fora do formato esperado: {e}") from e
    raise ErroIA("A IA não devolveu conteúdo.")
