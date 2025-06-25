import shutil
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import traceback
import requests
import time
import random
import logging
import threading
from queue import Queue
from collections import Counter
from selenium.webdriver import ActionChains
import re
import os, subprocess
import pyautogui
import colorama
import uuid
import base64
import json
from datetime import datetime
colorama.init() 

GITHUB_TOKEN = ''  # Thay bằng token của bạn
API_URL = "https://api.github.com/repos/xs2770/storage/contents/trial.json"
RAW_URL = "https://raw.githubusercontent.com/xs2770/storage/master/trial.json"

COLOR_RESET = '\033[0m'
COLOR_INFO = '\033[32m'    # Green
COLOR_WARNING = '\033[33m' # Yellow
COLOR_ERROR = '\033[31m'   # Red

card_success = []
def get_device_id():
    return str(uuid.getnode())

# Thiết lập logging cho cả file và console
class ColorFormatter(logging.Formatter):
    def format(self, record):
        color = ''
        if record.levelno == logging.INFO:
            color = COLOR_INFO
        elif record.levelno == logging.WARNING:
            color = COLOR_WARNING
        elif record.levelno == logging.ERROR:
            color = COLOR_ERROR
        msg = super().format(record)
        return f"{color}{msg}{COLOR_RESET}"
    def formatTime(self, record, datefmt=None):
        # record.created là timestamp float
        dt = datetime.fromtimestamp(record.created)
        # Trả về string định dạng "HH:MM"
        return dt.strftime("%H:%M")

# Create stream handler with color
console_handler = logging.StreamHandler()
console_handler.setFormatter(ColorFormatter(
    '%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s'
))

# File handler without color
file_handler = logging.FileHandler('automation.log', encoding='utf-8')
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s'
))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, console_handler]
)

# Khóa để đảm bảo an toàn khi ghi file trong môi trường đa luồng
file_lock = threading.Lock()
show_browser = True

# Đọc file đầu vào
def load_input_files():
    try:
        # Đọc accounts.txt (email|password|2fa_key)
        accounts = []
        with open('mailadd.txt', 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split('|')
                if len(parts) != 3:
                    # logging.warning(f"Bỏ qua dòng tài khoản không hợp lệ: {line}")
                    continue
                accounts.append({
                    'email': parts[0].strip(),
                    'password': parts[1].strip(),
                    '2fa_key': parts[2].strip()
                })
        
        # Đọc cards.txt (card_number|expiry_month|expiry_year|cvv)
        cards = []
        last_4_digits = []
        with open('cards.txt', 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split('|')
                if len(parts) != 4:
                    # logging.warning(f"Bỏ qua dòng thẻ không hợp lệ: {line}")
                    continue
                card_number = parts[0].strip()
                last_4 = card_number[-4:]
                last_4_digits.append(last_4)
                expiry_date = f"{parts[1].strip()}/{parts[2].strip()}"
                cards.append({
                    'card_number': card_number,
                    'expiry_date': expiry_date,
                    'card_holder': f'Holder{random.randint(1000,9999)}',
                    'cvv': parts[3].strip(),
                    'line': line.strip()
                })
        
        # Kiểm tra trùng lặp 4 số cuối của thẻ
        last_4_counts = Counter(last_4_digits)
        duplicates = [last_4 for last_4, count in last_4_counts.items() if count > 1]
        if duplicates:
            logging.warning(f"Phát hiện các thẻ có 4 số cuối trùng lặp: {duplicates}. Điều này có thể gây nhầm lẫn khi kiểm tra.")
        
        # Đọc proxies.txt (một proxy mỗi dòng, tùy chọn)
        proxies = []
        try:
            with open('proxies.txt', 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    proxies.append(line)
            if not proxies:
                logging.info("File proxies.txt rỗng. Chạy mà không dùng proxy.")
        except FileNotFoundError:
            logging.info("Không tìm thấy file proxies.txt. Chạy mà không dùng proxy.")
        
        if not accounts or not cards:
            raise ValueError("File tài khoản hoặc thẻ rỗng hoặc không hợp lệ")
        
        logging.info("Đã tải thành công các file đầu vào.")
        return accounts, cards, proxies
    except Exception as e:
        logging.error(f"Lỗi khi tải file đầu vào: {repr(e)}")
        raise

# Lấy mã 2FA từ https://2fa.live/
def get_2fa_code(secret_key):
    try:
        url = f"https://2fa.live/tok/{secret_key}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            return data.get('token')
        else:
            logging.error(f"Không lấy được mã 2FA cho khóa: {secret_key}")
            return None
    except Exception as e:
        logging.error(f"Lỗi khi lấy mã 2FA: {repr(e)}")
        return None
import os
import shutil
import tempfile

import undetected_chromedriver as webdriver


class ProxyExtension:
    manifest_json = """
    {
        "version": "1.0.0",
        "manifest_version": 2,
        "name": "Chrome Proxy",
        "permissions": [
            "proxy",
            "tabs",
            "unlimitedStorage",
            "storage",
            "<all_urls>",
            "webRequest",
            "webRequestBlocking"
        ],
        "background": {"scripts": ["background.js"]},
        "minimum_chrome_version": "76.0.0"
    }
    """

    background_js = """
    var config = {
        mode: "fixed_servers",
        rules: {
            singleProxy: {
                scheme: "http",
                host: "%s",
                port: %d
            },
            bypassList: ["localhost"]
        }
    };

    chrome.proxy.settings.set({value: config, scope: "regular"}, function() {});

    function callbackFn(details) {
        return {
            authCredentials: {
                username: "%s",
                password: "%s"
            }
        };
    }

    chrome.webRequest.onAuthRequired.addListener(
        callbackFn,
        { urls: ["<all_urls>"] },
        ['blocking']
    );
    """

    def __init__(self, host, port, user, password):
        self._dir = os.path.normpath(tempfile.mkdtemp())

        manifest_file = os.path.join(self._dir, "manifest.json")
        with open(manifest_file, mode="w") as f:
            f.write(self.manifest_json)

        background_js = self.background_js % (host, port, user, password)
        background_file = os.path.join(self._dir, "background.js")
        with open(background_file, mode="w") as f:
            f.write(background_js)

    @property
    def directory(self):
        return self._dir

    def __del__(self):
        shutil.rmtree(self._dir)

def get_chrome_major_version():
    output = subprocess.check_output(
        ['google-chrome', '--version'], stderr=subprocess.DEVNULL
    ).decode()
    return int(re.search(r"(\d+)\.", output).group(1))

# Khởi tạo trình duyệt Chrome với tính năng chống phát hiện
def init_driver(proxy=None, email=None, row = 0, col = 0, size=(1366, 768)):
    options = uc.ChromeOptions()
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-infobars')
    options.add_argument('--disable-extensions')
    
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/117.0"
    ]
    options.add_argument(f'--user-agent={random.choice(user_agents)}')
    user_data_dir = os.path.join(os.getcwd(), "user-data")
    if email:
        user_data_dir = os.path.join(user_data_dir, "user-data" + email)
    if not os.path.exists(user_data_dir):
        os.makedirs(user_data_dir)
    options.add_argument(f'--user-data-dir={user_data_dir}')
    if proxy:
        proxy_parts = proxy.split(':')
        if len(proxy_parts) == 4:
            proxy_extension = ProxyExtension(
                host=proxy_parts[0],
                port=int(proxy_parts[1]),
                user=proxy_parts[2],
                password=proxy_parts[3]
            )
            options.add_argument(f'--load-extension={proxy_extension.directory}')

    driver = uc.Chrome(
        options=options,
        headless= (not show_browser),
        suppress_welcome=True,
        use_subprocess=True,
        version_main=137
    )
    if show_browser:
        width, height = size
        x = col * width
        y = row * height
        driver.set_window_rect(x=x, y=y, width=width, height=height)
    else:
        driver.set_window_size(1366, 768)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.navigator.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        """
    })
    
    return driver

# Đăng nhập vào Amazon với 2FA
def login_amazon(driver, email, password, secret_key):
    try:
        driver.get(
            "https://na.account.amazon.com/ap/signin?_encoding=UTF8&openid.mode=checkid_setup&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.pape.max_auth_age=0&ie=UTF8&openid.ns.pape=http%3A%2F%2Fspecs.openid.net%2Fextensions%2Fpape%2F1.0&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&pageId=lwa&openid.assoc_handle=amzn_lwa_na&marketPlaceId=ATVPDKIKX0DER&arb=e62133d5-1923-4ce7-8b7a-11fb8efad586&language=en_US&openid.return_to=https%3A%2F%2Fna.account.amazon.com%2Fap%2Foa%3FmarketPlaceId%3DATVPDKIKX0DER%26arb%3De62133d5-1923-4ce7-8b7a-11fb8efad586%26language%3Den_US&enableGlobalAccountCreation=1&metricIdentifier=amzn1.application.eb539eb1b9fb4de2953354ec9ed2e379&signedMetricIdentifier=fLsotU64%2FnKAtrbZ2LjdFmdwR3SEUemHOZ5T2deI500%3D"
        )

        wait = WebDriverWait(driver, 15)

        # Nhập email
        email_input = wait.until(EC.visibility_of_element_located((By.ID, "ap_email")))
        email_input.send_keys(email)
        safe_click(driver, driver.find_element(By.ID, "continue"))

        time.sleep(1)
        if "ap/cvf" in driver.current_url or driver.find_elements(By.ID, "captchacharacters"):
            logging.error(f"🚫 CAPTCHA sau email: {email}")
            return False, "CAPTCHA"

        # Nhập mật khẩu
        pwd_input = wait.until(EC.visibility_of_element_located((By.ID, "ap_password")))
        pwd_input.send_keys(password)
        safe_click(driver, driver.find_element(By.ID, "signInSubmit"))

        time.sleep(1)
        if "ap/cvf" in driver.current_url or driver.find_elements(By.ID, "captchacharacters"):
            logging.error(f"🚫 CAPTCHA sau mật khẩu: {email}")
            return False, "CAPTCHA"

        # Nhập mã 2FA
        try:
            otp_code = get_2fa_code(secret_key)
            if otp_code:
                otp_input = wait.until(EC.visibility_of_element_located((By.ID, "auth-mfa-otpcode")))
                otp_input.send_keys(otp_code)
                safe_click(driver, driver.find_element(By.ID, "auth-signin-button"))

                WebDriverWait(driver, 20).until(EC.url_contains("amazon.com"))
                logging.info(f"✅ Đăng nhập thành công cho {email}")
                return True, None
            else:
                logging.error(f"❗ Không lấy được mã 2FA cho {email}")
                return False, "2FA Failure"
        except TimeoutException:
            return True, None

    except Exception as e:
        logging.error(f"❗ Lỗi khi đăng nhập tài khoản {email}: {repr(e)}")
        traceback_str = traceback.format_exc()
        logging.debug(f"Chi tiết lỗi:\n{traceback_str}")
        return False, repr(e)

def safe_click(driver, element):
    try:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        time.sleep(0.3)
        ActionChains(driver).move_to_element(element).click().perform()
    except Exception as e:
        # logging.warning(f"Click thao tác: {repr(e)}. Thử lại với JavaScript.")
        driver.execute_script("arguments[0].click();", element)

# Thêm một thẻ Visa
def add_visa_card(driver, card_number, expiry_date, card_holder):
    driver.get("https://www.amazon.com/cpe/yourpayments/settings/manageoneclick")
    try:
        # Bước 1: Nhấn nút "Change"
        change_button = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((
                By.XPATH,
                "//span[normalize-space(text())='Payment method']/following::input[@class='pmts-link-button' and @value='Change'][1]"
            ))
        )
        safe_click(driver, change_button)

        # Bước 2: Mở popup và click "Add a credit or debit card"
        wait = WebDriverWait(driver, 15)
        wait.until(EC.visibility_of_element_located((By.CLASS_NAME, "a-popover-modal")))
        time.sleep(1)

        add_card_link = wait.until(
            EC.element_to_be_clickable((By.ID, "apx-add-credit-card-action-test-id"))
        )
        safe_click(driver, add_card_link)
        time.sleep(1)

        # Bước 3: Điền thông tin thẻ trong iframe
        iframe = wait.until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, ".pmts-add-payment-instruments-wrapper iframe"))
        )
        driver.switch_to.frame(iframe)
        time.sleep(0.5)

        wait.until(EC.visibility_of_element_located((By.NAME, "ppw-accountHolderName"))).send_keys(card_holder)
        time.sleep(random.uniform(0.5, 1.2))
        driver.find_element(By.NAME, "addCreditCardNumber").send_keys(card_number)
        time.sleep(random.uniform(0.5, 1.2))

        # Set tháng
        month, year = expiry_date.split('/')
        month_btn = wait.until(EC.element_to_be_clickable((
            By.CSS_SELECTOR, "#add-credit-card-expiry-date-input-id .pmts-expiry-month .a-button-text"
        )))
        safe_click(driver, month_btn)

        wait.until(EC.visibility_of_element_located((By.ID, "a-popover-1")))
        time.sleep(0.5)
        month_options = driver.find_elements(By.CSS_SELECTOR, "#a-popover-1 .a-dropdown-item a")
        for option in month_options:
            if option.text.strip() == month.zfill(2):
                safe_click(driver, option)
                break

        # Set năm
        year_btn = wait.until(EC.element_to_be_clickable((
            By.CSS_SELECTOR, "#add-credit-card-expiry-date-input-id .pmts-expiry-year .a-button-text"
        )))
        safe_click(driver, year_btn)

        wait.until(EC.visibility_of_element_located((By.ID, "a-popover-2")))
        time.sleep(0.5)
        year_options = driver.find_elements(By.CSS_SELECTOR, "#a-popover-2 .a-dropdown-item a")
        for option in year_options:
            if option.text.strip() == year:
                safe_click(driver, option)
                break

        # Bước 4: Click "Add card"
        add_card_button = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//input[@name='ppw-widgetEvent:AddCreditCardEvent']"))
        )
        safe_click(driver, add_card_button)
        time.sleep(random.uniform(1.5, 2.5))

        driver.switch_to.default_content()

        # Bước 5: Đóng popup
        close_button = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//button[@data-action='a-popover-close']"))
        )
        safe_click(driver, close_button)

        logging.info(f"✅ Thêm thẻ: {card_number}")
        card_success.append(card_number)
        return True

    except Exception as e:
        logging.error(f"❌ Lỗi khi thêm thẻ {card_number}: {repr(e)}")
        return False

# Kiểm tra thẻ trên trang ví và xuất thẻ live ra file
def check_cards(driver, added_cards, email):
    logging.info(f"⏳ Đang chờ 4 phút trước khi kiểm tra thẻ cho tài khoản {email}...")
    time.sleep(240)

    try:
        driver.get("https://www.amazon.com/cpe/yourpayments/wallet")

        WebDriverWait(driver, 15).until(
            EC.visibility_of_any_elements_located((By.CSS_SELECTOR, ".apx-wallet-desktop-payment-method-selectable-tab-css"))
        )
        card_elements = driver.find_elements(By.CSS_SELECTOR, ".apx-wallet-desktop-payment-method-selectable-tab-css.a-scroller-vertical div.apx-wallet-selectable-payment-method-tab")
        live_cards = []

        logging.info(f"🔍 Đã tìm thấy {len(card_elements)} thẻ trên trang ví cho tài khoản {email}")

        for card_elem in card_elements:
            try:
                number_tail_elem = card_elem.find_element(By.CSS_SELECTOR, "span.pmts-instrument-number-tail")
                number_tail_text = number_tail_elem.text
                last_4_match = re.search(r'\d{4}$', number_tail_text)
                if not last_4_match:
                    continue
                last_4 = last_4_match.group(0)

                is_die = False
                try:
                    img_elem = card_elem.find_element(By.CSS_SELECTOR, "img.apx-wallet-selectable-image")
                    img_src = img_elem.get_attribute("src")
                    if img_src in [
                        "https://m.media-amazon.com/images/I/41MGiaNMk5L._SL85_.png",
                        "https://m.media-amazon.com/images/I/81NBfFByidL._SL85_.png"
                    ]:
                        is_die = True
                except NoSuchElementException:
                    pass

                if not is_die:
                    for card in added_cards:
                        if card['card_number'][-4:] == last_4:
                            live_cards.append(card['line'])
                            break
                else:
                    logging.info(f"❌ Thẻ ****{last_4} cho {email} là 'die'")

            except NoSuchElementException:
                continue

        if live_cards:
            existing_cards = set()
            if os.path.exists('live_cards.txt'):
                with open('live_cards.txt', 'r', encoding='utf-8') as f:
                    existing_cards = set(line.strip() for line in f)

            with file_lock:
                with open('live_cards.txt', 'a', encoding='utf-8') as f:
                    for live_card in live_cards:
                        if live_card not in existing_cards:
                            f.write(live_card + '\n')
                            card_number = live_card.split('|')[0]
                            logging.info(f"✅ Đã lưu thẻ live:  {card_number}")
                        else:
                            logging.info(f"📌 Thẻ {live_card.split('|')[0]} đã tồn tại trong live_cards.txt, không ghi trùng.")
        # Xóa tất cả thẻ
        if card_elements:
            delete_card(driver)
            logging.info(f"🧹 Đã xóa toàn bộ thẻ khỏi ví Amazon cho {email}")
        else:
            logging.info(f"📭 Không tìm thấy thẻ nào để xóa cho {email}")
    except Exception as e:
        logging.error(f"❗ Lỗi khi kiểm tra thẻ cho {email}: {repr(e)}")

# Xoá thẻ trên trang ví
def delete_card(driver):
    selector = ".apx-wallet-desktop-payment-method-selectable-tab-css div.apx-wallet-selectable-payment-method-tab"
    index = 0

    while True:
        try:
            wait = WebDriverWait(driver, 15)
            wait.until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, ".apx-wallet-desktop-payment-method-selectable-tab-css"))
            )
            card_elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if not card_elements:
                logging.info("✅ Không còn thẻ nào để xóa. Thoát.")
                break

            before_count = len(card_elements)

            edit_button = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, '.a-fixed-left-grid-col a[aria-label="edit payment method"]'))
            )
            safe_click(driver, edit_button)
            time.sleep(1)

            remove_button = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'input.apx-remove-link-button[type="submit"]'))
            )
            safe_click(driver, remove_button)
            time.sleep(1)

            confirm_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".pmts-delete-instrument.apx-remove-button-desktop"))
            )
            safe_click(driver, confirm_button)

            logging.info(f"🗑 Đã xác nhận xóa thẻ thứ {index + 1}")

            # Chờ thẻ biến mất khỏi DOM
            wait.until(lambda d: len(d.find_elements(By.CSS_SELECTOR, selector)) < before_count)

            logging.info(f"✅ Đã xóa xong thẻ thứ {index + 1}")
            index += 1

            driver.refresh()
            time.sleep(2)

        except TimeoutException as e:
            logging.error(f"⏱ Timeout khi xử lý thẻ thứ {index + 1}: {repr(e)}")
            driver.refresh()
            time.sleep(2)
            continue
        except NoSuchElementException as e:
            logging.error(f"🕳 Không tìm thấy nút khi xử lý thẻ thứ {index + 1}: {repr(e)}")
            driver.refresh()
            time.sleep(2)
            continue
        except Exception as e:
            logging.error(f"❗ Lỗi không xác định khi xóa thẻ {index + 1}: {repr(e)}")
            driver.refresh()
            time.sleep(2)
            continue

# Xử lý một tài khoản với phân bổ thẻ tuần tự và kiểm tra
def process_account(driver, account, cards, account_index, max_cards=5, proxy=None):
    email, password, secret_key = account['email'], account['password'], account['2fa_key']
    try:
        logging.info(f"Đang xử lý tài khoản: {email} với proxy: {proxy if proxy else 'Không có proxy'}")        
        # # Đăng nhập
        login_success, error_reason = login_amazon(driver, email, password, secret_key)
        if not login_success:
            logging.error(f"Đăng nhập thất bại cho tài khoản {email}: {error_reason}")
            # Lưu tài khoản thất bại vào acdie.txt
            with file_lock:
                # Check if account already exists in acdie.txt
                exists = False
                if os.path.exists('acdie.txt'):
                    with open('acdie.txt', 'r', encoding='utf-8') as f:
                        for line in f:
                            if line.strip().split('|')[0] == email:
                                exists = True
                                break
                if not exists:
                    with open('acdie.txt', 'a', encoding='utf-8') as f:
                        f.write(f"{email}|{password}|{secret_key}\n")
                    logging.info(f"Đã lưu tài khoản {email} vào acdie.txt do lỗi đăng nhập ({error_reason})")
                else:
                    logging.info(f"Tài khoản {email} đã tồn tại trong acdie.txt, không ghi trùng.")
            return
            
        # Phân bổ thẻ tuần tự
        card_count = len(cards)
        start_idx = (account_index * max_cards) % card_count if card_count > 0 else 0
        selected_cards = []
        for i in range(max_cards):
            if card_count == 0:
                break
            card_idx = (start_idx + i) % card_count
            selected_cards.append(cards[card_idx])
        
        # Thêm thẻ
        added_cards = []
        for card in selected_cards:
            if add_visa_card(
                driver,
                card['card_number'],
                card['expiry_date'],
                card['card_holder']
            ):
                added_cards.append(card)
                time.sleep(random.uniform(2, 3))
            else:
                logging.error(f"Thêm thẻ thất bại cho tài khoản {email}. Tiếp tục với thẻ tiếp theo.")
        
        # Kiểm tra thẻ đã thêm
        if added_cards:
            check_cards(driver, added_cards, email)
        else:
            logging.error(f"Không có thẻ nào được thêm thành công cho tài khoản {email}. Bỏ qua kiểm tra.")

        logging.info(f"Hoàn tất xử lý cho tài khoản {email}")
    except Exception as e:
        logging.error(f"Lỗi khi xử lý tài khoản {email}: {repr(e)}")
        # Lưu tài khoản thất bại vào mailadd.txt
        with file_lock:
            with open('mailadd.txt', 'a', encoding='utf-8') as f:
                f.write(f"{email}|{password}|{secret_key}\n")
        logging.info(f"Đã lưu tài khoản {email} vào mailadd.txt do lỗi xử lý chung")
    finally:
        if driver:
            driver.quit()

def read_key():
    try:
        with open("key.txt", "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        logging.error("Không tìm thấy file key.txt")
        return None

def get_current_keys():
    try:
        response = requests.get(RAW_URL, headers={"Cache-Control": "no-cache"})
        if response.status_code == 200:
            return response.json()
        else:
            logging.error(f"Lỗi khi lấy trial.json từ GitHub: {response.status_code}")
    except Exception as e:
        logging.error(f"Lỗi khi lấy dữ liệu từ GitHub: {repr(e)}")
    return None

def get_file_sha():
    try:
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        resp = requests.get(API_URL, headers=headers)
        if resp.status_code == 200:
            return resp.json().get("sha")
        else:
            logging.error(f"Lỗi khi lấy SHA file: {resp.text}")
    except Exception as e:
        logging.error(f"Lỗi khi lấy SHA: {repr(e)}")
    return None


def update_key_list(new_data, sha):
    try:
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }

        json_str = json.dumps(new_data, indent=2)
        content_bytes = json_str.encode("utf-8")
        content_base64 = base64.b64encode(content_bytes).decode("utf-8")

        payload = {
            "message": "Cập nhật key khi dùng thử",
            "content": content_base64,
            "sha": sha
        }

        response = requests.put(API_URL, headers=headers, json=payload)
        if response.status_code in [200, 201]:
            logging.info("Đã cập nhật key thành công.")
            return True
        else:
            logging.error(f"Lỗi khi cập nhật file: {response.status_code} - {response.text}")
    except Exception as e:
        logging.error(f"Lỗi khi push lên GitHub: {repr(e)}")
    return False

def check_and_update():
    key = read_key()
    if not key:
        return False
    logging.info(f"Đang kiểm tra key: {key}")

    device_id = get_device_id()
    data = get_current_keys()
    if not data:
        return False

    keys = data.get("keys", [])
    matched = False

    for entry in keys:
        if entry["key"] == key:
            if not entry.get("used", False) or entry.get("device") == device_id:
                entry["used"] = True
                entry["device"] = device_id
                matched = True
                break

    if not matched:
        logging.error("Key không hợp lệ hoặc đã được dùng trên thiết bị khác.")
        return False

    sha = get_file_sha()
    if not sha:
        return False

    return update_key_list({"keys": keys}, sha)

def clean_all_user_data():
    user_data_dir = os.path.join(os.getcwd(), "user-data")
    if os.path.exists(user_data_dir):
        try:
            shutil.rmtree(user_data_dir)
            logging.info("Đã xoá toàn bộ dữ liệu người dùng.")
        except Exception as e:
            logging.error(f"Lỗi khi xoá thư mục user-data: {repr(e)}")

# Hàm chính với nhập số luồng
def main():
    accounts, cards, proxies = load_input_files()
    if not check_and_update():
        logging.error("Phiên bản key không hợp lệ hoặc đã được sử dụng trên thiết bị khác. Vui lòng kiểm tra lại key.txt.")
        return
    # Nhập số luồng
    try:
        num_threads = int(input("Nhập số luồng để chạy: "))
        if num_threads <= 0:
            logging.warning("Số luồng phải là số dương. Mặc định là 1.")
            num_threads = 1
        if num_threads > len(accounts):
            logging.warning(f"Số luồng ({num_threads}) vượt quá số tài khoản ({len(accounts)}). Đặt thành {len(accounts)}.")
            num_threads = len(accounts)
    except ValueError:
        logging.warning("Đầu vào số luồng không hợp lệ. Mặc định là 1.")
        num_threads = 1
    # Nhập lựa chọn hiển thị trình duyệt
    show = input("Bạn có muốn hiển thị trình duyệt không? (y/n): ").strip().lower()
    global show_browser
    if show in ['y', 'yes']:
        show_browser = True
    else:
        show_browser = False
    account_queue = Queue()
    screen_width, screen_height = pyautogui.size()
    logging.info(f"Kích thước màn hình: {screen_width}x{screen_height}")
    col = input("Nhập số cột (mặc định 1): ").strip()
    if not col.isdigit() or int(col) <= 0:
        col = 1
    else:
        col = int(col)
    
    # Thêm tài khoản vào hàng đợi với chỉ số
    for idx, account in enumerate(accounts):
        account_queue.put((account, idx))
    driver_init_lock = threading.Lock()
    acc_success = []
    def worker():
        while not account_queue.empty():
            account, account_index = account_queue.get()
            try:
                with driver_init_lock:
                    proxy = random.choice(proxies) if proxies else None
                    row = account_index // col
                    col_index = account_index % col
                    size = (screen_width // col, 300)
                    driver = init_driver(proxy=proxy, email=account['email'], row=row, col=col_index, size=size)
                process_account(driver, account, cards, account_index, proxy=proxy)
                acc_success.append(account_index)
            except Exception as e:
                logging.error(f"Lỗi khi xử lý tài khoản {account['email']}: {repr(e)}")
            finally:
                if driver:
                    try:
                        driver.quit()
                        time.sleep(1)  # Chờ để đảm bảo process con thoát
                    except Exception as e:
                        logging.error(f"Lỗi khi đóng driver: {repr(e)}")
                account_queue.task_done()
    def clean_acc_success():
        if acc_success:
            # Xoá các tài khoản thành công khỏi mailadd.txt
            try:
                success_emails = set(accounts[idx]['email'] for idx in acc_success)
                with file_lock:
                    if os.path.exists('mailadd.txt'):
                        with open('mailadd.txt', 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                        with open('mailadd.txt', 'w', encoding='utf-8') as f:
                            for line in lines:
                                email = line.strip().split('|')[0]
                                if email not in success_emails:
                                    f.write(line)
                logging.info("Đã xoá các tài khoản thành công khỏi mailadd.txt")
            except Exception as e:
                logging.error(f"Lỗi khi xoá tài khoản thành công khỏi mailadd.txt: {repr(e)}")
    def clean_card_success():
        if card_success:
            # Xoá các thẻ thành công khỏi cards.txt
            try:
                success_cards = set(card['line'] for card in cards if card['card_number'] in card_success)
                with file_lock:
                    if os.path.exists('cards.txt'):
                        with open('cards.txt', 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                        with open('cards.txt', 'w', encoding='utf-8') as f:
                            for line in lines:
                                if line.strip() not in success_cards:
                                    f.write(line)
                logging.info("Đã xoá các thẻ thành công khỏi cards.txt")
            except Exception as e:
                logging.error(f"Lỗi khi xoá thẻ thành công khỏi cards.txt: {repr(e)}")

    threads = []
    for _ in range(num_threads):
        t = threading.Thread(target=worker, name=f"Luồng-{_+1}")
        t.start()
        threads.append(t)
    
    for t in threads:
        t.join()
    
    logging.info("Đã xử lý xong tất cả tài khoản.")
    # Xoá toàn bộ dữ liệu người dùng nếu cần
    clean_all_user_data()
    # Xoá các tài khoản thành công khỏi mailadd.txt
    clean_acc_success()
    # Xoá các thẻ thành công khỏi cards.txt
    clean_card_success()
    logging.info("Hoàn tất chương trình. Tự động thoát sau 5 giây...")
    time.sleep(5)

if __name__ == "__main__":
    main()
