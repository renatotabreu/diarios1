import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from datetime import datetime
import os
from dotenv import load_dotenv
import PyPDF2
import io
import urllib3 # Adicionado para gerenciar avisos de SSL

# --- ALTERAÇÃO AQUI ---
# Adicionado para desabilitar o aviso de "certificado não verificado" que aparecerá
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# --- CONFIGURAÇÕES ---
EMAIL_REMETENTE = os.getenv('EMAIL_REMETENTE')
SENHA_REMETENTE = os.getenv('SENHA_REMETENTE')
EMAIL_DESTINATARIO = os.getenv('EMAIL_DESTINATARIO')
PALAVRAS_CHAVE = []
URL_DOE = 'https://www.cge.ce.gov.br/diario-oficial-do-estado/'
URL_ALCE = 'https://www.al.ce.gov.br/index.php/diario-da-assembleia'

def buscar_e_enviar_diarios():
    print("Iniciando busca por diários...")
    hoje = datetime.now()
    pdfs_encontrados = {}

    # --- 1. Busca no Diário Oficial do Estado (DOE) ---
    try:
        print(f"Buscando no Diário Oficial do Estado (DOE)...")
        # --- ALTERAÇÃO AQUI ---
        # Adicionado verify=False para ignorar o erro de SSL
        response_doe = requests.get(URL_DOE, headers={'User-Agent': 'Mozilla/5.0'}, verify=False)
        response_doe.raise_for_status()
        
        soup_doe = BeautifulSoup(response_doe.text, 'html.parser')
        
        data_str_doe = hoje.strftime('%d/%m/%Y')
        print(f"Procurando por links com a data no texto: {data_str_doe}")
        link_doe = soup_doe.find('a', string=lambda text: text and data_str_doe in text)
        
        if link_doe and link_doe.get('href').endswith('.pdf'):
            url_pdf_doe = link_doe.get('href')
            print(f"PDF do DOE encontrado: {url_pdf_doe}")
            pdfs_encontrados['DOE'] = url_pdf_doe
        else:
            print("Nenhum Diário Oficial do Estado encontrado para hoje.")

    except requests.exceptions.RequestException as e:
        print(f"Erro ao acessar o site do DOE: {e}")

    # --- 2. Busca no Diário da Assembleia Legislativa (ALCE) ---
    try:
        print(f"Buscando no Diário da Assembleia Legislativa (ALCE)...")
        response_alce = requests.get(URL_ALCE, headers={'User-Agent': 'Mozilla/5.0'})
        response_alce.raise_for_status()
        soup_alce = BeautifulSoup(response_alce.text, 'html.parser')

        # --- ALTERAÇÃO AQUI ---
        # Lógica de busca atualizada para se adaptar ao novo layout da ALCE
        meses = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']
        data_str_alce = f"{hoje.day:02d} de {meses[hoje.month-1]} de {hoje.year}"
        print(f"Procurando por links com o texto contendo: '{data_str_alce}'")
        
        link_alce_encontrado = None
        # Procura todos os links na página
        for link in soup_alce.find_all('a'):
            # Verifica se o texto do link contém a data de hoje e se o link aponta para um PDF
            if data_str_alce.lower() in link.get_text().lower() and link.get('href').endswith('.pdf'):
                link_alce_encontrado = link
                break # Para no primeiro link que encontrar
        
        if link_alce_encontrado:
            url_pdf_alce = requests.compat.urljoin(URL_ALCE, link_alce_encontrado.get('href'))
            print(f"PDF da ALCE encontrado: {url_pdf_alce}")
            pdfs_encontrados['ALCE'] = url_pdf_alce
        else:
            print("Nenhum Diário da Assembleia encontrado para hoje.")

    except requests.exceptions.RequestException as e:
        print(f"Erro ao acessar o site da ALCE: {e}")

    if not pdfs_encontrados:
        print("Nenhum diário encontrado hoje. Encerrando.")
        return

    # O resto do código continua igual
    arquivos_para_enviar = []
    conteudo_email = "Olá,\n\nSegue(m) em anexo o(s) diário(s) oficial(is) encontrado(s) hoje.\n\n"
    for nome, url in pdfs_encontrados.items():
        try:
            print(f"Baixando {nome} de {url}...")
            # Adicionado verify=False aqui também para downloads de sites com problema de SSL
            response_pdf = requests.get(url, stream=True, verify=False)
            response_pdf.raise_for_status()
            pdf_bytes = response_pdf.content
            nome_arquivo = f"{nome}_{hoje.strftime('%Y-%m-%d')}.pdf"
            arquivos_para_enviar.append({'nome': nome_arquivo, 'conteudo': pdf_bytes})
        except Exception as e:
            print(f"Falha ao baixar ou processar o PDF de {nome}: {e}")
    if arquivos_para_enviar:
        enviar_email(arquivos_para_enviar, conteudo_email)
    else:
        print("Nenhum PDF correspondeu aos filtros. Nenhum e-mail será enviado.")

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
