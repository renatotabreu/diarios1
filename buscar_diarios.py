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

# Ignora avisos de SSL (uma boa prática a se manter)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

# --- CONFIGURAÇÕES ---
EMAIL_REMETENTE = os.getenv('EMAIL_REMETENTE')
SENHA_REMETENTE = os.getenv('SENHA_REMETENTE')
EMAIL_DESTINATARIO = os.getenv('EMAIL_DESTINATARIO')

# --- ALTERAÇÃO AQUI: NOVA URL DO DOE ---
URL_DOE = "http://pesquisa.doe.seplag.ce.gov.br/doepesquisa/sead.do?page=ultimasEdicoes&cmd=11&action=Ultimas"
URL_ALCE = "https://doalece.al.ce.gov.br/publico/ultimas-edicoes"

def buscar_diario_doe(data_alvo):
    # --- ALTERAÇÃO AQUI: Lógica reescrita para a nova página do DOE (baseada em tabela) ---
    try:
        data_str_busca = data_alvo.strftime('%d/%m/%Y')
        print(f"Buscando no site do DOE por diários da data {data_str_busca}...")
        response = requests.get(URL_DOE, headers={'User-Agent': 'Mozilla/5.0'}, verify=False, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # A página usa uma tabela para listar os diários
        tabela_resultados = soup.find('table', id='resultados')
        if not tabela_resultados:
            print("Não foi possível encontrar a tabela de resultados no site do DOE.")
            return None

        linhas = tabela_resultados.find_all('tr')
        for linha in linhas:
            celulas = linha.find_all('td')
            # Verifica se a linha tem o número esperado de células (ex: 3)
            if len(celulas) >= 3 and data_str_busca in celulas[1].get_text(strip=True):
                # A data foi encontrada na segunda célula. O link está na terceira.
                link_tag = celulas[2].find('a')
                if link_tag and link_tag.get('href'):
                    # O link é relativo, então precisamos construir a URL completa
                    url_base = "http://pesquisa.doe.seplag.ce.gov.br/doepesquisa/"
                    return requests.compat.urljoin(url_base, link_tag.get('href'))

    except requests.exceptions.RequestException as e:
        print(f"Erro ao acessar o site do DOE: {e}")
    return None

def buscar_diario_alce(data_alvo):
    # Esta função, corrigida na etapa anterior, permanece a mesma.
    try:
        data_str_busca = data_alvo.strftime('%d/%m/%Y')
        print(f"Buscando no site da ALCE por diários da data {data_str_busca}...")
        response = requests.get(URL_ALCE, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        linhas_tabela = soup.find_all('tr')
        for linha in linhas_tabela:
            celula_data = linha.find('td', string=lambda text: text and data_str_busca in text)
            if celula_data:
                link_tag = linha.find('a', href=lambda href: href and 'download' in href)
                if link_tag and link_tag.get('href'):
                    return requests.compat.urljoin(URL_ALCE, link_tag.get('href'))
    except requests.exceptions.RequestException as e:
        print(f"Erro ao acessar o site da ALCE: {e}")
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
            response_pdf = requests.get(url, stream=True, verify=False, timeout=60)
            response_pdf.raise_for_status()
            pdf_bytes = response_pdf.content
            nome_arquivo = f"{nome}_{datetime.now().strftime('%Y-%m-%d')}.pdf"
            arquivos_para_enviar.append({'nome': nome_arquivo, 'conteudo': pdf_bytes})
        except Exception as e:
            print(f"Falha ao baixar ou processar o PDF de {nome}: {e}")
    if arquivos_para_enviar:
        enviar_email(arquivos_para_enviar, conteudo_email)
    else:
        print("Nenhum PDF pôde ser baixado. Nenhum e-mail será enviado.")

def enviar_email(anexos, corpo_email):
    # (Esta função permanece exatamente a mesma)
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
