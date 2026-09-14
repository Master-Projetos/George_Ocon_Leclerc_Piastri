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

RELATORY = "viabilidade"
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GEOGRID_USER = os.getenv("GEOGRID_USER")
GEOGRID_PASS = os.getenv("GEOGRID_PASS")
if not GEOGRID_USER or not GEOGRID_PASS:
    raise RuntimeError("GEOGRID_USER and GEOGRID_PASS must be set (see .env)")

download_dir = os.path.join(PROJECT_ROOT, "data")
os.makedirs(download_dir, exist_ok=True)

options = Options()
options.add_experimental_option("prefs", {
    "download.default_directory": download_dir,
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
#   "safebrowsing.enabled": True,
    "plugins.always_open_pdf_externally": True
})

driver = webdriver.Chrome(options=options)

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
                driver.execute_script("arguments[0].click();", element)
            return element
        except (StaleElementReferenceException, ElementClickInterceptedException) as error:
            last_error = error
            time.sleep(retry_delay)
    raise last_error


driver.get("https://morfeu.geogridmaps.com.br/rbc/")


user_box = driver.find_element(by=By.NAME, value="usuario")
user_box.send_keys(GEOGRID_USER)

password_box = driver.find_element(by=By.NAME, value="senha")
password_box.send_keys(GEOGRID_PASS)

aceitar_button = driver.find_elements(by=By.NAME, value="aceitar")
if aceitar_button:
    click(By.NAME, "aceitar")

click(By.NAME, "entrar")
click(By.CLASS_NAME, "elemento-menu")
click(By.NAME, "relatorios")
click(By.CSS_SELECTOR, f"div[data-relatorio='{RELATORY}']")

# CAMPOS
click(By.NAME, "configurar")
click(By.XPATH, "//label[.//span[text()='Tipo']]//input[@name='item']")
click(By.XPATH, "//label[.//span[text()='Usuário']]//input[@name='item']")
click(By.NAME, "salvar")

# FILTROS
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

time.sleep(120)
driver.quit()