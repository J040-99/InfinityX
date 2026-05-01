"""Sistema de Plugins Dinâmicos para a InfinityX.

Permite carregar e executar ferramentas externas sem alterar o núcleo do sistema.
"""

import os
import importlib.util
from pathlib import Path
from typing import Dict, Callable

PLUGINS_DIR = Path("/home/ubuntu/InfinityX/InfinityX/plugins")

# Dicionário global de plugins carregados
PLUGINS: Dict[str, Callable] = {}

def carregar_plugins():
    """Carrega todos os plugins da pasta plugins/."""
    global PLUGINS
    if not PLUGINS_DIR.exists():
        PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
        return

    for f in PLUGINS_DIR.glob("*.py"):
        if f.name == "__init__.py":
            continue
        
        try:
            spec = importlib.util.spec_from_file_location(f.stem, f)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Procura por funções que começam com 'plugin_'
            for attr in dir(module):
                if attr.startswith("plugin_"):
                    func = getattr(module, attr)
                    if callable(func):
                        plugin_name = attr.replace("plugin_", "")
                        PLUGINS[plugin_name] = func
                        print(f"[PLUGINS] Carregado: {plugin_name}")
        except Exception as e:
            print(f"[PLUGINS] Erro ao carregar {f.name}: {e}")

def executar_plugin(nome: str, **kwargs) -> str:
    """Executa um plugin carregado."""
    if nome not in PLUGINS:
        return f"❌ Plugin '{nome}' não encontrado."
    
    try:
        return PLUGINS[nome](**kwargs)
    except Exception as e:
        return f"❌ Erro ao executar plugin '{nome}': {e}"
