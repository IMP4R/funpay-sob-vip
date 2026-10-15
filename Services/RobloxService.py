#from selenium import webdriver
#from selenium.webdriver.common.by import By
#from selenium.webdriver.support.ui import WebDriverWait
#from selenium.webdriver.support import expected_conditions as EC
#from selenium.webdriver.chrome.options import Options
import time
import os
import requests
import json


class RobloxService:
    def __init__(self, headless=True, credentials_file="ROBLOX_TOKEN.txt"):
        self.credentials_file = credentials_file
        #self.setup_driver(headless)
    '''     
    def setup_driver(self, headless):
        options = Options()
        
        if headless:
            options.add_argument("--headless=new")

        prefs = {
            "profile.default_content_setting_values.notifications": 2,
            "profile.default_content_settings.popups": 0,
            "profile.managed_default_content_settings.images": 1, 
        }

        options.add_experimental_option("prefs", prefs)

        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        import random
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.1 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.1 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.1 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.1 Safari/537.36"
        ]
        options.add_argument(f"--user-agent={random.choice(user_agents)}")

        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-web-security")
        options.add_argument("--allow-running-insecure-content")
        options.add_argument("--disable-features=VizDisplayCompositor")

        options.add_argument("--disable-extensions")
        options.add_argument("--disable-plugins-discovery")
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-backgrounding-occluded-windows")
        options.add_argument("--disable-renderer-backgrounding")

        options.add_argument("--enable-javascript")
        
        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 10)

    def read_credentials(self):
        """Читает логин и пароль из файла"""
        if not os.path.exists(self.credentials_file):
            raise FileNotFoundError(f"Файл {self.credentials_file} не найден")
        
        with open(self.credentials_file, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
        
        if len(lines) < 2:
            raise ValueError(f"В файле {self.credentials_file} должно быть 2 строки: логин и пароль")
        
        username = lines[0]
        password = lines[1]
        
        return username, password
    '''
    def regenerate_link(self, server_url) -> str | None:
        
        if not os.path.exists(self.credentials_file):
            raise FileNotFoundError(f"Файл {self.credentials_file} не найден")
        
        with open(self.credentials_file, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]

        raw = lines[0]
        cookie_header = f".ROBLOSECURITY={raw}"
        
        headers = {
            "Cookie": cookie_header,
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.1 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": "https://www.roblox.com",
            "Referer": "https://www.roblox.com/",
            "X-CSRF-Token": ""
        }
        try:
            resp = requests.post(
                "https://auth.roblox.com/v2/logout",
                headers={k: v for k, v in headers.items() if k != "X-CSRF-Token"},
                timeout=10
            )
            csrf = resp.headers.get("x-csrf-token")
            
        except Exception as e:
            print(f"[CSRF] Ошибка: {e}")
            return None
        
        if not csrf:
            print("[CSRF] Не удалось получить токен")
            return None
        
        headers["X-CSRF-Token"] = csrf
        
        try:
            url = f"https://games.roblox.com/v1/vip-servers/{server_url.split('/')[5]}"

            response = requests.patch(
                url,
                headers=headers,
                json={"active": False},
                timeout=30
            )
            time.sleep(0.3)
            response = requests.patch(
                url,
                headers=headers,
                json={"active": True},
                timeout=30
            )
            time.sleep(0.3)
            response = requests.patch(
                url,
                headers=headers,
                json={"newJoinCode": True},
                timeout=30
            )
            
            #print(f"[DEBUG] Статус ответа: {response.status_code}")
            #print(f"[DEBUG] Заголовки ответа: {dict(response.headers)}")
            #print(f"[DEBUG] Тело ответа: {response.text}")
            
            if response.status_code == 200:
                data = response.json()
                #print(f"[DEBUG] JSON данные: {json.dumps(data, indent=2)}")
                
                link = data.get("link") or data.get("joinLink") or data.get("joinCodeUrl")
                
                if link and not link.startswith("http"):
                    universe_id = data.get("universeId")
                    if universe_id:
                        link = f"https://www.roblox.com/games/start?privateServerLinkCode={link}"
                    else:
                        #print(f"[INFO] Получен код: {link}")
                        return link
                
                return link
            else:
                print(f"[ERROR] Ошибка {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            print(f"[ERROR] Исключение: {e}")
            return None
    '''
    def roblox_autorize(self):    
        try:
            username, password = self.read_credentials()
            print(f"Авторизация для пользователя: {username}")
            
            self.driver.get("https://www.roblox.com/login")
            time.sleep(1)
            
            username_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "login-username"))
            )
            password_input = self.driver.find_element(By.ID, "login-password")
            
            username_input.send_keys(username)
            time.sleep(1)
            password_input.send_keys(password)
            time.sleep(1)
            
            login_button = self.driver.find_element(By.ID, "login-button")
            login_button.click()

            time.sleep(3)
            
            if "login" in self.driver.current_url:
                print("Ошибка авторизации! Проверьте логин и пароль")
                time.sleep(300)
                return True
            else:
                print("Авторизация успешна!")
                return True
            
        except Exception as e:
            print(f"Ошибка при авторизации: {e}")
            return False
    '''
if __name__ == "__main__":
    parser = RobloxService(headless=False)
    for i in range(1):
        print(parser.regenerate_link("https://www.roblox.com/private-server/configure/0"))
        time.sleep(0.5)