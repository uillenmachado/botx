#!/bin/bash
# Instala o Caco Daemon como serviço systemd

set -e

echo "🎭 Instalando Caco Fakessen Daemon..."

# Copiar service file
sudo cp caco.service /etc/systemd/system/

# Recarregar systemd
sudo systemctl daemon-reload

# Habilitar para iniciar no boot
sudo systemctl enable caco

# Iniciar
sudo systemctl start caco

# Status
echo ""
echo "✅ Serviço instalado!"
echo ""
sudo systemctl status caco --no-pager

echo ""
echo "📋 Comandos úteis:"
echo "   sudo systemctl status caco    # Ver status"
echo "   sudo systemctl stop caco      # Parar"
echo "   sudo systemctl start caco     # Iniciar"
echo "   sudo systemctl restart caco   # Reiniciar"
echo "   journalctl -u caco -f         # Ver logs em tempo real"
echo "   tail -f logs/caco_daemon.log  # Ver logs do bot"
