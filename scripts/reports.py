import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    StaleElementReferenceException,
    ElementClickInterceptedException,
)
from dotenv import load_dotenv

load_dotenv()

# Doesn't include the "gestao" relatory, because
# it's a set containing all other relatories
# and requires different logic
ALLOWED_RELATORIES = [
    "cabos", "dutos", "poste",
    "estacao", "pontoAcesso", "grupoAcesso",
    "caixa", "terminal", "rack",
    "reserva", "viabilidade", "interesse",
    "equipamento", "antenas"
]

# Only these realtory types expose a "Tipo" field in the form
ALLOWED_ITEM_TYPES = ["viabilidade", "terminal", "caixa", "rack"]

RELATORY = "viabilidade"

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
download_dir = os.path.join(PROJECT_ROOT, "data")
os.makedirs(download_dir, exist_ok=True)

GEOGRID_USER = os.getenv("GEOGRID_USER")
GEOGRID_PASS = os.getenv("GEOGRID_PASS")


if not GEOGRID_USER or not GEOGRID_PASS:
    raise RuntimeError("GEOGRID_USER and GEOGRID_PASS must be set (see .env)")

if RELATORY not in ALLOWED_RELATORIES:
    raise RuntimeError("This relatory doesn't have support yet, try a valid one")


options = Options()
options.add_argument("--headless=new")
options.add_experimental_option("prefs", {
    "download.default_directory": download_dir,
    "download.prompt_for_download": False,
})

driver = webdriver.Chrome(options=options)

# In headless mode, downloads are automatically blocked, even with
# download.default_directory set in options.
# So we use the Chrome DevTools Protocol to force downloads and set where they go.
driver.execute_cdp_cmd("Page.setDownloadBehavior", {
    "behavior": "allow",
    "downloadPath": download_dir,
})

def click(by, value, timeout=15, retries=20, retry_delay=1):
    last_error = None
    for attempt in range(retries):
        try:
            element = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((by, value))
            )
            if attempt < retries - 1:
                element.click()
            else:
                # Last attempt: force click via JS
                driver.execute_script("arguments[0].click();", element)
            return element
        except (StaleElementReferenceException, ElementClickInterceptedException) as error:
            last_error = error
            time.sleep(retry_delay)
    raise last_error


driver.get("https://morfeu.geogridmaps.com.br/rbc/")

# LOGIN
user_box = driver.find_element(by=By.NAME, value="usuario")
user_box.send_keys(GEOGRID_USER)

password_box = driver.find_element(by=By.NAME, value="senha")
password_box.send_keys(GEOGRID_PASS)

# Cookie/terms banner doesn't always appear, so only click if it exists
cookies_button = driver.find_elements(by=By.NAME, value="aceitar")
if cookies_button:
    click(By.NAME, "aceitar")

click(By.NAME, "entrar")

# RELATORY SELECT
click(By.CLASS_NAME, "elemento-menu")
click(By.NAME, "relatorios")
click(By.CSS_SELECTOR, f"div[data-relatorio='{RELATORY}']")

# COLUMNS IN THE XLSX
click(By.NAME, "configurar")
if RELATORY in ALLOWED_ITEM_TYPES:
    click(By.XPATH, "//label[.//span[text()='Tipo']]//input[@name='item']")
click(By.XPATH, "//label[.//span[text()='Usuário']]//input[@name='item']")
click(By.NAME, "salvar")

# FILTER - exclude records that are still just a project (not executed yet)
click(By.NAME, "adicionar-filtros")
click(By.XPATH, "//label[.//span[text()='Execução']]//input[@name='item']")
click(By.XPATH, "//button[@name='salvar' and normalize-space(text())='Aplicar filtros']")

# EXCEL
click(By.NAME, "exportar-xls")
archive_name = WebDriverWait(driver, 15).until(
    EC.element_to_be_clickable((By.CSS_SELECTOR, "div[name='titulo'] input"))
)
archive_name.clear()
archive_name.send_keys(RELATORY)
click(By.XPATH, "//button[@name='salvar' and normalize-space(text())='Exportar']")

# Wait 2 minutes before ending the script, so it has time to download bigger relatories
time.sleep(120)
driver.quit()
