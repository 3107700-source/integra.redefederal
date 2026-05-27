"""
Extrai dados de gestão/comissões e corrige titulação via resumo.
"""
import asyncio
import re
import sqlite3
import aiohttp

from config import INSTITUICOES, HEADERS, REQUEST_TIMEOUT, REQUEST_DELAY, MAX_CONCURRENT, DB_PATH
from etl.database import DatabaseManager, clean_value


async def fetch_json(session, url, retries=3):
    for attempt in range(retries):
        try:
            async with session.get(url, headers=HEADERS, ssl=False,
                                   timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)) as resp:
                if resp.status == 429:
                    await asyncio.sleep(2)
                    continue
                if resp.status >= 400:
                    return None
                return await resp.json()
        except Exception:
            if attempt == retries - 1:
                return None
            await asyncio.sleep(REQUEST_DELAY * (attempt + 1))
    return None


PESOS_TITULACAO = {"pos_doutorado": 12, "doutorado": 10, "mestrado": 7, "especializacao": 4, "graduacao": 2}


def detect_titulacao_from_resumo(resumo):
    """Detecta maior titulação mencionada no resumo."""
    if not resumo:
        return None
    text = resumo.lower()
    if re.search(r'\b(p[oó]s[- ]?doutor|p[oó]s[- ]?doutorado)', text):
        return "pos_doutorado"
    if re.search(r'\b(doutor[ao]?|doutorado|ph\.?d)', text):
        return "doutorado"
    if re.search(r'\b(mestr[ea]|mestrado|m\.?sc)', text):
        return "mestrado"
    if re.search(r'\b(especialist[ao]|especializa[çc][aã]o|mba)', text):
        return "especializacao"
    return None


async def extract_gestao_for_professor(session, db, sigla, base_url, professor_id, slug):
    """Extrai gestão/comissões de um professor."""
    detail_url = f"{base_url}/api/portfolio/pessoa/s/{slug}"
    data = await fetch_json(session, detail_url)
    if not data or not isinstance(data, dict):
        return 0

    gestao_rows = []
    dados_gerais = data.get("dadosGerais") or {}
    atuacoes_prof = dados_gerais.get("atuacoesProfissionais") or {}
    atuacoes = atuacoes_prof.get("atuacaoProfissional") or []

    for atuacao in atuacoes:
        if not isinstance(atuacao, dict):
            continue
        inst_nome = clean_value(atuacao.get("nomeInstituicao"))

        # Direção e Administração
        for item in atuacao.get("atividadesDeDirecaoEAdministracao", []):
            if not isinstance(item, dict):
                continue
            inner = item.get("direcaoEAdministracao")
            if isinstance(inner, dict):
                inner = [inner]
            elif not isinstance(inner, list):
                inner = [item]
            for d in inner:
                if not isinstance(d, dict):
                    continue
                gestao_rows.append((
                    professor_id, sigla, slug, "direcao",
                    clean_value(d.get("cargoOuFuncao")),
                    inst_nome,
                    clean_value(d.get("nomeOrgao")),
                    clean_value(d.get("nomeUnidade")),
                    clean_value(d.get("mesInicio")),
                    clean_value(d.get("anoInicio")),
                    clean_value(d.get("mesFim")),
                    clean_value(d.get("anoFim")),
                    clean_value(d.get("flagPeriodo")),
                ))

        # Conselhos, Comissões e Consultorias
        for item in atuacao.get("atividadesDeConselhoComissaoEConsultoria", []):
            if not isinstance(item, dict):
                continue
            inner = item.get("conselhoComissaoEConsultoria")
            if isinstance(inner, dict):
                inner = [inner]
            elif not isinstance(inner, list):
                inner = [item]
            for c in inner:
                if not isinstance(c, dict):
                    continue
                gestao_rows.append((
                    professor_id, sigla, slug, "comissao",
                    clean_value(c.get("especificacao")),
                    inst_nome,
                    clean_value(c.get("nomeOrgao")),
                    clean_value(c.get("nomeUnidade")),
                    clean_value(c.get("mesInicio")),
                    clean_value(c.get("anoInicio")),
                    clean_value(c.get("mesFim")),
                    clean_value(c.get("anoFim")),
                    clean_value(c.get("flagPeriodo")),
                ))

    db.save_gestao_comissoes(gestao_rows)
    return len(gestao_rows)


async def run_extraction():
    """Extrai gestão/comissões e corrige titulação."""
    db = DatabaseManager()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 1. Corrige titulação via resumo
    print("=" * 60)
    print("  CORREÇÃO DE TITULAÇÃO VIA RESUMO")
    print("=" * 60)
    cur.execute("SELECT professor_id, slug, sigla, resumo FROM professores WHERE resumo IS NOT NULL AND resumo != ''")
    profs_with_resumo = cur.fetchall()
    print(f"Professores com resumo: {len(profs_with_resumo)}")

    corrections = 0
    for prof_id, slug, sigla, resumo in profs_with_resumo:
        nivel_resumo = detect_titulacao_from_resumo(resumo)
        if not nivel_resumo:
            continue

        # Verifica se já tem essa titulação na formacao_academica
        cur.execute("SELECT nivel FROM formacao_academica WHERE professor_id=?", (prof_id,))
        niveis_existentes = [r[0] for r in cur.fetchall()]

        peso_resumo = PESOS_TITULACAO.get(nivel_resumo, 0)
        peso_max_existente = max([PESOS_TITULACAO.get(n, 0) for n in niveis_existentes], default=0)

        if peso_resumo > peso_max_existente:
            # Insere a titulação detectada no resumo
            cur.execute("""
                INSERT INTO formacao_academica 
                (professor_id, sigla, slug_professor, nivel, nome_curso, nome_instituicao, 
                 ano_inicio, ano_conclusao, status, titulo_trabalho, nome_orientador, bolsa, agencia_financiadora)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (prof_id, sigla, slug, nivel_resumo, "(detectado via resumo)", "(detectado via resumo)",
                  None, None, "DETECTADO_RESUMO", None, None, None, None))
            corrections += 1

    conn.commit()
    print(f"Titulações corrigidas via resumo: {corrections}")

    # 2. Extrai gestão/comissões
    print(f"\n{'='*60}")
    print("  EXTRAÇÃO DE GESTÃO E COMISSÕES")
    print(f"{'='*60}")

    cur.execute("SELECT professor_id, sigla, slug FROM professores ORDER BY sigla")
    professores = cur.fetchall()
    conn.close()

    print(f"Total de professores: {len(professores)}")

    by_sigla = {}
    for prof_id, sigla, slug in professores:
        if sigla not in by_sigla:
            by_sigla[sigla] = []
        by_sigla[sigla].append((prof_id, slug))

    # Prioriza IFB
    siglas_ordered = sorted(by_sigla.keys())
    if "IFB" in siglas_ordered:
        siglas_ordered.remove("IFB")
        siglas_ordered.insert(0, "IFB")

    total_gestao = 0
    for sigla in siglas_ordered:
        if sigla not in INSTITUICOES:
            continue
        nome, base_url, uf = INSTITUICOES[sigla]
        profs = by_sigla[sigla]
        print(f"\n[{sigla}] Processando {len(profs)} professores...")

        connector = aiohttp.TCPConnector(limit=MAX_CONCURRENT)
        async with aiohttp.ClientSession(connector=connector) as session:
            sem = asyncio.Semaphore(MAX_CONCURRENT)
            processed = 0
            sigla_gestao = 0

            async def process_prof(prof_id, slug):
                nonlocal processed, sigla_gestao
                async with sem:
                    n = await extract_gestao_for_professor(session, db, sigla, base_url, prof_id, slug)
                    sigla_gestao += n
                    processed += 1
                    if processed % 100 == 0:
                        print(f"  [{sigla}] {processed}/{len(profs)}...")
                    await asyncio.sleep(REQUEST_DELAY)

            tasks = [process_prof(pid, s) for pid, s in profs]
            await asyncio.gather(*tasks)

        total_gestao += sigla_gestao
        print(f"  [{sigla}] ✅ {sigla_gestao} registros de gestão/comissões")

    print(f"\n{'='*60}")
    print(f"  Total gestão/comissões extraídas: {total_gestao}")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(run_extraction())
