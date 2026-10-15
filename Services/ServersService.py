import json
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import os
from queue import Queue, Empty


class ServerStatus:
    FREE = "free"
    IN_USE = "used"

class JSONDatabase:
    def __init__(self, db_file="servers_database.json"):
        self.db_file = db_file
        self._lock = threading.RLock()
        self._ensure_db_exists()
    
    def _ensure_db_exists(self):
        with self._lock:
            if not os.path.exists(self.db_file):
                default_data = {
                    "free_servers": [],
                    "used_servers": []
                }
                self._save_data(default_data)
    
    def _load_data(self) -> Dict:
        with self._lock:
            try:
                with open(self.db_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Ошибка загрузки БД: {e}")
                return {"free_servers": [], "used_servers": []}
    
    def _save_data(self, data: Dict):
        with self._lock:
            try:
                with open(self.db_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"Ошибка сохранения БД: {e}")
    
    def add_free_server(self, configure_url: str, invite_link: str):
        with self._lock:
            data = self._load_data()
            
            # делит
            data["used_servers"] = [s for s in data["used_servers"] if s["configure_url"] != configure_url]
            
            # адд ту фри
            if not any(s["configure_url"] == configure_url for s in data["free_servers"]):
                data["free_servers"].append({
                    "configure_url": configure_url,
                    "invite_link": invite_link,
                    "added_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
            
            self._save_data(data)
    
    def add_used_server(self, configure_url: str, invite_link: str, hours_to_wait: int):
        with self._lock:
            data = self._load_data()
            
            # делит
            data["free_servers"] = [s for s in data["free_servers"] if s["configure_url"] != configure_url]
            
            # адд ту юз
            occupied_at = datetime.now()
            free_at = occupied_at + timedelta(hours=hours_to_wait)
            
            data["used_servers"].append({
                "configure_url": configure_url,
                "invite_link": invite_link,
                "occupied_at": occupied_at.strftime('%Y-%m-%d %H:%M:%S'),
                "free_at": free_at.strftime('%Y-%m-%d %H:%M:%S'),
                "hours_to_wait": hours_to_wait
            })
            
            self._save_data(data)
    
    def get_free_servers_queue(self) -> List[Dict]:
        with self._lock:
            data = self._load_data()
            return data["free_servers"]
    
        with self._lock:
            data = self._load_data()
            return data["used_servers"]
    
    def pop_free_server(self) -> Optional[Dict]:
        with self._lock:
            data = self._load_data()
            
            if data["free_servers"]:
                server = data["free_servers"].pop(0)
                self._save_data(data)
                return server
            return None
    
    def check_and_free_expired_servers(self, roblox_service) -> List[Dict]:
        with self._lock:
            data = self._load_data()
            now = datetime.now()
            freed_servers = []
            
            for server in data["used_servers"][:]:
                free_at = datetime.strptime(server["free_at"], '%Y-%m-%d %H:%M:%S')
                
                if now >= free_at:
                    print(f"Время ожидания истекло для {server['configure_url']}")
                    
                    try:
                        # реген
                        new_invite_link = roblox_service.regenerate_link(server["configure_url"])
                        
                        # адд ту юз
                        data["free_servers"].append({
                            "configure_url": server["configure_url"],
                            "invite_link": new_invite_link,
                            "added_at": now.strftime('%Y-%m-%d %H:%M:%S')
                        })
                        
                        freed_servers.append({
                            "configure_url": server["configure_url"],
                            "old_invite_link": server["invite_link"],
                            "new_invite_link": new_invite_link
                        })
                        
                        # делит фром юз
                        data["used_servers"].remove(server)
                        print(f"Сервер освобожден: {new_invite_link}")
                        
                    except Exception as e:
                        print(f"Ошибка регенерации ссылки для {server['configure_url']}: {e}")
            
            if freed_servers:
                self._save_data(data)
            
            return freed_servers

class FreeServersQueue:
    
    def __init__(self, database: JSONDatabase):
        self.db = database
    
    def add_server(self, configure_url: str, invite_link: str):
        self.db.add_free_server(configure_url, invite_link)
    
    def get_next_server(self) -> Optional[Dict]:
        return self.db.pop_free_server()
    
    def get_queue_length(self) -> int:
        return len(self.db.get_free_servers_queue())
    
    def get_all_servers(self) -> List[Dict]:
        return self.db.get_free_servers_queue()

class UsedServersService:
    
    def __init__(self, database: JSONDatabase, roblox_service):
        self.db = database
        self.roblox_service = roblox_service
    
    def occupy_server(self, configure_url: str, invite_link: str, hours_to_wait: int):
        self.db.add_used_server(configure_url, invite_link, hours_to_wait)
        print(f"Сервер занят на {hours_to_wait} часов: {configure_url}")
    
    def check_timers(self) -> List[Dict]:
        return self.db.check_and_free_expired_servers(self.roblox_service)
    
    def get_used_servers(self) -> List[Dict]:
        return self.db.get_used_servers()
    
    def get_used_servers_count(self) -> int:
        return len(self.db.get_used_servers())

class ServerAcquisitionThread(threading.Thread):
    
    def __init__(self, roblox_service, servers_file: str, free_queue: FreeServersQueue, 
                 used_service: UsedServersService, check_interval: int = 600): 
        super().__init__()
        self.roblox_service = roblox_service
        self.servers_file = servers_file
        self.free_queue = free_queue
        self.used_service = used_service 
        self.check_interval = check_interval
        self._stop_event = threading.Event()
        self.daemon = True
    
    def stop(self):
        self._stop_event.set()
    
    def run(self):
        print("Запущен поток получения серверов")
        
        while not self._stop_event.is_set():
            try:
                self._acquire_servers()
                
                # таймаут
                for _ in range(self.check_interval):
                    if self._stop_event.is_set():
                        break
                    time.sleep(1)
                    
            except Exception as e:
                print(f"Ошибка в потоке получения серверов: {e}")
                time.sleep(60)
    
    def _acquire_servers(self):
        if not os.path.exists(self.servers_file):
            print(f"Файл {self.servers_file} не найден")
            return
        
        with open(self.servers_file, 'r', encoding='utf-8') as f:
            servers = [line.strip() for line in f if line.strip()]
        
        print(f"Проверяем {len(servers)} серверов из файла...")
        
        for server_url in servers:
            if self._stop_event.is_set():
                break
                
            in_free = any(s["configure_url"] == server_url for s in self.free_queue.get_all_servers())
            in_used = any(s["configure_url"] == server_url for s in self.used_service.get_used_servers())
            
            if not in_free and not in_used:
                try:
                    print(f"Добавляем новый сервер: {server_url}")
                    # реген
                    new_link = self.roblox_service.regenerate_link(server_url)
                    self.free_queue.add_server(server_url, new_link)
                    print(f"Добавлен в свободные: {server_url}")
                    
                    if hasattr(self.free_queue, 'db') and hasattr(self.free_queue.db, 'funpay_service'):
                        free_count = self.free_queue.get_queue_length()
                        self.free_queue.db.funpay_service.update_lots_stock(free_count)
                    
                    time.sleep(0.1)
                    
                except Exception as e:
                    print(f"Ошибка добавления сервера {server_url}: {e}")

class TimerCheckThread(threading.Thread):
    
    def __init__(self, used_service: UsedServersService, servers_manager, check_interval: int = 60): 
        super().__init__()
        self.used_service = used_service
        self.check_interval = check_interval
        self.servers_manager = servers_manager 
        self._stop_event = threading.Event()
        self.daemon = True
    
    def stop(self):
        self._stop_event.set()
    
    def run(self):
        print("Запущен поток проверки таймеров")
        
        while not self._stop_event.is_set():
            try:
                freed_servers = self.used_service.check_timers()
                if freed_servers:
                    print(f"Освобождено серверов: {len(freed_servers)}")
                    self.servers_manager.check_waiting_queue()
                
                # таймаут
                for _ in range(self.check_interval):
                    if self._stop_event.is_set():
                        break
                    time.sleep(1)
                    
            except Exception as e:
                print(f"Ошибка в потоке проверки таймеров: {e}")
                time.sleep(60)

class ServersManager:
    def __init__(self, roblox_service, db_file="servers_database.json", funpay_service=None):
        self.db = JSONDatabase(db_file)
        self.free_queue = FreeServersQueue(self.db)
        self.used_service = UsedServersService(self.db, roblox_service)
        self.roblox_service = roblox_service
        self.funpay_service = funpay_service 

        self.waiting_queue = []
        self.waiting_lock = threading.Lock()
        
        # потоки
        self.acquisition_thread = None
        self.timer_thread = None
    
    def start_background_threads(self, servers_file: str):
        # гет фром текст
        self.acquisition_thread = ServerAcquisitionThread(
            self.roblox_service, servers_file, self.free_queue, self.used_service, check_interval=600
        )
        
        # потоу таймеров
        self.timer_thread = TimerCheckThread(
            self.used_service, self, check_interval=100
        )
        
        self.acquisition_thread.start()
        self.timer_thread.start()
        print("Фоновые потоки запущены")
    
    def stop_background_threads(self):
        if self.acquisition_thread:
            self.acquisition_thread.stop()
        if self.timer_thread:
            self.timer_thread.stop()
        print("Фоновые потоки остановлены")
    
    def initialize_from_file(self, servers_file: str):
        if not os.path.exists(servers_file):
            print(f"Файл {servers_file} не найден")
            return
        
        with open(servers_file, 'r', encoding='utf-8') as f:
            servers = [line.strip() for line in f if line.strip()]
        
        for server_url in servers:
            # проверка в бд
            in_free = any(s["configure_url"] == server_url for s in self.free_queue.get_all_servers())
            in_used = any(s["configure_url"] == server_url for s in self.used_service.get_used_servers())
            for s in self.used_service.get_used_servers():
                print(f"{s["configure_url"]} == {server_url}")
            
            if not in_free and not in_used:
                try:
                    # редженери
                    new_link = self.roblox_service.regenerate_link(server_url)
                    self.free_queue.add_server(server_url, new_link)
                    print(f"Добавлен в свободные: {server_url}")
                    time.sleep(0.1)
                except Exception as e:
                    print(f"Ошибка инициализации сервера {server_url}: {e}")
    
    def get_free_server(self) -> Optional[Dict]:
        server = self.free_queue.get_next_server()
        if server and self.funpay_service:
            # Обновляем лоты после взятия сервера
            self._update_funpay_lots()
        return server
    
    def return_server_to_used(self, configure_url: str, invite_link: str, hours: int):
        self.used_service.occupy_server(configure_url, invite_link, hours)
        if self.funpay_service:
            # Обновляем лоты после возврата сервера
            self._update_funpay_lots()
    
    def _update_funpay_lots(self):
        try:
            free_count = self.free_queue.get_queue_length()
            if hasattr(self.funpay_service, 'update_lots_stock'):
                self.funpay_service.update_lots_stock(free_count)
        except Exception as e:
            print(f"Ошибка при обновлении лотов FunPay: {e}")

    def run_timer_check(self):
        return self.used_service.check_timers()
    
    def get_stats(self) -> Dict:
        return {
            "free_servers": self.free_queue.get_queue_length(),
            "used_servers": self.used_service.get_used_servers_count(),
            "total_servers": self.free_queue.get_queue_length() + self.used_service.get_used_servers_count()
        }
    
    def wait_for_free_servers(self, timeout: int = 60) -> Optional[Dict]:
        start_time = time.time()
        while time.time() - start_time < timeout:
            server = self.get_free_server()
            if server:
                return server
            time.sleep(1)
        return None
    
    def add_to_waiting_queue(self, buyer_username: str, order_data: dict, hours_to_rent: int):
        with self.waiting_lock:
            self.waiting_queue.append({
                "buyer_username": buyer_username,
                "order_data": order_data,
                "hours_to_rent": hours_to_rent,
                "added_time": time.time(),
                "position": len(self.waiting_queue) + 1
            })
        print(f"Пользователь {buyer_username} добавлен в очередь ожидания (позиция: {len(self.waiting_queue)})")

    def remove_from_waiting_queue(self, buyer_username: str, order_id: str) -> bool:
        with self.waiting_lock:
            for i, item in enumerate(self.waiting_queue):
                if (item["buyer_username"] == buyer_username and 
                    item["order_data"]["order_id"] == order_id):
                    self.waiting_queue.pop(i)
                    for j, remaining_item in enumerate(self.waiting_queue[i:], i):
                        remaining_item["position"] = j + 1
                    print(f"Пользователь {buyer_username} удален из очереди ожидания")
                    return True
        return False

    def get_next_free_time(self) -> Optional[float]:
        used_servers = self.used_service.get_used_servers()
        if not used_servers:
            return None
            
        nearest_time = None
        for server in used_servers:
            free_at = datetime.strptime(server["free_at"], '%Y-%m-%d %H:%M:%S')
            free_timestamp = free_at.timestamp()
            
            if nearest_time is None or free_timestamp < nearest_time:
                nearest_time = free_timestamp
                
        return nearest_time

    def check_waiting_queue(self):
        free_server = self.free_queue.get_next_server()
        if not free_server or not self.waiting_queue:
            if free_server:
                self.free_queue.add_server(free_server["configure_url"], free_server["invite_link"])
            return
        
        with self.waiting_lock:
            if self.waiting_queue:
                waiting_user = self.waiting_queue.pop(0)
                
                for i, item in enumerate(self.waiting_queue):
                    item["position"] = i + 1
                
                try:
                    message = self._create_success_after_wait_message(
                        free_server["invite_link"], 
                        waiting_user["hours_to_rent"]
                    )
                    
                    if self.funpay_service:
                        self.funpay_service.send_message(
                            waiting_user["buyer_username"], 
                            message
                        )
                    
                    # Занимаем сервер
                    self.used_service.occupy_server(
                        free_server["configure_url"],
                        free_server["invite_link"],
                        waiting_user["hours_to_rent"]
                    )
                    
                    print(f"Сервер выдан пользователю {waiting_user['buyer_username']} из очереди ожидания")
                    
                except Exception as e:
                    print(f"Ошибка выдачи сервера из очереди: {e}")
                    self.waiting_queue.insert(0, waiting_user)
                    self.free_queue.add_server(free_server["configure_url"], free_server["invite_link"])

    def get_waiting_position(self, buyer_username: str, order_id: str) -> Optional[int]:
        with self.waiting_lock:
            for item in self.waiting_queue:
                if (item["buyer_username"] == buyer_username and 
                    item["order_data"]["order_id"] == order_id):
                    return item["position"]
        return None

    def _create_success_after_wait_message(self, invite_link: str, hours: int) -> str:
        return f"""✅ Ваш сервер готов после ожидания!

🔗 Ссылка для присоединения: {invite_link}

⏰ Время аренды: {hours} часов (таймер запущен)

Спасибо за ожидание! Приятной игры! 🎮"""

    def get_waiting_queue_length(self) -> int:
        with self.waiting_lock:
            return len(self.waiting_queue)

    def check_waiting_queue(self):
        free_server = self.free_queue.get_next_server()
        if not free_server:
            return
        
        with self.waiting_lock:
            if self.waiting_queue:
                waiting_user = self.waiting_queue.pop(0)

                for i, item in enumerate(self.waiting_queue):
                    item["position"] = i + 1
                
                try:
                    message = self._create_success_after_wait_message(
                        free_server["invite_link"], 
                        waiting_user["hours_to_rent"]
                    )
                    
                    if self.funpay_service:
                        self.funpay_service.send_message(
                            waiting_user["buyer_username"], 
                            message
                        )
                    
                    self.used_service.occupy_server(
                        free_server["configure_url"],
                        free_server["invite_link"],
                        waiting_user["hours_to_rent"]
                    )
                    
                    print(f"Сервер выдан пользователю {waiting_user['buyer_username']} из очереди ожидания")
                    
                except Exception as e:
                    print(f"Ошибка выдачи сервера из очереди: {e}")
                    self.waiting_queue.insert(0, waiting_user)
                    self.free_queue.add_server(free_server["configure_url"], free_server["invite_link"])
            else:
                self.free_queue.add_server(free_server["configure_url"], free_server["invite_link"])
                
