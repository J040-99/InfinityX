"""Pacote de ações do InfinityX, agrupadas por categoria.

Mantém a API antiga (`import actions; actions.action_X(...)`) através de
re-exportações abaixo. O parser e qualquer outro código que faça
`from actions import action_X` continuam a funcionar."""

from .arquivos import (
    action_cleanup_temp,
    action_criar_arquivo,
    action_file_info,
    action_listar,
    action_organizar,
    action_search_files,
)
from .midia import (
    action_clipboard_copy,
    action_clipboard_paste,
    action_click,
    action_press_key,
    action_speak,
    action_type_text,
    action_window_control,
)
from .produtividade import (
    action_lembrete_add,
    action_lembrete_excluir,
    action_lembretes_listar,
    action_nota_add,
    action_nota_excluir,
    action_notas_listar,
    action_palavras_aprender,
    action_palavras_excluir,
    action_palavras_listar,
    action_palavras_procurar,
    action_resumo_dia,
    action_timer_set,
    action_todo_add,
    action_todo_list,
    iniciar_scheduler_lembretes,
)
from .sistema import (
    action_battery_status,
    action_clima,
    action_disk_usage,
    action_hora,
    action_network_info,
    action_sysinfo,
)
from .util import (
    action_base64,
    action_bmi,
    action_color_convert,
    action_convert,
    action_currency_convert,
    action_generate_password,
    action_generate_qr,
    action_hash_text,
    action_json_format,
    action_lorem_ipsum,
    action_ping,
    action_random_dice,
    action_shorten_url,
    action_text_tools,
    action_translate,
    action_url_codec,
    action_uuid_gen,
)
from .web import (
    action_abrir,
    action_abrir_url,
    action_browser_search,
    action_crypto_price,
    action_noticias,
    action_public_ip,
    action_wikipedia,
    action_youtube_music_shuffle,
)
