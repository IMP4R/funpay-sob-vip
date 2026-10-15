import sys
import os
import subprocess

def main():
    
    try:
        from FunPayBot import FunPayBot
        bot = FunPayBot()
        
        if bot.initialize():
            bot.run()
        else:
            print("Ошибка инициализации бота")
        
    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()