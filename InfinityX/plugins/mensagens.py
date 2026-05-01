"""Plugin de Automação de Mensagens para a InfinityX.

Permite enviar mensagens no Discord (App) e em plataformas Web.
"""

import time
import actions

def plugin_enviar_discord(contacto: str, mensagem: str) -> str:
    """Automatiza o envio de uma mensagem no Discord (App Desktop)."""
    try:
        # 1. Abrir/Focar no Discord
        actions.action_abrir("discord")
        time.sleep(3) # Espera a app carregar/focar
        
        # 2. Usar atalho de procura rápida (Quick Switcher: Ctrl+K)
        actions.action_press_key("ctrl+k")
        time.sleep(1)
        
        # 3. Digitar o nome do contacto
        actions.action_type_text(contacto)
        time.sleep(1)
        
        # 4. Pressionar Enter para selecionar o contacto
        actions.action_press_key("enter")
        time.sleep(1)
        
        # 5. Digitar a mensagem
        actions.action_type_text(mensagem)
        time.sleep(0.5)
        
        # 6. Enviar
        actions.action_press_key("enter")
        time.sleep(1)
        
        # 7. Verificação Visual
        actions.action_screenshot("confirmacao_discord.png")
        verificacao = actions.action_descrever_imagem("data/confirmacao_discord.png", "A mensagem para " + contacto + " foi enviada com sucesso no Discord? Responde apenas Sim ou Não e o porquê.")
        
        return f"✅ Mensagem enviada para '{contacto}' no Discord.\n🔍 Verificação: {verificacao}"
    except Exception as e:
        return f"❌ Erro ao enviar mensagem no Discord: {e}"

def plugin_enviar_whatsapp_web(contacto: str, mensagem: str) -> str:
    """Automatiza o envio de uma mensagem no WhatsApp Web via Browser."""
    try:
        url = f"https://web.whatsapp.com/send?phone={contacto}&text={mensagem}"
        # Nota: Requer que o utilizador já esteja logado no browser padrão
        actions.action_abrir_url(url)
        time.sleep(10) # Espera o WhatsApp Web carregar
        
        # Pressionar Enter para enviar (o URL já preenche o texto)
        actions.action_press_key("enter")
        time.sleep(2)
        
        # Verificação Visual
        actions.action_screenshot("confirmacao_whatsapp.png")
        verificacao = actions.action_descrever_imagem("data/confirmacao_whatsapp.png", "A mensagem para " + contacto + " aparece como enviada no WhatsApp Web?")
        
        return f"✅ Tentativa de envio para '{contacto}' via WhatsApp Web.\n🔍 Verificação: {verificacao}"
    except Exception as e:
        return f"❌ Erro ao enviar via WhatsApp Web: {e}"
