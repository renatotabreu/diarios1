import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import urllib3

# Ignora avisos de SSL (necessário para o site do DOE)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

# --- CONFIGURAÇÕES ---
EMAIL_REMETENTE = os.getenv('EMAIL_REMETENTE')
SENHA_REMETENTE = os.getenv('SENHA_REMETENTE')
EMAIL_DESTINATARIO = os.getenv('EMAIL_DESTINATARIO')

# URLs dos portais
URL_DOE = "https://doe.seplag.ce.gov.br/diario-completo"
# --- ALTERAÇÃO AQUI: NOVA URL DA API DA ALCE ---
URL_ALCE_API = "https://doalece.al.ce.gov.br/api/publico/publicacoes/ultimas"
BASE_URL_ALCE_DOWNLOAD = "https://doalece.al.ce.gov.br"

def buscar_diario_doe(data_alvo):
    """Busca o Diário Oficial do Estado (DOE) para uma data específica."""
    try:
        print(f"Buscando no Diário Oficial do Estado (DOE) para a data {data_alvo.strftime('%d/%m/%Y')}...")
        response = requests.get(URL_DOE, headers={'User-Agent': 'Mozilla/5.0'}, verify=False, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        data_str = data_alvo.strftime('%d/%m/%Y')
        cards = soup.find_all('div', class_='card-daily')
        for card in cards:
            data_tag = card.find('p')
            if data_tag and data_str in data_tag.get_text():
                link_tag = card.find('a', class_='btn-secondary')
                if link_tag and link_tag.get('href'):
                    return link_tag.get('href')
    except requests.exceptions.RequestException as e:
        print(f"Erro ao acessar o site do DOE: {e}")
    return None

def buscar_diario_alce(data_alvo):
    """Busca o Diário Oficial da ALCE via API para uma data específica."""
    try:
        print(f"Buscando no Diário da ALCE via API para a data {data_alvo.strftime('%Y-%m-%d')}...")
        response = requests.get(URL_ALCE_API, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
        response.raise_for_status()
        
        publicacoes = response.json() # A resposta da API é em formato JSON
        data_str = data_alvo.strftime('%Y-%m-%d')

        for pub in publicacoes:
            # A data na API vem no formato "2025-10-07T..."
            if pub.get('dataPublicacao', '').startswith(data_str):
                link_download_parcial = pub.get('linkDownload')
                if link_download_parcial:
                    # Monta a URL completa para o download
                    return f"{BASE_URL_ALCE_DOWNLOAD}{link_download_parcial}"
    except requests.exceptions.RequestException as e:
        print(f"Erro ao acessar a API da ALCE: {e}")
    except requests.exceptions.JSONDecodeError:
        print("Erro: A resposta da API da ALCE não é um JSON válido.")
    return None

def buscar_e_enviar_diarios():
    print("Iniciando busca por diários...")
    hoje = datetime.now()
    ontem = hoje - timedelta(days=1)
    
    pdfs_encontrados = {}

    # --- Busca no DOE (hoje, com fallback para ontem) ---
    url_pdf_doe = buscar_diario_doe(hoje)
    if not url_pdf_doe:
        print("Não encontrou o diário do DOE de hoje, tentando o de ontem...")
        url_pdf_doe = buscar_diario_doe(ontem)
    
    if url_pdf_doe:
        print(f"PDF do DOE encontrado: {url_pdf_doe}")
        pdfs_encontrados['DOE'] = url_pdf_doe
    else:
        print("Nenhum Diário Oficial do Estado (hoje ou ontem) encontrado.")

    # --- Busca na ALCE (hoje, com fallback para ontem) ---
    url_pdf_alce = buscar_diario_alce(hoje)
    if not url_pdf_alce:
        print("Não encontrou o diário da ALCE de hoje, tentando o de ontem...")
        url_pdf_alce = buscar_diario_alce(ontem)

    if url_pdf_alce:
        print(f"PDF da ALCE encontrado: {url_pdf_alce}")
        pdfs_encontrados['ALCE'] = url_pdf_alce
    else:
        print("Nenhum Diário da Assembleia (hoje ou ontem) encontrado.")

    if not pdfs_encontrados:
        print("Nenhum diário encontrado nas buscas. Encerrando.")
        return

    # --- Código de download e envio de e-mail (sem alterações) ---
    arquivos_para_enviar = []
    conteudo_email = "Olá,\n\nSegue(m) em anexo o(s) diário(s) oficial(is) mais recente(s) encontrado(s).\n\n"
    for nome, url in pdfs_encontrados.items():
        try:
            print(f"Baixando {nome} de {url}...")
            response_pdf = requests.get(url, stream=True, verify=False, timeout=60) # Timeout maior para downloads
            response_pdf.raise_for_status()
            pdf_bytes = response_pdf.content
            nome_arquivo_data = url.split('/')[-2] # Pega o ID da publicação como nome
            nome_arquivo = f"{nome}_{nome_arquivo_data}.pdf"
            arquivos_para_enviar.append({'nome': nome_arquivo, 'conteudo': pdf_bytes})
        except Exception as e:
            print(f"Falha ao baixar ou processar o PDF de {nome}: {e}")
    
    if arquivos_para_enviar:
        enviar_email(arquivos_para_enviar, conteudo_email)
    else:
        print("Nenhum PDF pôde ser baixado. Nenhum e-mail será enviado.")

def enviar_email(anexos, corpo_email):
    print("Preparando para enviar email...")
    msg = MIMEMultipart()
    msg['From'] = EMAIL_REMETENTE
    msg['To'] = EMAIL_DESTINATARIO
    msg['Subject'] = f"Diários Oficiais do Ceará - {datetime.now().strftime('%d/%m/%Y')}"
    msg.attach(MIMEText(corpo_email, 'plain'))
    for anexo in anexos:
        part = MIMEApplication(anexo['conteudo'], Name=anexo['nome'])
        part['Content-Disposition'] = f'attachment; filename="{anexo["nome"]}"'
        msg.attach(part)
        print(f"Anexando {anexo['nome']}...")
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_REMETENTE, SENHA_REMETENTE)
        server.sendmail(EMAIL_REMETENTE, EMAIL_DESTINATARIO, msg.as_string())
        server.quit()
        print("Email enviado com sucesso!")
    except Exception as e:
        print(f"Erro ao enviar o email: {e}")

if __name__ == '__main__':
    buscar_e_enviar_diarios()
