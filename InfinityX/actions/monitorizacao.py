"""Monitorização de eventos e condições para a InfinityX."""

import time
import threading
import actions

MONITORAMENTOS = {}

def action_monitorar_condicao(tipo: str, alvo: str, condicao: str, valor: float, acao: str) -> str:
    """Monitoriza uma condição e executa uma ação quando atingida.
    
    tipo: 'crypto', 'clima', 'bateria'
    alvo: 'bitcoin', 'temperatura', 'percentagem'
    condicao: '>', '<', '=='
    valor: o valor limite
    acao: o comando a executar (ex: 'responder "A bateria está baixa!"')
    """
    
    def monitor_loop():
        print(f"👀 Iniciando monitorização: {alvo} {condicao} {valor}")
        while tipo in MONITORAMENTOS and alvo in MONITORAMENTOS[tipo]:
            try:
                valor_atual = 0.0
                if tipo == 'crypto':
                    res = actions.action_crypto_price(alvo)
                    # Extrair valor da string (ex: "Bitcoin: 50000.0 USD")
                    import re
                    match = re.search(r": ([\d.]+)", res)
                    if match:
                        valor_atual = float(match.group(1))
                
                elif tipo == 'bateria':
                    res = actions.action_battery_status()
                    match = re.search(r"(\d+)%", res)
                    if match:
                        valor_atual = float(match.group(1))
                
                # Verificar condição
                atingiu = False
                if condicao == '>' and valor_atual > valor: atingiu = True
                elif condicao == '<' and valor_atual < valor: atingiu = True
                elif condicao == '==' and valor_atual == valor: atingiu = True
                
                if atingiu:
                    print(f"🔔 CONDIÇÃO ATINGIDA: {alvo} {condicao} {valor} (Atual: {valor_atual})")
                    # Executar a ação (simulado)
                    print(f"🚀 Executando: {acao}")
                    break # Para após atingir (ou pode continuar se desejado)
                    
            except Exception as e:
                print(f"❌ Erro na monitorização: {e}")
            
            time.sleep(300) # Verifica a cada 5 minutos
            
    if tipo not in MONITORAMENTOS:
        MONITORAMENTOS[tipo] = {}
    
    MONITORAMENTOS[tipo][alvo] = True
    threading.Thread(target=monitor_loop, daemon=True).start()
    
    return f"👀 Monitorização ativada para {alvo} {condicao} {valor}. Vou avisar-te quando acontecer!"
