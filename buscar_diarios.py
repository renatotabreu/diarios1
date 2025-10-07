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

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# --- CONFIGURAÇÕES ---
# Email de onde os alertas serão enviados (use um email de aplicativo, não sua senha principal)
EMAIL_REMETENTE = os.getenv('EMAIL_REMETENTE')
SENHA_REMETENTE = os.getenv('SENHA_REMETENTE')

# Email que receberá os diários
EMAIL_DESTINATARIO = os.getenv('EMAIL_DESTINATARIO')

# Palavras-chave para buscar dentro dos PDFs (deixe a lista vazia para não filtrar)
# Exemplo: PALAVRAS_CHAVE = ['nomeação', 'licitação', 'edital']
PALAVRAS_CHAVE = []

# --- URLS DOS DIÁRIOS ---
URL_DOE = 'https://www.cge.ce.gov.br/diario-oficial-do-estado/'
URL_ALCE = 'https://doalece.al.ce.gov.br/publico/ultimas-edicoes'

def buscar_e_enviar_diarios():
    """Função principal que orquestra todo o processo."""
    print("Iniciando busca por diários...")
    hoje = datetime.now()
    
    # Dicionário para armazenar os PDFs encontrados
    pdfs_encontrados = {}

    # --- 1. Busca no Diário Oficial do Estado (DOE) ---
    try:
        print(f"Buscando no Diário Oficial do Estado (DOE)...")
        response_doe = requests.get(URL_DOE, headers={'User-Agent': 'Mozilla/5.0'})
        response_doe.raise_for_status() # Lança um erro se a requisição falhar
        
        soup_doe = BeautifulSoup(response_doe.text, 'html.parser')
        
        # Lógica para encontrar o link do DOE. Esta parte pode precisar de ajuste.
        # Geralmente, o link contém a data no formato YYYY/MM/DD.
        data_str_doe = hoje.strftime('%d/%m/%Y')
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
        
        # Lógica para encontrar o link da ALCE. Também pode precisar de ajuste.
        # Procuramos por um link que contenha a data no formato "DD de MÊS de AAAA".
        meses = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']
        data_str_alce = f"{hoje.day} de {meses[hoje.month-1]} de {hoje.year}"
        link_alce = soup_alce.find('a', title=lambda t: t and data_str_alce.lower() in t.lower())
        
        if link_alce and link_alce.get('href').endswith('.pdf'):
            # O link pode ser relativo, então o juntamos com a URL base.
            url_pdf_alce = requests.compat.urljoin(URL_ALCE, link_alce.get('href'))
            print(f"PDF da ALCE encontrado: {url_pdf_alce}")
            pdfs_encontrados['ALCE'] = url_pdf_alce
        else:
            print("Nenhum Diário da Assembleia encontrado para hoje.")

    except requests.exceptions.RequestException as e:
        print(f"Erro ao acessar o site da ALCE: {e}")

    # --- 3. Download, Filtro e Envio de E-mail ---
    if not pdfs_encontrados:
        print("Nenhum diário encontrado hoje. Encerrando.")
        return

    arquivos_para_enviar = []
    conteudo_email = "Olá,\n\nSegue(m) em anexo o(s) diário(s) oficial(is) encontrado(s) hoje.\n\n"

    for nome, url in pdfs_encontrados.items():
        try:
            print(f"Baixando {nome} de {url}...")
            response_pdf = requests.get(url, stream=True)
            response_pdf.raise_for_status()
            
            # Lê o PDF em memória
            pdf_bytes = response_pdf.content
            
            enviar_este_pdf = True
            
            # Filtro por palavra-chave (se houver)
            if PALAVRAS_CHAVE:
                print(f"Verificando palavras-chave em {nome}...")
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
                texto_completo = ""
                for page in pdf_reader.pages:
                    texto_completo += page.extract_text()
                
                palavras_encontradas = [p for p in PALAVRAS_CHAVE if p.lower() in texto_completo.lower()]
                
                if palavras_encontradas:
                    conteudo_email += f"- O diário '{nome}' contém as palavras: {', '.join(palavras_encontradas)}.\n"
                else:
                    print(f"Nenhuma palavra-chave encontrada em {nome}. O anexo não será enviado.")
                    enviar_este_pdf = False
            
            if enviar_este_pdf:
                nome_arquivo = f"{nome}_{hoje.strftime('%Y-%m-%d')}.pdf"
                arquivos_para_enviar.append({'nome': nome_arquivo, 'conteudo': pdf_bytes})

        except Exception as e:
            print(f"Falha ao baixar ou processar o PDF de {nome}: {e}")
    
    if arquivos_para_enviar:
        enviar_email(arquivos_para_enviar, conteudo_email)
    else:
        print("Nenhum PDF correspondeu aos filtros. Nenhum e-mail será enviado.")


def enviar_email(anexos, corpo_email):
    """Função para montar e enviar o email."""
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
        # Configuração para o Gmail. Ajuste se usar outro provedor.
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_REMETENTE, SENHA_REMETENTE)
        server.sendmail(EMAIL_REMETENTE, EMAIL_DESTINATARIO, msg.as_string())
        server.quit()
        print("Email enviado com sucesso!")
    except Exception as e:
        print(f"Erro ao enviar o email: {e}")

# --- Ponto de Entrada do Script ---
if __name__ == '__main__':
    buscar_e_enviar_diarios()