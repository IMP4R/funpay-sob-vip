from Services.FunPayService import FunPayService
from Services.ServersService import ServersManager
from Services.RobloxService import RobloxService
import time
import threading
import os
from typing import Optional

from FunPayAPI.types import SubCategoryTypes


class FunPayBot:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        
        self.funpay_service = FunPayService(
            token_file=os.path.join(self.base_dir, "FUNPAY_TOKEN.txt"),
            subcategory_type=SubCategoryTypes.COMMON, 
            subcategory_id=3503,
            credentials_file='ORDERS.txt'
        )
        
        self.roblox_service = RobloxService(
            headless=False, 
            credentials_file=os.path.join(self.base_dir, "ROBLOX_TOKEN.txt")
        )
        self.servers_manager = ServersManager(
            self.roblox_service,
            db_file=os.path.join(self.base_dir, "servers_database.json"),
            funpay_service=self.funpay_service  
        )
        
        self._stop_event = threading.Event()
    
    def initialize(self):
        print("Инициализация бота...")
        
        #print("Авторизация в Roblox...")
        #if not self.roblox_service.roblox_autorize():
        #    print("Ошибка авторизации в Roblox!")
        #    return False
        
        print("Инициализация серверов...")
        servers_file = os.path.join(self.base_dir, "Roblox_servers.txt")
        self.servers_manager.initialize_from_file(servers_file)
        
        print("Запуск фоновых потоков...")
        self.servers_manager.start_background_threads(servers_file)
        self.funpay_service.start()
        
        print("Бот успешно инициализирован!")
        return True
    
    def process_order(self, order_data: dict):
        try:
            buyer_username = order_data["buyer_username"]
            description = order_data["description"]
            amount = order_data["amount"]
            
            print(f"Обработка заказа от {buyer_username}: {description}")
            
            hours_to_rent = self._parse_order_description(description)
            if hours_to_rent is None:
                self.funpay_service.send_message(
                    buyer_username, 
                    "❌ Извините, не удалось определить тип заказа. Свяжитесь с поддержкой."
                )
                self.funpay_service.account.refund(order_data["order_id"])
                return
            
            free_servers = [self.servers_manager.get_free_server() for k in amount] 
            

            for free_server in free_servers:
                if free_server is None:
                    self._handle_no_servers(buyer_username, order_data, hours_to_rent)
                    return

            invite_links = ""
            for free_server in free_servers:
                invite_links += f"{free_server["invite_link"]}\n\n"
            
            message = self._create_success_message(invite_links, hours_to_rent)
            self.funpay_service.send_message(buyer_username, message)
            
            for free_server in free_servers:
                self.servers_manager.return_server_to_used(
                    free_server["configure_url"],
                    free_server["invite_link"],
                    hours_to_rent
                )
            
            print(f"Заказ от {buyer_username} успешно обработан!")
            
        except Exception as e:
            print(f"Ошибка обработки заказа: {e}")
            if 'buyer_username' in locals():
                self.funpay_service.send_message(
                    buyer_username,
                    "❌ Произошла ошибка при обработке заказа. Свяжитесь с поддержкой."
                )

    def _handle_no_servers(self, buyer_username: str, order_data: dict, hours_to_rent: int):
        next_free_time = self.servers_manager.get_next_free_time()
        
        if next_free_time:
            wait_time = next_free_time - time.time()
            if wait_time <= 36000: 
                wait_message = self._create_wait_message(wait_time, order_data["order_id"])
                self.funpay_service.send_message(buyer_username, wait_message)
                
                self.servers_manager.add_to_waiting_queue(buyer_username, order_data, hours_to_rent)
                return
        
        self.funpay_service.send_message(
            buyer_username,
            "⏳ Извините, в данный момент нет свободных серверов. Деньги возвращены."
        )
        self.funpay_service.account.refund(order_data["order_id"])

    def _create_wait_message(self, wait_seconds: float, order_id: str) -> str:
        wait_minutes = max(1, int(wait_seconds / 60))
        
        return f"""⏳ Серверы заняты, но скоро освободятся!

    🕐 Примерное время ожидания: ~{wait_minutes} минут
    📋 Ваша позиция в очереди: {self.servers_manager.get_waiting_queue_length()}

    Вы можете:
     Подождать - мы пришлем вам ссылку автоматически, как только сервер освободится
     Вернуть деньги - напишите «Отмена {order_id}»

    Сервер будет зарезервирован специально для вас после освобождения!"""

    def get_waiting_queue_length(self) -> int:
        with self.waiting_lock:
            return len(self.waiting_queue)
        
    def _create_success_after_wait_message(self, invite_link: str, hours: int) -> str:
        return f"""✅ Ваш сервер готов после ожидания!

    🔗 Ссылка для присоединения: {invite_link}

    ⏰ Время аренды: {hours} часов (таймер запущен)

    Спасибо за ожидание! Приятной игры! 🎮"""

    def _parse_order_description(self, description: str) -> Optional[int]:
        description_lower = description.lower()
        
        if "12 часов" in description_lower or "12 часов" in description:
            return 12
        elif "24 часа" in description_lower or "24 часа" in description:
            return 24
        elif "8 часов" in description_lower or "8 часов" in description:
            return 8
        elif "6 часов" in description_lower or "6 часов" in description:
            return 6
        elif "4 часа" in description_lower or "4 часа" in description:
            return 4
        elif "2 часа" in description_lower or "2 часа" in description:
            return 2
        elif "1 час" in description_lower or "1 час" in description:
            return 1
        else:
            import re
            hours_match = re.search(r'(\d+)\s*(час|часов|ч|hour|h|hours)', description_lower)
            if hours_match:
                return int(hours_match.group(1))
        
        return None
    
    def _create_success_message(self, invite_link: str, hours: int) -> str:
        return f"""✅ Ваш приватный сервер готов!

🔗 Ссылка для присоединения: {invite_link}

⏰ Время аренды: {hours} часов

📝 Инструкция:
1. Нажмите на ссылку выше
3. Наслаждайтесь игрой!

⚠️ Внимание: Сервер автоматически закроется через {hours} часов.

Если возникли проблемы - свяжитесь с поддержкой!"""
    
    def run(self):
        print("Запуск основного цикла бота...")
        
        while not self._stop_event.is_set():
            try:
                order = self.funpay_service.get_order(timeout=0.1)
                if order:
                    self.process_order(order)
                message = self.funpay_service.get_message(timeout=0.1)
                if message:
                    self.process_message(message)
                
                if int(time.time()) % 30 == 0:
                    self.servers_manager.check_waiting_queue()
                
                if int(time.time()) % 30 == 0:
                    self._print_statistics()
                
                time.sleep(2)
                
            except KeyboardInterrupt:
                print("\nОстановка по запросу пользователя...")
                break
            except Exception as e:
                print(f"Ошибка в основном цикле: {e}")
                time.sleep(1)
    
    def process_message(self, message_data: dict):
        try:
            text = message_data["text"].strip()
            buyer_username = message_data["buyer_username"]
            
            print(f"Обработка сообщения от {buyer_username}: {text}")
            
            if self._is_cancel_command(text):
                self._handle_cancel_command(buyer_username, text)
                
        except Exception as e:
            print(f"Ошибка обработки сообщения: {e}")
    
    def _is_cancel_command(self, text: str) -> bool:
        cancel_keywords = ["отмена", "вернуть", "возврат", "cancel", "refund"]
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in cancel_keywords)
    
    def _handle_cancel_command(self, buyer_username: str, text: str):
        try:
            order_id = self._extract_order_id(text)
            
            if not order_id:
                self.funpay_service.send_message(
                    buyer_username,
                    "❌ Не удалось определить номер заказа. Укажите номер заказа после команды отмены, например: 'Отмена 0'"
                )
                return
            
            position = self.servers_manager.get_waiting_position(buyer_username, order_id)
            
            if position is not None:
                if self.servers_manager.remove_from_waiting_queue(buyer_username, order_id):
                    self.funpay_service.account.refund(order_id)
                    self.funpay_service.send_message(
                        buyer_username,
                        f"✅ Заказ {order_id} отменен. Деньги возвращены."
                    )
                    print(f"Заказ {order_id} отменен пользователем {buyer_username} из очереди ожидания")
                else:
                    self.funpay_service.send_message(
                        buyer_username,
                        f"❌ Не удалось найти заказ {order_id} в очереди ожидания."
                    )
            else:
                self.funpay_service.send_message(
                    buyer_username,
                    f"❌ Заказ {order_id} не найден в очереди ожидания или уже обработан."
                )
                
        except Exception as e:
            print(f"Ошибка обработки команды отмены: {e}")
            self.funpay_service.send_message(
                buyer_username,
                "❌ Произошла ошибка при обработке команды отмены. Свяжитесь с поддержкой."
            )
    
    def _extract_order_id(self, text: str) -> Optional[str]:
        try:
            import re
            
            match = re.search(r'Отмена\s+(\S+)', text)
            if match:
                return match.group(1)
                
            return None
            
        except Exception as e:
            print(f"Ошибка извлечения order_id: {e}")
            return None
        
    def _print_statistics(self):
        funpay_stats = self.funpay_service.get_stats()
        servers_stats = self.servers_manager.get_stats()
        
        print(f"\n=== СТАТИСТИКА ===")
        print(f"FunPay: Заказов {funpay_stats['orders_received']}, "
              f"Сообщений {funpay_stats['messages_sent']}, "
              f"Ошибок {funpay_stats['errors']}")
        print(f"Серверы: Свободных {servers_stats['free_servers']}, "
              f"Занятых {servers_stats['used_servers']}, "
              f"Всего {servers_stats['total_servers']}")
        print(f"Очереди: Заказов {funpay_stats['orders_in_queue']}, "
              f"Сообщений {funpay_stats['messages_in_queue']}")
    
    def stop(self):
        print("Остановка бота...")
        self._stop_event.set()
        self.funpay_service.stop()
        self.servers_manager.stop_background_threads()
        self.roblox_service.driver.quit()
        print("Бот остановлен")


def main():
    bot = FunPayBot()
    
    try:
        if not bot.initialize():
            return
        
        bot.run()
        
    except KeyboardInterrupt:
        print("\nОстановка...")
    except Exception as e:
        print(f"Критическая ошибка: {e}")
    finally:
        bot.stop()


if __name__ == "__main__":
    main()
