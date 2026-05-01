"""Ações de automação avançada: execução de código e automação de browser."""

import sys
import io
import contextlib
from typing import Any, Dict

def action_executar_codigo(codigo: str) -> str:
    """Executa código Python de forma controlada e retorna o output.
    
    Esta ferramenta dá à Infinity a liberdade de resolver problemas complexos
    através de programação dinâmica.
    """
    if not codigo:
        return "❌ Nenhum código fornecido para execução."

    # Captura o stdout para retornar o resultado ao utilizador
    stdout = io.StringIO()
    
    # Define um ambiente restrito para execução
    # Nota: Em produção, isto deveria ser ainda mais isolado (ex: Docker ou multiprocessing)
    locais: Dict[str, Any] = {}
    
    try:
        with contextlib.redirect_stdout(stdout):
            # Executa o código
            exec(codigo, {"__builtins__": __builtins__}, locais)
        
        output = stdout.getvalue()
        
        # Se houver variáveis definidas, podemos incluí-las no resumo (opcional)
        if not output and locais:
            resumo_vars = ", ".join([f"{k}={v}" for k, v in locais.items() if not k.startswith("__")])
            return f"✅ Código executado com sucesso. Variáveis: {resumo_vars}"
            
        return output if output else "✅ Código executado (sem output)."
        
    except Exception as e:
        return f"❌ Erro na execução do código: {e}"

def action_browser_automation(url: str, script: str = None) -> str:
    """Base para automação de browser usando Selenium."""
    from config import SELENIUM_AVAILABLE
    
    if not SELENIUM_AVAILABLE:
        return "❌ Selenium não está disponível. Instala 'selenium' e o respetivo webdriver."
    
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        
        chrome_options = Options()
        chrome_options.add_argument("--headless") # Execução em background
        
        # Nota: Requer que o utilizador tenha o ChromeDriver instalado
        driver = webdriver.Chrome(options=chrome_options)
        
        try:
            driver.get(url)
            if script:
                # Permite que a IA execute JavaScript na página
                result = driver.execute_script(script)
                return f"🌐 Browser: {url}\nResultado do script: {result}"
            
            # Se não houver script, apenas retorna o título e um resumo do texto
            title = driver.title
            text = driver.find_element("tag name", "body").text[:500]
            return f"🌐 Browser: {title} ({url})\nConteúdo inicial: {text}..."
            
        finally:
            driver.quit()
            
    except Exception as e:
        return f"❌ Erro na automação de browser: {e}"

def action_indexar_ficheiro(path: str) -> str:
    """Indexa o conteúdo de um ficheiro na memória de longo prazo."""
    from rag import indexar_ficheiro
    return indexar_ficheiro(path)
