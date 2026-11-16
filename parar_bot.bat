@echo off
title Parar Bot de Ofertas
echo Encerrando o bot de ofertas...
python -c "import psutil, os; my_pid = os.getpid(); [p.kill() for p in psutil.process_iter() if 'bot.py' in ' '.join(p.cmdline() or []) and p.pid != my_pid]"
echo Bot encerrado com sucesso!
pause
