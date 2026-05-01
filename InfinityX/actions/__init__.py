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
from .percepcao import (
    action_descrever_imagem,
    action_ouvir,
    action_ouvir_e_responder,
    action_ver,
)
from .lastfm import (
    action_lastfm_artist_info,
    action_lastfm_logout,
    action_lastfm_now_playing,
    action_lastfm_now_playing_set,
    action_lastfm_recent,
    action_lastfm_scrobble,
    action_lastfm_setup,
    action_lastfm_similar_artist,
    action_lastfm_similar_track,
    action_lastfm_top,
)
from .musica import (
    action_media_mute,
    action_media_next,
    action_media_play_pause,
    action_media_previous,
    action_media_stop,
    action_media_volume_down,
    action_media_volume_up,
    action_youtube_music_shuffle,
    action_yt_music_artist,
    action_yt_music_play,
    action_yt_music_playlist,
    action_yt_music_radio,
    action_yt_music_recommendations,
    action_yt_music_search,
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
    get_localizacao_atual,
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
)
