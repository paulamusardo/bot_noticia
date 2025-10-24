import os
import requests
from bs4 import BeautifulSoup
import gspread
import gspread.utils
from oauth2client.service_account import ServiceAccountCredentials
from google import genai
import pandas as pd
import feedparser
from datetime import datetime
import time

# --- 1. CONFIGURAÇÕES OBRIGATÓRIAS ---
# Cole aqui a chave que você gerou no Google AI Studio
GOOGLE_AI_API_KEY = 'AIzaSyCOoRvA6LuKo3PmN7U-5a_P8D13srN--dY' # (Mantenha a sua chave que já estava)

# O nome EXATO da sua planilha no Google Drive
GOOGLE_SHEET_NAME = 'BOT Notícias'

# O nome do arquivo JSON que você baixou (Caminho corrigido)
script_dir = os.path.dirname(os.path.abspath(__file__))
GOOGLE_CREDENTIALS_FILE = os.path.join(script_dir, 'credentials.json')
# ----------------------------------------

# Configura a API do Gemini
try:
    #genai.configure(api_key=GOOGLE_AI_API_KEY)
    clientAi = genai.Client(api_key=GOOGLE_AI_API_KEY)
    #model = genai.GenerativeModel('gemini')
    print("API do Gemini configurada.")
except Exception as e:
    print(f"Erro ao configurar a API do Gemini: {e}")
    exit()

# Configura a API do Google Sheets
try:
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDENTIALS_FILE, scope)
    client = gspread.authorize(creds)
    sheet = client.open(GOOGLE_SHEET_NAME).sheet1
    print(f"Conectado à planilha: {GOOGLE_SHEET_NAME}")
except Exception as e:
    print(f"Erro ao conectar na Planilha: {e}")
    print("Verifique se o 'GOOGLE_SHEET_NAME' está correto e se você compartilhou a planilha com o e-mail do 'credentials.json'.")
    exit()

# --- 2. MÓDULO DE RESUMO (O "AGENTE") ---
def obter_resumo_ia(titulo, portal):
    """
    Usa a API do Gemini para gerar o resumo de 5 linhas.
    """
    # Evita chamar a API se o título estiver vazio
    if not titulo or not titulo.strip():
        print("Título vazio, pulando resumo.")
        return ""
        
    print(f"Gerando resumo para: {titulo[:30]}... ({portal})")
    # Este prompt é otimizado para a IA focar apenas na tarefa
    prompt = f"Você é um assistente de resumo jornalístico. Resuma a seguinte notícia em no máximo 5 linhas, com tom jornalístico.\n\nTítulo: {titulo}\nPortal: {portal}\n\nResumo:"
    
    try:
        response = clientAi.models.generate_content(
            model="gemini-2.5-flash", # (Mantido '2.5' como no seu original)
            contents=prompt,
        )

        resumo = response.text.strip().replace("\n", " ") # Remove quebras de linha
        return resumo
    except Exception as e:
        print(f"Erro ao gerar resumo: {e}")
        return "" # Retorna vazio se falhar

# --- 3. MÓDULO DE COLETA (Sem alterações) ---

def coletar_via_rss(url_feed, nome_portal):
    """
    Coleta notícias dos feeds RSS que funcionam.
    """
    print(f"Coletando RSS de: {nome_portal}")
    noticias = []
    feed = feedparser.parse(url_feed)
    
    # Pega apenas os 10 mais recentes
    for entry in feed.entries[:10]:
        noticias.append({
            'timestamp': entry.get('published', datetime.now().isoformat()),
            'portal': nome_portal,
            'título': entry.get('title', 'Sem título').strip(),
            'url': entry.get('link', ''),
            'editoria': entry.get('category', ''),
            'sinal_de_popularidade': 'N/A (RSS)',
            'resumo': '' # Será preenchido pelo robô
        })
    return noticias

def coletar_via_scraper_correio_povo():
    """
    Coleta notícias do Correio do Povo usando BeautifulSoup.
    """
    print("Coletando via scraper: Correio do Povo")
    url = 'https://www.correiodopovo.com.br/ultimas'
    noticias = []
    try:
        # Simula ser um navegador para evitar bloqueios
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        artigos = soup.find_all('a', class_='item-link', limit=10)
        for artigo in artigos:
            titulo_tag = artigo.find('h3', class_='title')
            if titulo_tag:
                titulo = titulo_tag.text.strip()
                link = artigo['href']
                if not link.startswith('http'):
                    link = 'https://www.correiodopovo.com.br' + link
                
                noticias.append({
                    'timestamp': datetime.now().isoformat(),
                    'portal': 'Correio do Povo',
                    'título': titulo,
                    'url': link,
                    'editoria': '',
                    'sinal_de_popularidade': 'N/A (Scraper)',
                    'resumo': ''
                })
    except Exception as e:
        print(f"Erro ao raspar Correio do Povo: {e}")
    return noticias

def coletar_via_scraper_portal_arauto():
    """
    Coleta notícias do Portal Arauto (Santa Cruz do Sul) usando BeautifulSoup.
    """
    print("Coletando via scraper: Portal Arauto")
    url = 'https://portalarauto.com.br/ultimas-noticias'
    noticias = []
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        artigos = soup.find_all('div', class_='post-item-destaque-content', limit=10)
        for artigo in artigos:
            titulo_tag = artigo.find('h2', class_='post-item-destaque-title')
            link_tag = artigo.find('a')
            if titulo_tag and link_tag:
                titulo = titulo_tag.text.strip()
                link = link_tag['href']
                
                noticias.append({
                    'timestamp': datetime.now().isoformat(),
                    'portal': 'Portal Arauto',
                    'título': titulo,
                    'url': link,
                    'editoria': '',
                    'sinal_de_popularidade': 'N/A (Scraper)',
                    'resumo': ''
                })
    except Exception as e:
        print(f"Erro ao raspar Portal Arauto: {e}")
    return noticias


# --- 4. MÓDULO PRINCIPAL (ORQUESTRAÇÃO) ---

# (NOVO) Determina a função correta de conversão de A1
# Versões mais novas do gspread (v4+) usam 'cell_to_a1'
# Versões mais antigas (v3.x) usam 'rowcol_to_a1'
try:
    a1_converter_func = gspread.utils.cell_to_a1
    print("Usando 'gspread.utils.cell_to_a1' (gspread v4+)")
except AttributeError:
    try:
        a1_converter_func = gspread.utils.rowcol_to_a1
        print("Usando 'gspread.utils.rowcol_to_a1' (gspread v3.x)")
    except AttributeError:
        print("ERRO CRÍTICO: Não foi possível encontrar 'cell_to_a1' ou 'rowcol_to_a1' em gspread.utils.")
        print("Por favor, atualize sua biblioteca gspread: pip install --upgrade gspread")
        exit()
        
def main():
    print("--- Iniciando Robô Coletor de Notícias ---")
    
    # --- ETAPA 1: CARREGAR DADOS EXISTENTES (PARA EVITAR DUPLICATAS) ---
    try:
        dados_existentes = sheet.get_all_records()
        df_existente = pd.DataFrame(dados_existentes)
        # Cria um "set" (lista de itens únicos) com todas as URLs que já estão na planilha
        if not df_existente.empty:
            urls_existentes = set(df_existente['url'])
        else:
            urls_existentes = set()
        print(f"Encontradas {len(urls_existentes)} URLs existentes na planilha (Passo 1).")
    except Exception as e:
        print(f"Planilha vazia ou erro ao ler: {e}. Começando do zero.")
        urls_existentes = set()


    # --- ETAPA 2: (NOVO) VERIFICAR E PREENCHER RESUMOS FALTANTES (Make.com) ---
    print("\n--- Verificando resumos faltantes (Tarefas do Make)... ---")
    try:
        # Pega todos os valores (incluindo cabeçalhos)
        all_data = sheet.get_all_values()
        if len(all_data) < 2:
            print("Planilha vazia ou contém apenas cabeçalho. Pulando verificação de resumos.")
        else:
            headers = all_data[0]
            
            # Encontra as colunas pelo nome (para o código não quebrar se você mudar a ordem)
            try:
                col_idx_resumo = headers.index('resumo')
                col_idx_titulo = headers.index('título')
                col_idx_portal = headers.index('portal')
            except ValueError as e:
                print(f"Erro: Não foi possível encontrar uma coluna obrigatória ('resumo', 'título' ou 'portal') na planilha: {e}")
                print("Verifique se os nomes das colunas na Planilha Google estão corretos.")
                exit() # Não podemos continuar se as colunas não existem

            updates_em_lote = []
            
            # Itera pelas linhas, começando da linha 2 (índice 1, pois 0 é o cabeçalho)
            # 'start=2' porque as linhas da planilha são 1-indexadas
            for row_num, row_data in enumerate(all_data[1:], start=2):
                
                # Verifica se a coluna de resumo está vazia
                # (Usa 'col_idx_resumo' pois 'row_data' é uma lista 0-indexada)
                
                # Proteção extra: verifica se a linha tem colunas suficientes
                if len(row_data) > col_idx_resumo and not row_data[col_idx_resumo].strip():
                    titulo = row_data[col_idx_titulo] if len(row_data) > col_idx_titulo else ""
                    portal = row_data[col_idx_portal] if len(row_data) > col_idx_portal else ""
                    
                    print(f"Resumo faltante encontrado na Linha {row_num}.")
                    
                    # Adiciona pausa para não sobrecarregar a API
                    time.sleep(1) 
                    resumo_novo = obter_resumo_ia(titulo, portal)
                    
                    if resumo_novo:
                        # *** ESTA É A LINHA CORRIGIDA ***
                        # Usa a função 'a1_converter_func' que definimos fora do main()
                        cell_label = a1_converter_func(row_num, col_idx_resumo + 1)
                        
                        # Adiciona à lista para atualização em lote
                        updates_em_lote.append({
                            'range': cell_label,
                            'values': [[resumo_novo]]
                        })
                        print(f"Resumo para linha {row_num} preparado para update.")
                    else:
                        print(f"Falha ao gerar resumo para linha {row_num}. Será tentado na próxima vez.")
                elif len(row_data) <= col_idx_resumo:
                     print(f"Aviso: Linha {row_num} parece estar mal formatada ou incompleta, pulando.")

            # Se houver resumos para atualizar, faz tudo de uma vez
            if updates_em_lote:
                print(f"\nAtualizando {len(updates_em_lote)} resumos faltantes na planilha...")
                sheet.batch_update(updates_em_lote, value_input_option='USER_ENTERED')
                print("Resumos faltantes atualizados com sucesso!")
            else:
                print("Nenhum resumo faltante encontrado.")
    
    except Exception as e:
        print(f"Erro inesperado ao verificar resumos faltantes: {e}")


    # --- ETAPA 3: (EXISTENTE) COLETAR NOVAS NOTÍCIAS ---
    print("\n--- Iniciando coleta de novas notícias... ---")
    
    # Define a lista de portais para monitorar
    lista_de_fontes_rss = [
        ('G1 RS', 'http://g1.globo.com/dynamo/rs/rio-grande-do-sul/rss2.xml'),
        ('GZH', 'https://gauchazh.clicrbs.com.br/rss/ultimas-noticias.xml'),
        ('Jornal do Comércio', 'https://www.jornaldocomercio.com/rss/ultimas-noticias.xml'),
        ('Rádio Guaíba', 'https://guaiba.com.br/feed/'),
        ('Diário Gaúcho', 'https://diariogaucho.clicrbs.com.br/rss/ultimas-noticias.xml'),
        ('Portal Arauto', 'https://rss.app/feeds/mXPFLRQnFJgGLwiP.xml')
    ]
    
    noticias_finais = []

    # 3.1. Coleta de RSS
    for nome, url in lista_de_fontes_rss:
        noticias_finais.extend(coletar_via_rss(url, nome))

    # 3.2. Coleta de Scrapers (sites sem RSS)
    noticias_finais.extend(coletar_via_scraper_correio_povo())
    noticias_finais.extend(coletar_via_scraper_portal_arauto())
    
    print(f"--- Coleta finalizada. Total de {len(noticias_finais)} notícias encontradas. Verificando duplicatas... ---")

    # --- ETAPA 4: (EXISTENTE) PROCESSAR E ADICIONAR NOVAS NOTÍCIAS ---
    linhas_para_adicionar = []
    for noticia in noticias_finais:
        # A MÁGICA ESTÁ AQUI: Se a URL da notícia NÃO ESTIVER na lista de URLs existentes...
        if noticia['url'] not in urls_existentes:
            
            print(f"Notícia NOVA encontrada: {noticia['título'][:30]}...")
            # Gera o Resumo com a IA
            # (Adiciona uma pausa de 1 segundo para não sobrecarregar a API do Gemini)
            time.sleep(1) 
            resumo = obter_resumo_ia(noticia['título'], noticia['portal'])
            
            # Monta a linha para a planilha (seguindo o seu "Esquema de dados")
            linha = [
                noticia['timestamp'],
                noticia['portal'],
                noticia['título'],
                noticia['url'],
                noticia['editoria'],
                noticia['sinal_de_popularidade'],
                resumo # A IA preenche a última coluna!
            ]
            linhas_para_adicionar.append(linha)
            urls_existentes.add(noticia['url']) # Adiciona na lista para não duplicar na mesma rodada
        
    # Salva no Google Sheets
    if linhas_para_adicionar:
        print(f"\n--- Adicionando {len(linhas_para_adicionar)} novas notícias na planilha... ---")
        # Adiciona todas as novas linhas de uma vez
        sheet.append_rows(linhas_para_adicionar, value_input_option='USER_ENTERED')
        print("Planilha atualizada com sucesso!")
    else:
        print("\n--- Nenhuma notícia nova encontrada para adicionar. ---")

# --- Ponto de partida do script ---
if __name__ == "__main__":
    main()