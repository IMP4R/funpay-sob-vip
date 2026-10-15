from FunPayAPI import Account, Runner, types, enums
import threading
import queue
import time
import os
from typing import Dict, Optional


class FunPayService:
    def __init__(self, token_file: str = "FUNPAY_TOKEN.txt", 
                 subcategory_type=None, subcategory_id=None, credentials_file=None):
        self.token_file = token_file 
        self.token = self._read_token()
        self.account = Account(self.token).get()
        self.runner = Runner(self.account)
        self.credentials_file = credentials_file

        self.subcategory_type = subcategory_type
        self.subcategory_id = subcategory_id
        
        # очереди
        self.orders_queue = queue.Queue()  # очередь заказов
        self.messages_queue = queue.Queue()  # очередь сообщений
        self.messages_receive_queue = queue.Queue()
        
        # потоки
        self.listener_thread = None
        self.sender_thread = None
        self._stop_event = threading.Event()
        
        # статистика
        self.stats = {
            "orders_received": 0,
            "messages_sent": 0,
            "errors": 0
        }
    
    def _read_token(self) -> str:
        if not os.path.exists(self.token_file):
            raise FileNotFoundError(f"Файл {self.token_file} не найден")
        
        with open(self.token_file, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
        
        if not lines:
            raise ValueError(f"Файл {self.token_file} пустой")
        
        return lines[0]
    
    def _event_listener(self):
            print("Запущен поток прослушивания событий FunPay")
            
            while not self._stop_event.is_set():
                try:
                    for event in self.runner.listen(requests_delay=4):
                        if self._stop_event.is_set():
                            break
                        
                        if event.type is enums.EventTypes.NEW_ORDER:
                            skip = True
                            if not os.path.exists(self.credentials_file):
                                raise FileNotFoundError(f"Файл {self.credentials_file} не найден")
                            with open(self.credentials_file, 'r', encoding='utf-8') as f:
                                lines = [line.strip() for line in f.readlines() if line.strip()]
                            for line in lines:
                                if self.account.get_user(self.account.id).get_lot(line).description in event.order.description: 
                                    skip=False
                            if skip == True: 
                                continue
                            
                            self.stats["orders_received"] += 1
                            print(f"Получен новый заказ от {event.order.buyer_username}")
                            
                            order_data = {
                                "order_id": event.order.id,
                                "buyer_username": event.order.buyer_username,
                                "description": event.order.description,
                                "price": event.order.price,
                                "amount": event.order.parse_amount(),
                                "timestamp": time.time()
                            }
                            self.orders_queue.put(order_data)
                        
                        elif event.type is enums.EventTypes.NEW_MESSAGE:
                            message_data = {
                                "buyer_username": event.message.author,
                                "text": event.message.text,
                                "timestamp": time.time()
                            }
                            print(f"Получено сообщение от {event.message.author}: {event.message.text}")
                            self.messages_receive_queue.put(message_data)
                            
                except Exception as e:
                    self.stats["errors"] += 1
                    print(f"Ошибка в потоке прослушивания: {e}")
                    time.sleep(1)
    
    def get_message(self, timeout: int = 1) -> Optional[Dict]:
        try:
            return self.messages_receive_queue.get(timeout=timeout)
        except queue.Empty:
            return None
         
    def _message_sender(self):
        print("Запущен поток отправки сообщений")
        
        while not self._stop_event.is_set():
            try:
                try:
                    message_data = self.messages_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                
                self.stats["messages_sent"] += 1
                print(f"Отправлено сообщение пользователю {message_data['buyer_username']}")
                self.messages_queue.task_done()

                chat = self.account.get_chat_by_name(message_data["buyer_username"], True)
                try:
                    self.account.send_message(chat.id, message_data["message"])
                except:
                    continue
                
                
            except Exception as e:
                self.stats["errors"] += 1
                print(f"Ошибка отправки сообщения: {e}")
                #if 'message_data' in locals():
                    #self.messages_queue.put(message_data)
                time.sleep(1)
    
    def start(self):
        if self.listener_thread is None or not self.listener_thread.is_alive():
            self.listener_thread = threading.Thread(target=self._event_listener, daemon=True)
            self.listener_thread.start()
        
        if self.sender_thread is None or not self.sender_thread.is_alive():
            self.sender_thread = threading.Thread(target=self._message_sender, daemon=True)
            self.sender_thread.start()
        
        print("FunPayService запущен")
    
    def stop(self):
        self._stop_event.set()
        print("FunPayService остановлен")
    
    def get_order(self, timeout: int = 1) -> Optional[Dict]:
        try:
            return self.orders_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def send_message(self, buyer_username: str, message: str):
        message_data = {
            "buyer_username": buyer_username,
            "message": message,
            "timestamp": time.time()
        }
        self.messages_queue.put(message_data)
        print(f"Сообщение добавлено в очередь для {buyer_username}")
    
    def get_stats(self) -> Dict:
        return {
            "orders_received": self.stats["orders_received"],
            "messages_sent": self.stats["messages_sent"],
            "errors": self.stats["errors"],
            "orders_in_queue": self.orders_queue.qsize(),
            "messages_in_queue": self.messages_queue.qsize()
        }
    
    def wait_for_order(self, timeout: int = 1) -> Optional[Dict]:
        start_time = time.time()
        while time.time() - start_time < timeout:
            order = self.get_order(timeout=0.2)
            if order:
                return order
        return None
    
    def update_lots_stock(self, free_servers_count: int):
        return
        if not self.subcategory_type or not self.subcategory_id:
            print("Не указаны subcategory_type и subcategory_id для обновления лотов")
            return
            
        try:
            if not os.path.exists(self.credentials_file):
                raise FileNotFoundError(f"Файл {self.credentials_file} не найден")
            with open(self.credentials_file, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
            for lot in lines:
                print(int(lot))
                lot_fields = self.account.get_lot_fields(int(lot))
                print(lot_fields.active)
                if free_servers_count == 0:
                    lot_fields.active = False
                    print(f"Лот {lot.id} деактивирован (нет свободных серверов)")
                else:
                    lot_fields.active = True
                    lot_fields.fields["amount"] = free_servers_count
                    print(f"Обновлен лот {lot.id}: активен, количество = {free_servers_count}")
                
                self.account.save_lot(lot_fields)
                
        except Exception as e:
            print(f"Ошибка при обновлении лоtов: {e}")
