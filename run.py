from app import app, init_bot, signal_handler
import signal
import sys

if __name__ == '__main__':
    # Регистрируем обработчик сигнала SIGINT (Ctrl+C)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        init_bot()
        print('Бот запущен. Нажмите Ctrl+C для завершения.')
        # Отключаем перезагрузчик, но оставляем режим отладки
        app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)
    except KeyboardInterrupt:
        print('\nПолучен сигнал завершения.')
        sys.exit(0) 