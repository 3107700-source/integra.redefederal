"""
Módulo de extração (Extract) - Consome a API interna do Portal Integra.
Suporta extração de TODA a rede federal ou instituições individuais.
Extrai: professores, publicações, TCCs, artigos, projetos e detalhes do currículo.
"""

import asyncio
import json
import os
import time
from datetime import datetime
from typing import Optional

import aiohttp
from tqdm import tqdm

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    INSTITUICOES, RAW_DIR, HEADERS, REQUEST_TIMEOUT,
    REQUEST_DELAY, MAX_RETRIES, MAX_CONCURRENT, PAGE_SIZE,
    AREAS_CNPQ, DATA_DIR
)
from etl.database import DatabaseManager, clean_value


def log(msg):
    """Log com timestamp."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def classify_area_cnpq(text: str) -> str:
    """Classifica texto em grande área CNPq."""
    if not text or not text.strip():
        return "Não Classificado"
    full_text = text.lower()
    scores = {}
    for area, keywords in AREAS_CNPQ.items():
        score = sum(full_text.count(kw.lower()) for kw in keywords)
        scores[area] = score
    if max(scores.values()) > 0:
        return max(scores, key=scores.get)
    return "Não Classificado"


class IntegraExtractor:
    """Extrator assíncrono para o Portal Integra de qualquer IF."""

    def __init__(self, db_manager: DatabaseManager = None):
        self.db = db_manager or DatabaseManager()

    async def _fetch_json(self, session, url, params=None, retries=MAX_RETRIES):
        """Faz requisição HTTP com retry."""
        for attempt in range(retries):
            try:
                async with session.get(url, params=params, headers=HEADERS,
                                       ssl=False, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)) as resp:
                    if resp.status == 429:
                        delay = float(resp.headers.get("Retry-After", 2))
                        await asyncio.sleep(delay)
                        continue
                    if resp.status >= 400:
                        return None
                    return await resp.json()
            except Exception as e:
                if attempt == retries - 1:
                    return None
                await asyncio.sleep(REQUEST_DELAY * (attempt + 1))
        return None

    async def fetch_professores(self, sigla: str, base_url: str, uf: str, session):
        """Busca todos os professores de uma instituição."""
        list_url = f"{base_url}/api/portfolio/pessoa/data"
        professores = []
        start = 0

        data = await self._fetch_json(session, list_url, {"start": start, "length": PAGE_SIZE})
        if not data or len(data) < 2:
            return []

        total = data[0].get("total", 0) if isinstance(data[0], dict) else 0
        if data[1]:
            professores.extend(data[1])

        log(f"[{sigla}] Total de pessoas no portal: {total}")

        while len(professores) < total:
            start += PAGE_SIZE
            data = await self._fetch_json(session, list_url, {"start": start, "length": PAGE_SIZE})
            if not data or len(data) < 2 or not data[1]:
                break
            professores.extend(data[1])
            await asyncio.sleep(0.05)

        # Processa e salva
        processed = []
        for p in professores:
            if not isinstance(p, dict):
                continue
            slug = p.get("slug")
            if not slug:
                continue

            resumo = clean_value(p.get("textoResumoCvRh", ""))
            temas_list = p.get("palavrasChave") or []
            if isinstance(temas_list, list) and temas_list:
                if isinstance(temas_list[0], dict):
                    temas = "; ".join([kw.get("text", "") for kw in temas_list if kw.get("text")])
                else:
                    temas = "; ".join([str(kw) for kw in temas_list if kw])
            else:
                temas = ""

            classification_text = f"{resumo or ''} {temas}"
            area = classify_area_cnpq(classification_text)

            processed.append({
                "nome": p.get("nome"),
                "campus": p.get("campusNome"),
                "cargo": p.get("cargo"),
                "slug": slug,
                "url_final": f"{base_url}/portfolio/pessoas/{slug}",
                "lattes_id": p.get("lattesId"),
                "resumo": resumo,
                "temas": temas,
                "area_cnpq": area,
                "uf": uf,
            })

        self.db.save_professores(sigla, processed)
        log(f"[{sigla}] {len(processed)} professores salvos no banco.")
        return processed

    async def fetch_publicacoes(self, sigla: str, base_url: str, session):
        """Busca todas as publicações de uma instituição."""
        criteria_url = f"{base_url}/api/portfolio/producao/criteria"
        data_url = f"{base_url}/api/portfolio/producao/data"

        # Busca tipos disponíveis
        criteria = await self._fetch_json(session, criteria_url)
        tipos = []
        if criteria and len(criteria) >= 2:
            tipos = criteria[1] if isinstance(criteria[1], list) else []

        all_pubs = []
        for tipo in tipos:
            start = 0
            data = await self._fetch_json(session, data_url, {"start": start, "length": PAGE_SIZE, "tipo": tipo})
            if not data or len(data) < 2:
                continue

            total = data[0].get("total", 0) if isinstance(data[0], dict) else 0
            batch = data[1] or []
            all_pubs.extend(batch)

            max_items = min(total, 5000)
            while len(batch) < max_items and start + PAGE_SIZE < max_items:
                start += PAGE_SIZE
                data = await self._fetch_json(session, data_url, {"start": start, "length": PAGE_SIZE, "tipo": tipo})
                if not data or len(data) < 2 or not data[1]:
                    break
                all_pubs.extend(data[1])
                batch.extend(data[1])
                await asyncio.sleep(0.05)

        # Salva publicações
        rows = []
        for pub in all_pubs:
            if not isinstance(pub, dict):
                continue
            campus = pub.get("campus")
            campus_nome = ""
            if isinstance(campus, dict):
                campus_nome = campus.get("nome", "")
            elif isinstance(campus, str):
                campus_nome = campus

            professor_id = self.db.get_professor_id(sigla, pub.get("slug", ""))
            rows.append((
                professor_id,
                sigla,
                clean_value(pub.get("slug")),
                clean_value(pub.get("titulo")),
                clean_value(pub.get("tipo")),
                clean_value(pub.get("tipoProducao")),
                clean_value(pub.get("nomeCompleto")),
                pub.get("ano"),
                clean_value(campus_nome),
                clean_value(pub.get("lattesId")),
                clean_value(pub.get("fonte")),
            ))

        self.db.save_publicacoes(rows)
        log(f"[{sigla}] {len(rows)} publicações salvas.")
        return all_pubs

    async def fetch_detalhes_professor(self, sigla: str, base_url: str, uf: str,
                                        professor: dict, session):
        """Busca detalhes completos do currículo de um professor (TCCs, artigos, projetos, etc.)."""
        slug = professor.get("slug")
        detail_url = f"{base_url}/api/portfolio/pessoa/s/{slug}"

        data = await self._fetch_json(session, detail_url)
        if not data or not isinstance(data, dict):
            return

        professor_id = self.db.get_professor_id(sigla, slug)
        if professor_id is None:
            return

        nome_professor = clean_value(professor.get("nome"))
        tccs = []
        artigos = []
        projetos = []
        detalhes_curriculo = []

        # ─── TCCs (orientações concluídas) ───
        outra_producao = data.get("outraProducao") or {}
        if isinstance(outra_producao, dict):
            for item in outra_producao.get("orientacoesConcluidas", []):
                if not isinstance(item, dict):
                    continue
                for trabalho in item.get("outrasOrientacoesConcluidas", []):
                    if not isinstance(trabalho, dict):
                        continue
                    dados_basicos = trabalho.get("dadosBasicosDeOutrasOrientacoesConcluidas") or {}
                    detalhamento = trabalho.get("detalhamentoDeOutrasOrientacoesConcluidas") or {}
                    natureza = (dados_basicos.get("natureza") or "").upper()

                    # Registra todas as orientações como detalhe do currículo
                    detalhes_curriculo.append((
                        professor_id, sigla, slug, "orientacao_concluida",
                        clean_value(natureza),
                        clean_value(dados_basicos.get("titulo")),
                        clean_value(detalhamento.get("nomeDoOrientado")),
                        clean_value(dados_basicos.get("ano")),
                        None,
                        clean_value(detalhamento.get("nomeDaInstituicao")),
                        None,
                    ))

                    if "TRABALHO_DE_CONCLUSAO" not in natureza:
                        continue

                    autores = clean_value(detalhamento.get("nomeDoOrientado"))
                    if nome_professor:
                        autores = (autores + ", " if autores else "") + f"{nome_professor} (Orientador/a)"

                    palavras = trabalho.get("palavrasChave") or {}
                    info_add = trabalho.get("informacoesAdicionais") or {}

                    tccs.append((
                        professor_id, slug, nome_professor, sigla,
                        clean_value(detalhamento.get("nomeDaInstituicao")),
                        uf,
                        clean_value(professor.get("campus")),
                        clean_value(dados_basicos.get("ano")),
                        clean_value(detalhamento.get("nomeDoCurso")),
                        autores,
                        clean_value(dados_basicos.get("titulo") or detalhamento.get("titulo")),
                        clean_value(info_add.get("descricaoInformacoesAdicionais")),
                        clean_value(palavras.get("palavrasChaves")),
                    ))

            # Orientações em andamento
            for item in outra_producao.get("orientacoesEmAndamento", []):
                if not isinstance(item, dict):
                    continue
                for trabalho in item.get("outrasOrientacoesEmAndamento", []):
                    if not isinstance(trabalho, dict):
                        continue
                    dados_basicos = trabalho.get("dadosBasicosDeOutrasOrientacoesEmAndamento") or {}
                    detalhamento = trabalho.get("detalhamentoDeOutrasOrientacoesEmAndamento") or {}
                    detalhes_curriculo.append((
                        professor_id, sigla, slug, "orientacao_andamento",
                        clean_value((dados_basicos.get("natureza") or "").upper()),
                        clean_value(dados_basicos.get("titulo")),
                        clean_value(detalhamento.get("nomeDoOrientado")),
                        clean_value(dados_basicos.get("ano")),
                        None,
                        clean_value(detalhamento.get("nomeDaInstituicao")),
                        None,
                    ))

        # ─── Artigos publicados ───
        prodbib = data.get("producaoBibliografica") or {}
        if isinstance(prodbib, dict):
            for bloco in prodbib.get("artigosPublicados", []):
                if not isinstance(bloco, dict):
                    continue
                for art in bloco.get("artigoPublicado", []):
                    if not isinstance(art, dict):
                        continue
                    dados = art.get("dadosBasicosDoArtigo") or {}
                    titulo_art = dados.get("tituloDoArtigo") or dados.get("titulo")
                    ano_art = dados.get("anoDoArtigo") or dados.get("ano")
                    palavras = art.get("palavrasChave") or {}
                    detalhamento_art = art.get("detalhamentoDoArtigo") or {}

                    if titulo_art:
                        artigos.append((
                            professor_id, slug, nome_professor, sigla,
                            clean_value(ano_art),
                            clean_value(titulo_art),
                            clean_value(detalhamento_art.get("tituloDoPeriodicoOuRevista")),
                            clean_value(dados.get("doi")),
                            clean_value(palavras.get("palavrasChaves")),
                        ))

        # ─── Projetos de pesquisa ───
        dados_gerais = data.get("dadosGerais") or {}
        atuacoes_prof = dados_gerais.get("atuacoesProfissionais") or {}
        atuacoes = atuacoes_prof.get("atuacaoProfissional") or []

        for atuacao in atuacoes:
            if not isinstance(atuacao, dict):
                continue

            # Registra atuações profissionais como detalhe
            detalhes_curriculo.append((
                professor_id, sigla, slug, "atuacao_profissional",
                clean_value(atuacao.get("tipoVinculo")),
                clean_value(atuacao.get("nomeInstituicao")),
                None,
                clean_value(atuacao.get("anoInicio")),
                clean_value(atuacao.get("anoFim")),
                clean_value(atuacao.get("nomeInstituicao")),
                None,
            ))

            for atividade in atuacao.get("atividadesDeParticipacaoEmProjeto", []):
                if not isinstance(atividade, dict):
                    continue
                for participacao in atividade.get("participacaoEmProjeto", []):
                    if not isinstance(participacao, dict):
                        continue
                    for proj in participacao.get("projetoDePesquisa", []):
                        if not isinstance(proj, dict):
                            continue
                        titulo_proj = proj.get("nomeDoProjeto") or proj.get("nomeDoProjetoIngles")
                        descricao = proj.get("descricaoDoProjeto") or proj.get("descricaoDoProjetoIngles")
                        natureza = proj.get("natureza")

                        # Período
                        ano_inicio = clean_value(participacao.get("anoInicio") or proj.get("anoInicio"))
                        ano_fim = clean_value(participacao.get("anoFim") or proj.get("anoFim"))
                        mes_inicio = clean_value(participacao.get("mesInicio"))
                        mes_fim = clean_value(participacao.get("mesFim"))
                        data_inicio = f"{ano_inicio}-{int(mes_inicio):02d}" if ano_inicio and mes_inicio and mes_inicio.isdigit() else ano_inicio
                        data_fim = f"{ano_fim}-{int(mes_fim):02d}" if ano_fim and mes_fim and mes_fim.isdigit() else ano_fim

                        # Equipe
                        equipe = []
                        equipe_obj = proj.get("equipeDoProjeto") or {}
                        for integrante in (equipe_obj.get("integrantesDoProjeto") or []):
                            if not isinstance(integrante, dict):
                                continue
                            nome_int = integrante.get("nomeParaCitacao") or integrante.get("nomeCompleto")
                            if nome_int:
                                if str(integrante.get("flagResponsavel", "")).upper() in ("SIM", "S", "TRUE", "1"):
                                    nome_int = f"{nome_int} (Responsável)"
                                equipe.append(nome_int)

                        # Financiadores
                        financiadores = []
                        for fin in (proj.get("financiadoresDoProjeto") or []):
                            if isinstance(fin, dict):
                                nome_fin = fin.get("nomeInstituicao") or fin.get("nome")
                                if nome_fin:
                                    financiadores.append(nome_fin)

                        if titulo_proj:
                            projetos.append((
                                professor_id, slug, nome_professor, sigla,
                                clean_value(titulo_proj),
                                clean_value(descricao),
                                clean_value(natureza),
                                "; ".join(equipe) if equipe else None,
                                "; ".join(financiadores) if financiadores else None,
                                data_inicio,
                                data_fim,
                            ))

            # Atividades de ensino (tempo de sala de aula)
            for atividade in atuacao.get("atividadesDeEnsino", []):
                if not isinstance(atividade, dict):
                    continue
                detalhes_curriculo.append((
                    professor_id, sigla, slug, "ensino",
                    clean_value(atividade.get("tipoEnsino")),
                    clean_value(atividade.get("disciplina")),
                    None,
                    clean_value(atividade.get("anoInicio")),
                    clean_value(atividade.get("anoFim")),
                    clean_value(atuacao.get("nomeInstituicao")),
                    None,
                ))

            # Atividades de extensão
            for atividade in atuacao.get("atividadesDeExtensao", []):
                if not isinstance(atividade, dict):
                    continue
                detalhes_curriculo.append((
                    professor_id, sigla, slug, "extensao",
                    None,
                    clean_value(atividade.get("titulo")),
                    None,
                    clean_value(atividade.get("anoInicio")),
                    clean_value(atividade.get("anoFim")),
                    clean_value(atuacao.get("nomeInstituicao")),
                    None,
                ))

        # ─── Bancas ───
        bancas = data.get("dadosComplementares", {}).get("participacaoEmBanca", {}) if isinstance(data.get("dadosComplementares"), dict) else {}
        if isinstance(bancas, dict):
            for tipo_banca, lista in bancas.items():
                if not isinstance(lista, list):
                    continue
                for banca in lista:
                    if not isinstance(banca, dict):
                        continue
                    for item in banca.values():
                        if not isinstance(item, list):
                            continue
                        for b in item:
                            if not isinstance(b, dict):
                                continue
                            dados_b = {}
                            for k, v in b.items():
                                if "dadosBasicos" in k.lower() and isinstance(v, dict):
                                    dados_b = v
                                    break
                            detalhes_curriculo.append((
                                professor_id, sigla, slug, "banca",
                                clean_value(tipo_banca),
                                clean_value(dados_b.get("titulo")),
                                None,
                                clean_value(dados_b.get("ano")),
                                None,
                                None,
                                None,
                            ))

        # ─── Formação Acadêmica (estruturada) ───
        formacoes = []
        dados_gerais = data.get("dadosGerais") or {}
        formacao_titulacao = dados_gerais.get("formacaoAcademicaTitulacao") or {}

        if isinstance(formacao_titulacao, dict):
            # Pós-Doutorado
            for item in (formacao_titulacao.get("posDoutorado") or []):
                if not isinstance(item, dict):
                    continue
                formacoes.append((
                    professor_id, sigla, slug, "pos_doutorado",
                    clean_value(item.get("nomeCurso") or item.get("nomeAreaConcentracao")),
                    clean_value(item.get("nomeInstituicao")),
                    clean_value(item.get("anoDeInicio")),
                    clean_value(item.get("anoDeConclusao")),
                    clean_value(item.get("statusDoCurso")),
                    clean_value(item.get("tituloDoTrabalho")),
                    clean_value(item.get("nomeDoOrientador")),
                    clean_value(item.get("flagBolsa")),
                    clean_value(item.get("nomeAgencia")),
                ))

            # Doutorado
            for item in (formacao_titulacao.get("doutorado") or []):
                if not isinstance(item, dict):
                    continue
                formacoes.append((
                    professor_id, sigla, slug, "doutorado",
                    clean_value(item.get("nomeCurso")),
                    clean_value(item.get("nomeInstituicao")),
                    clean_value(item.get("anoDeInicio")),
                    clean_value(item.get("anoDeConclusao")),
                    clean_value(item.get("statusDoCurso")),
                    clean_value(item.get("tituloDaDissertacaoTese") or item.get("tituloDoTrabalho")),
                    clean_value(item.get("nomeCompletoDoOrientador") or item.get("nomeDoOrientador")),
                    clean_value(item.get("flagBolsa")),
                    clean_value(item.get("nomeAgencia")),
                ))

            # Mestrado
            for item in (formacao_titulacao.get("mestrados") or []):
                if not isinstance(item, dict):
                    continue
                formacoes.append((
                    professor_id, sigla, slug, "mestrado",
                    clean_value(item.get("nomeCurso")),
                    clean_value(item.get("nomeInstituicao")),
                    clean_value(item.get("anoDeInicio")),
                    clean_value(item.get("anoDeConclusao")),
                    clean_value(item.get("statusDoCurso")),
                    clean_value(item.get("tituloDaDissertacaoTese") or item.get("tituloDoTrabalho")),
                    clean_value(item.get("nomeCompletoDoOrientador") or item.get("nomeDoOrientador")),
                    clean_value(item.get("flagBolsa")),
                    clean_value(item.get("nomeAgencia")),
                ))

            # Especialização
            for item in (formacao_titulacao.get("especializacoes") or []):
                if not isinstance(item, dict):
                    continue
                formacoes.append((
                    professor_id, sigla, slug, "especializacao",
                    clean_value(item.get("nomeCurso")),
                    clean_value(item.get("nomeInstituicao")),
                    clean_value(item.get("anoDeInicio")),
                    clean_value(item.get("anoDeConclusao")),
                    clean_value(item.get("statusDoCurso")),
                    clean_value(item.get("tituloDaMonografia")),
                    clean_value(item.get("nomeDoOrientador")),
                    clean_value(item.get("flagBolsa")),
                    clean_value(item.get("nomeAgencia")),
                ))

            # Graduação
            for item in (formacao_titulacao.get("graduacoes") or []):
                if not isinstance(item, dict):
                    continue
                formacoes.append((
                    professor_id, sigla, slug, "graduacao",
                    clean_value(item.get("nomeCurso")),
                    clean_value(item.get("nomeInstituicao")),
                    clean_value(item.get("anoDeInicio")),
                    clean_value(item.get("anoDeConclusao")),
                    clean_value(item.get("statusDoCurso")),
                    clean_value(item.get("tituloDoTrabalhoDeConclusaoDeCurso")),
                    clean_value(item.get("nomeDoOrientador")),
                    clean_value(item.get("flagBolsa")),
                    clean_value(item.get("nomeAgencia")),
                ))

        # ─── Bancas (estruturadas) ───
        bancas_estruturadas = []
        dados_comp = data.get("dadosComplementares") or {}
        if isinstance(dados_comp, dict):
            # Bancas de trabalhos de conclusão
            bancas_tc = dados_comp.get("participacaoEmBancaTrabalhosConclusao") or {}
            if isinstance(bancas_tc, dict):
                for tipo_banca_key, lista_bancas in bancas_tc.items():
                    if not isinstance(lista_bancas, list):
                        continue
                    for banca_item in lista_bancas:
                        if not isinstance(banca_item, dict):
                            continue
                        # Busca dados básicos e detalhamento
                        dados_basicos = {}
                        detalhamento = {}
                        for k, v in banca_item.items():
                            if "dadosBasicos" in k and isinstance(v, dict):
                                dados_basicos = v
                            elif "detalhamento" in k and isinstance(v, dict):
                                detalhamento = v

                        if dados_basicos:
                            bancas_estruturadas.append((
                                professor_id, sigla, slug,
                                clean_value(tipo_banca_key),
                                clean_value(dados_basicos.get("natureza")),
                                clean_value(dados_basicos.get("titulo")),
                                clean_value(dados_basicos.get("ano")),
                                clean_value(detalhamento.get("nomeDoCandidato")),
                                clean_value(detalhamento.get("nomeInstituicao")),
                                clean_value(detalhamento.get("nomeCurso")),
                            ))

            # Bancas julgadoras (concursos, etc.)
            bancas_julg = dados_comp.get("participacaoEmBancaJulgadora") or {}
            if isinstance(bancas_julg, dict):
                for tipo_banca_key, lista_bancas in bancas_julg.items():
                    if not isinstance(lista_bancas, list):
                        continue
                    for banca_item in lista_bancas:
                        if not isinstance(banca_item, dict):
                            continue
                        dados_basicos = {}
                        detalhamento = {}
                        for k, v in banca_item.items():
                            if "dadosBasicos" in k and isinstance(v, dict):
                                dados_basicos = v
                            elif "detalhamento" in k and isinstance(v, dict):
                                detalhamento = v

                        if dados_basicos:
                            bancas_estruturadas.append((
                                professor_id, sigla, slug,
                                clean_value(tipo_banca_key),
                                clean_value(dados_basicos.get("natureza")),
                                clean_value(dados_basicos.get("titulo")),
                                clean_value(dados_basicos.get("ano")),
                                None,
                                clean_value(detalhamento.get("nomeInstituicao")),
                                None,
                            ))

        # Salva tudo
        self.db.save_tccs(tccs)
        self.db.save_artigos(artigos)
        self.db.save_projetos(projetos)
        self.db.save_curriculo_detalhes(detalhes_curriculo)
        self.db.save_formacao_academica(formacoes)
        self.db.save_bancas(bancas_estruturadas)

    async def run_institution(self, sigla: str):
        """Executa extração completa para uma instituição."""
        if sigla not in INSTITUICOES:
            log(f"Instituição '{sigla}' não encontrada na lista.")
            return

        nome, base_url, uf = INSTITUICOES[sigla]
        log(f"{'='*60}")
        log(f"  EXTRAÇÃO: {sigla} - {nome}")
        log(f"  URL: {base_url}")
        log(f"{'='*60}")

        connector = aiohttp.TCPConnector(limit=MAX_CONCURRENT)
        async with aiohttp.ClientSession(connector=connector) as session:
            # 1. Busca professores
            professores = await self.fetch_professores(sigla, base_url, uf, session)

            # 2. Busca publicações
            await self.fetch_publicacoes(sigla, base_url, session)

            # 3. Busca detalhes de cada professor (TCCs, artigos, projetos)
            log(f"[{sigla}] Buscando detalhes de {len(professores)} professores...")
            sem = asyncio.Semaphore(MAX_CONCURRENT)

            async def fetch_with_sem(prof):
                async with sem:
                    await self.fetch_detalhes_professor(sigla, base_url, uf, prof, session)
                    await asyncio.sleep(REQUEST_DELAY)

            tasks = [fetch_with_sem(p) for p in professores]
            for i, task in enumerate(asyncio.as_completed(tasks)):
                await task
                if (i + 1) % 50 == 0:
                    log(f"[{sigla}] Detalhes: {i+1}/{len(professores)}")

        log(f"[{sigla}] ✅ Extração concluída!")

    async def run_all(self, siglas: list = None):
        """Executa extração para múltiplas instituições."""
        target_siglas = siglas or list(INSTITUICOES.keys())
        log(f"Iniciando extração para {len(target_siglas)} instituições...")

        for sigla in target_siglas:
            try:
                await self.run_institution(sigla)
            except Exception as e:
                log(f"[{sigla}] ERRO: {e}")
                continue

        log("✅ Extração de todas as instituições concluída!")

    def run(self, siglas: list = None):
        """Ponto de entrada síncrono."""
        asyncio.run(self.run_all(siglas))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Extrator Integra - Rede Federal")
    parser.add_argument("--sigla", type=str, default=None,
                        help="Sigla da instituição (ex: IFB). Se não informado, extrai apenas IFB.")
    parser.add_argument("--todas", action="store_true",
                        help="Extrai dados de TODAS as instituições da rede federal.")
    args = parser.parse_args()

    extractor = IntegraExtractor()
    if args.todas:
        extractor.run()
    elif args.sigla:
        extractor.run([args.sigla.upper()])
    else:
        # Padrão: apenas IFB
        extractor.run(["IFB"])
