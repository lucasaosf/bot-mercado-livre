@echo off
title Bot de Ofertas Mercado Livre (Afiliado)
cd /d "%~dp0"
echo ==========================================================
echo   BOT DE OFERTAS MERCADO LIVRE - INICIANDO EXECUCAO
echo ==========================================================
echo.
python bot.py --loop
pause
