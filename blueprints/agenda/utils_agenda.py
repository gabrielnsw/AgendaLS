import os
import json
import requests
from datetime import datetime

DATA_DIR = os.path.join("data", "agenda_monthly")
HISTORICO_DIR = os.path.join("data", "historico_monthly")
TYPES_FILE = os.path.join("data", "tipos.json")


def gerar_slots():
    return [
        "1º horário (Manhã)",
        "2º horário (Manhã)",
        "3º horário (Manhã)",
        "4º horário (Manhã)",
        "Intervalo 1",
        "Intervalo 2",
        "1º horário (Tarde)",
        "2º horário (Tarde)",
        "3º horário (Tarde)",
        "4º horário (Tarde)",
    ]


def get_agenda_file_path(date):
    filename = f"agenda_{date.year}_{date.month:02d}.json"
    return os.path.join(DATA_DIR, filename)


def carregar_agendamentos(dates):
    agendamentos = []
    meses = set((date.year, date.month) for date in dates)
    for year, month in meses:
        date = datetime(year=year, month=month, day=1)
        file_path = get_agenda_file_path(date)
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                try:
                    agendamentos.extend(json.load(f))
                except json.JSONDecodeError:
                    pass
    return agendamentos


def salvar_agendamentos(agendamento):
    date_obj = datetime.strptime(agendamento["data"], "%Y-%m-%d")
    file_path = get_agenda_file_path(date_obj)
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                lista = json.load(f)
            except json.JSONDecodeError:
                lista = []
    else:
        lista = []
    # Remove se já existir
    lista = [ag for ag in lista if ag["id"] != agendamento["id"]]
    lista.append(agendamento)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(lista, f, indent=4, ensure_ascii=False)


def verificar_feriado(data):
    try:
        ano = data.year
        cache_dir = os.path.join("data", "feriados_cache")
        os.makedirs(cache_dir, exist_ok=True)
        cache_file = os.path.join(cache_dir, f"feriados_{ano}.json")
        if os.path.exists(cache_file):
            with open(cache_file, "r", encoding="utf-8") as f:
                feriados = json.load(f)
        else:
            url = f"https://brasilapi.com.br/api/feriados/v1/{ano}"
            response = requests.get(url)
            if response.status_code == 200:
                feriados = response.json()
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(feriados, f, indent=4, ensure_ascii=False)
            else:
                return False
        data_str = data.strftime("%Y-%m-%d")
        for feriado in feriados:
            if feriado.get("date") == data_str:
                return True
        return False
    except:
        return False


def obter_diferencas(dados_antigos, dados_novos):
    diferencas = {}
    for chave in ["ordem_servico", "data", "tipo", "categoria"]:
        if dados_antigos.get(chave) != dados_novos.get(chave):
            diferencas[chave] = {
                "antigo": dados_antigos.get(chave),
                "novo": dados_novos.get(chave),
            }
    old_slots = dados_antigos.get("slots_ocupados", [])
    new_slots = dados_novos.get("slots_ocupados", [])
    if old_slots != new_slots:
        diferencas["slots_ocupados"] = {
            "antigo": ", ".join(old_slots),
            "novo": ", ".join(new_slots),
        }
    return diferencas


def get_historico_file_path(dt=None):
    if dt is None:
        dt = datetime.now()
    filename = f"historico_{dt.year}_{dt.month:02d}.json"
    return os.path.join(HISTORICO_DIR, filename)


def salvar_no_historico_global(agendamento_id, ordem_servico, historico_entry):
    os.makedirs(HISTORICO_DIR, exist_ok=True)
    file_path = get_historico_file_path()
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                hist_lista = json.load(f)
            except json.JSONDecodeError:
                hist_lista = []
    else:
        hist_lista = []
    entry = {
        "agendamento_id": agendamento_id,
        "ordem_servico": ordem_servico,
        **historico_entry,
    }
    hist_lista.append(entry)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(hist_lista, f, indent=4, ensure_ascii=False)


def carregar_todos_historicos():
    os.makedirs(HISTORICO_DIR, exist_ok=True)
    all_entries = []
    for fname in os.listdir(HISTORICO_DIR):
        if fname.startswith("historico_") and fname.endswith(".json"):
            path = os.path.join(HISTORICO_DIR, fname)
            with open(path, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                    all_entries.extend(data)
                except json.JSONDecodeError:
                    pass

    def _dt_sort(e):
        return e.get("data_hora", "")
    all_entries.sort(key=_dt_sort, reverse=True)
    return all_entries


def encontrar_agendamento_por_id(ag_id):
    for filename in os.listdir(DATA_DIR):
        if filename.startswith("agenda_") and filename.endswith(".json"):
            file_path = os.path.join(DATA_DIR, filename)
            with open(file_path, "r", encoding="utf-8") as f:
                try:
                    ags = json.load(f)
                    for ag in ags:
                        if ag["id"] == ag_id:
                            return ag, file_path
                except:
                    pass
    return None, None


def load_tipos():
    if not os.path.exists(TYPES_FILE):
        return {}
    try:
        with open(TYPES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)  # dicionário nome->qtd
    except:
        return {}


def save_tipos(tipos_dict):
    os.makedirs(os.path.dirname(TYPES_FILE), exist_ok=True)
    with open(TYPES_FILE, "w", encoding="utf-8") as f:
        json.dump(tipos_dict, f, indent=4, ensure_ascii=False)


def listar_meses_historico():
    """Retorna lista de (ano,mes) existentes no HISTORICO_DIR."""
    os.makedirs(HISTORICO_DIR, exist_ok=True)
    found = set()
    for fname in os.listdir(HISTORICO_DIR):
        if fname.startswith("historico_") and fname.endswith(".json"):
            # historico_2025_01.json
            parts = fname.replace("historico_", "").replace(
                ".json", "").split("_")
            if len(parts) == 2:
                try:
                    yr = int(parts[0])
                    mo = int(parts[1])
                    found.add((yr, mo))
                except:
                    pass
    return sorted(list(found))  # ex.: [(2025,1),(2025,2)]


def carregar_historico_mes(ano, mes):
    """Carrega um arquivo do mês/ano específico."""
    fname = f"historico_{ano}_{mes:02d}.json"
    path = os.path.join(HISTORICO_DIR, fname)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []


def load_aniversariantes():
    fpath = os.path.join("data", "aniversariantes.json")
    if not os.path.exists(fpath):
        return []
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []


def save_aniversariantes(aniversariantes):
    fpath = os.path.join("data", "aniversariantes.json")
    os.makedirs(os.path.dirname(fpath), exist_ok=True)
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(aniversariantes, f, indent=4, ensure_ascii=False)


def load_correcoes():
    fpath = os.path.join("data", "correcoes.json")
    if not os.path.exists(fpath):
        return {}
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def save_correcoes(correcoes):
    fpath = os.path.join("data", "correcoes.json")
    os.makedirs(os.path.dirname(fpath), exist_ok=True)
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(correcoes, f, indent=4, ensure_ascii=False)
