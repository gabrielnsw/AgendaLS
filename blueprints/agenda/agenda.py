# blueprints/agenda/agenda.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, current_app
from flask_login import login_required, current_user
from datetime import datetime, timedelta
import locale
import json

from .utils_agenda import (
    carregar_agendamentos,
    salvar_agendamentos,
    verificar_feriado,
    obter_diferencas,
    salvar_no_historico_global,
    carregar_todos_historicos,
    encontrar_agendamento_por_id,
    gerar_slots,
    load_tipos,
    save_tipos,
    listar_meses_historico,
    carregar_historico_mes
)

agenda_bp = Blueprint("agenda_bp", __name__, template_folder="templates")

try:
    locale.setlocale(locale.LC_TIME, "pt_BR.UTF-8")
except locale.Error:
    locale.setlocale(locale.LC_TIME, "C.UTF-8")

nomes_dias_semana = [
    "Segunda-feira", "Terça-feira", "Quarta-feira",
    "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"
]

categorias = [
    "Nova Hartz - Araricá - Igrejinha",
    "OSs",
    "Infraestrutura",
    "Recolhimentos",
    "Três Coroas",
]


@agenda_bp.route("/", methods=["GET", "POST"])
@login_required
def agenda_main():
    tipos_agendamento_qtd = load_tipos()

    if "agenda_data" not in session:
        session["agenda_data"] = datetime.now().strftime("%Y-%m-%d")

    if request.method == "POST":
        acao = request.form.get("acao", "")
        if acao == "go_date":
            dt_post = request.form.get("data_selecionada", "")
            if dt_post:
                session["agenda_data"] = dt_post
        elif acao == "anterior":
            step = int(session.get("agenda_view", "1"))
            old_date = datetime.strptime(session["agenda_data"], "%Y-%m-%d")
            new_date = old_date - timedelta(days=step)
            session["agenda_data"] = new_date.strftime("%Y-%m-%d")
        elif acao == "proximo":
            step = int(session.get("agenda_view", "1"))
            old_date = datetime.strptime(session["agenda_data"], "%Y-%m-%d")
            new_date = old_date + timedelta(days=step)
            session["agenda_data"] = new_date.strftime("%Y-%m-%d")
        elif acao in ["view_1", "view_2", "view_7"]:
            session["agenda_view"] = acao.split('_')[1]
        return redirect(url_for("agenda_bp.agenda_main"))

    data_str = session.get("agenda_data", "")
    if not data_str:
        data_str = datetime.now().strftime("%Y-%m-%d")
        session["agenda_data"] = data_str

    view = session.get("agenda_view", "1")

    try:
        data_atual = datetime.strptime(data_str, "%Y-%m-%d")
    except ValueError:
        data_atual = datetime.now()

    if view == "7":
        num_dias = 7
    elif view == "2":
        num_dias = 2
    else:
        num_dias = 1

    dias_semana = []
    for i in range(num_dias):
        dia = data_atual + timedelta(days=i)
        dias_semana.append({
            "data": dia,
            "nome_dia": nomes_dias_semana[dia.weekday()],
            "fim_de_semana": dia.weekday() >= 5,
            "feriado": verificar_feriado(dia),
        })

    datas_para_carregar = [d["data"] for d in dias_semana]
    agendamentos = carregar_agendamentos(datas_para_carregar)
    semana_agendamentos = {}
    slots = gerar_slots()

    for d_info in dias_semana:
        dstr = d_info["data"].strftime("%Y-%m-%d")
        semana_agendamentos[dstr] = {}
        for s in slots:
            semana_agendamentos[dstr][s] = {}
            for cat in categorias:
                semana_agendamentos[dstr][s][cat] = {
                    "id": None,
                    "usuario": None,
                    "ordem_servico": None,
                    "tipo": None,
                    "slots_ocupados": [],
                    "quantidade_slots": 1,
                    "feito": False,
                    "exibir": True,
                    "rowspan": 1,
                    "criador": None,
                    "reagendado_por": None
                }

    from .utils_agenda import load_correcoes
    correcoes = load_correcoes()
    for dia in dias_semana:
        data_str = dia["data"].strftime("%Y-%m-%d")
        if data_str in correcoes:
            dia["status"] = correcoes[data_str]
        else:
            if verificar_feriado(dia["data"]):
                dia["status"] = "Feriado"
            elif dia["data"].weekday() >= 5:
                dia["status"] = "Plantão"
            else:
                dia["status"] = "Normal"

    from .utils_agenda import load_aniversariantes
    aniversariantes = load_aniversariantes()
    for dia in dias_semana:
        dia_str = dia["data"].strftime("%m-%d")
        nomes = [a["nome"]
                 for a in aniversariantes if a.get("data") == dia_str]
        if nomes:
            if len(nomes) == 1:
                dia["aniversario"] = "O aniversário de " + \
                    nomes[0] + " é nesta data"
            else:
                dia["aniversario"] = "Os aniversários de " + \
                    ", ".join(nomes) + " são nesta data"
        else:
            dia["aniversario"] = ""

    for ag in agendamentos:
        if "data" not in ag or "slots_ocupados" not in ag:
            continue
        ds = ag["data"]
        cat = ag["categoria"].strip()
        cat_norm = next(
            (c for c in categorias if c.lower() == cat.lower()), None)
        if not cat_norm:
            continue
        if ds not in semana_agendamentos:
            continue
        if not ag["slots_ocupados"]:
            continue
        p_slot = ag["slots_ocupados"][0]
        if p_slot in semana_agendamentos[ds]:
            semana_agendamentos[ds][p_slot][cat_norm].update({
                "id": ag["id"],
                "usuario": ag.get("usuario", "?"),
                "ordem_servico": ag["ordem_servico"],
                "tipo": ag["tipo"],
                "slots_ocupados": ag["slots_ocupados"],
                "quantidade_slots": ag.get("quantidade_slots", len(ag["slots_ocupados"])),
                "feito": ag.get("feito", False),
                "exibir": True,
                "rowspan": len(ag["slots_ocupados"]),
                "criador": ag.get("criador"),
                "reagendado_por": ag.get("reagendado_por")
            })
        for sidx in range(1, len(ag["slots_ocupados"])):
            slot_sub = ag["slots_ocupados"][sidx]
            if slot_sub in semana_agendamentos[ds]:
                semana_agendamentos[ds][slot_sub][cat_norm]["exibir"] = False

    return render_template(
        "agenda.html",
        slots=slots,
        dias_semana=dias_semana,
        categorias=categorias,
        tipos_agendamento=tipos_agendamento_qtd,
        semana_agendamentos=semana_agendamentos,
        data_atual=data_atual,
        view=view
    )


@agenda_bp.route("/agendar", methods=["POST"])
@login_required
def agendar():
    tipos_agendamento_qtd = load_tipos()
    ordem_servico = request.form.get("ordem_servico")
    data = request.form.get("data")
    slot_inicial = request.form.get("slot")
    categoria = request.form.get("categoria", "").strip()
    tipo = request.form.get("tipo")
    if not all([ordem_servico, data, slot_inicial, categoria, tipo]):
        flash("Campos obrigatórios faltando.", "danger")
        return redirect(url_for("agenda_bp.agenda_main"))

    qtd = tipos_agendamento_qtd.get(tipo, 1)
    slots = gerar_slots()
    if slot_inicial not in slots:
        flash("Horário inválido.", "danger")
        return redirect(url_for("agenda_bp.agenda_main"))

    idx_inicial = slots.index(slot_inicial)
    if idx_inicial + qtd > len(slots):
        flash("Horários insuficientes.", "danger")
        return redirect(url_for("agenda_bp.agenda_main"))

    slots_necessarios = slots[idx_inicial:idx_inicial+qtd]
    ags_mes = carregar_agendamentos([datetime.strptime(data, "%Y-%m-%d")])
    for a in ags_mes:
        if a.get("data") == data and a.get("categoria", "").strip().lower() == categoria.lower():
            if set(slots_necessarios) & set(a.get("slots_ocupados", [])):
                flash("Conflito de horários.", "danger")
                return redirect(url_for("agenda_bp.agenda_main"))

    all_ag_sameday = carregar_agendamentos(
        [datetime.strptime(data, "%Y-%m-%d")])
    max_seq = 0
    for a in all_ag_sameday:
        try:
            seq = int(str(a["id"]).split('-')[1])
            if seq > max_seq:
                max_seq = seq
        except:
            continue
    new_id = f"{data.replace('-', '')}-{max_seq + 1}"
    user_name = current_user.nome_completo
    hist_entry = {
        "usuario": user_name,
        "data_hora": datetime.now().isoformat(),
        "acao": "criou o agendamento"
    }

    novo = {
        "id": new_id,
        "usuario": user_name,
        "criador": user_name,
        "reagendado_por": None,
        "categoria": categoria,
        "ordem_servico": ordem_servico.upper(),
        "tipo": tipo,
        "data": data,
        "slots_ocupados": slots_necessarios,
        "quantidade_slots": qtd,
        "feito": False
    }
    salvar_agendamentos(novo)
    salvar_no_historico_global(new_id, novo["ordem_servico"], hist_entry)

    flash("Agendamento criado!", "success")
    current_app.extensions["socketio"].emit(
        "inserir-agendamento", novo, room=None)
    return redirect(url_for("agenda_bp.agenda_main"))


@agenda_bp.route("/remover", methods=["POST"])
@login_required
def remover_agendamento():
    ag_id = request.form.get("id")
    if not ag_id:
        flash("ID do agendamento é necessário.", "danger")
        return redirect(url_for("agenda_bp.agenda_main"))

    ag_atual, file_path = encontrar_agendamento_por_id(ag_id)
    if not ag_atual:
        flash("Agendamento não encontrado.", "danger")
        return redirect(url_for("agenda_bp.agenda_main"))

    with open(file_path, "r", encoding="utf-8") as f:
        try:
            ags = json.load(f)
        except:
            ags = []
    ags = [x for x in ags if x["id"] != ag_id]
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(ags, f, indent=4, ensure_ascii=False)

    hist = {
        "usuario": current_user.nome_completo,
        "data_hora": datetime.now().isoformat(),
        "acao": "removeu o agendamento"
    }
    salvar_no_historico_global(ag_id, ag_atual["ordem_servico"], hist)
    flash("Removido com sucesso!", "success")
    current_app.extensions["socketio"].emit(
        "remover-agendamento", {"id": ag_id}, room=None)
    return redirect(url_for("agenda_bp.agenda_main"))


@agenda_bp.route("/editar", methods=["POST"])
@login_required
def editar_agendamento():
    tipos_agendamento_qtd = load_tipos()
    ag_id = request.form.get("id")
    ordem = request.form.get("ordem_servico")
    dt_br = request.form.get("data")  # dd/mm/yyyy
    slot_inicial = request.form.get("slot")
    cat = request.form.get("categoria", "").strip()
    tipo = request.form.get("tipo")

    if not all([ag_id, ordem, dt_br, slot_inicial, cat, tipo]):
        flash("Campos obrigatórios faltando.", "danger")
        return redirect(url_for("agenda_bp.agenda_main"))

    try:
        dd, mm, yyyy = dt_br.split('/')
        dt_iso = f"{yyyy}-{mm}-{dd}"
    except:
        flash("Data inválida.", "danger")
        return redirect(url_for("agenda_bp.agenda_main"))

    qtd = tipos_agendamento_qtd.get(tipo, 1)
    slots = gerar_slots()
    if slot_inicial not in slots:
        flash("Horário inválido.", "danger")
        return redirect(url_for("agenda_bp.agenda_main"))

    idx_inicial = slots.index(slot_inicial)
    if idx_inicial + qtd > len(slots):
        flash("Horários insuficientes.", "danger")
        return redirect(url_for("agenda_bp.agenda_main"))

    slots_necessarios = slots[idx_inicial:idx_inicial+qtd]
    ag_atual, file_path = encontrar_agendamento_por_id(ag_id)
    if not ag_atual:
        flash("Agendamento não encontrado.", "danger")
        return redirect(url_for("agenda_bp.agenda_main"))

    with open(file_path, "r", encoding="utf-8") as f:
        try:
            ags = json.load(f)
        except:
            ags = []

    ags = [x for x in ags if x["id"] != ag_id]

    same_day_ag = carregar_agendamentos(
        [datetime.strptime(dt_iso, "%Y-%m-%d")])
    for x in same_day_ag:
        if x.get("id") == ag_id:
            continue
        if x.get("data") == dt_iso and x.get("categoria", "").strip().lower() == cat.lower():
            if set(slots_necessarios) & set(x.get("slots_ocupados", [])):
                flash("Conflito de horários.", "danger")
                return redirect(url_for("agenda_bp.agenda_main"))

    old = ag_atual.copy()
    data_ant = ag_atual["data"]
    mudou_data = (data_ant != dt_iso)

    ag_atual["ordem_servico"] = ordem.upper()
    ag_atual["data"] = dt_iso
    ag_atual["tipo"] = tipo
    ag_atual["categoria"] = cat
    ag_atual["slots_ocupados"] = slots_necessarios
    ag_atual["quantidade_slots"] = qtd
    ag_atual["usuario"] = current_user.nome_completo

    diffs = obter_diferencas(old, ag_atual)
    if diffs:
        hist = {
            "usuario": current_user.nome_completo,
            "data_hora": datetime.now().isoformat(),
            "mudancas": diffs
        }
        salvar_no_historico_global(ag_id, ag_atual["ordem_servico"], hist)

    if mudou_data:
        salvar_agendamentos(ag_atual)
        old_ag = carregar_agendamentos(
            [datetime.strptime(data_ant, "%Y-%m-%d")])
        old_ag = [xx for xx in old_ag if xx["id"] != ag_id]
        with open(file_path, "w", encoding="utf-8") as f2:
            json.dump(old_ag, f2, indent=4, ensure_ascii=False)
    else:
        ags.append(ag_atual)
        with open(file_path, "w", encoding="utf-8") as f3:
            json.dump(ags, f3, indent=4, ensure_ascii=False)

    flash("Agendamento atualizado!", "success")
    current_app.extensions["socketio"].emit(
        "atualizar-agendamento", ag_atual, room=None)
    return redirect(url_for("agenda_bp.agenda_main"))


@agenda_bp.route("/marcar_feito", methods=["POST"])
@login_required
def marcar_feito():
    ag_id = request.form.get("id")
    if not ag_id:
        flash("ID é necessário.", "danger")
        return redirect(url_for("agenda_bp.agenda_main"))

    ag_atual, file_path = encontrar_agendamento_por_id(ag_id)
    if not ag_atual:
        flash("Agendamento não encontrado.", "danger")
        return redirect(url_for("agenda_bp.agenda_main"))

    ag_atual["feito"] = not ag_atual.get("feito", False)
    acao = "marcou como feito" if ag_atual["feito"] else "desmarcou como feito"
    hist = {
        "usuario": current_user.nome_completo,
        "data_hora": datetime.now().isoformat(),
        "acao": acao
    }
    salvar_no_historico_global(ag_id, ag_atual["ordem_servico"], hist)

    with open(file_path, "r", encoding="utf-8") as f:
        try:
            ags = json.load(f)
        except:
            ags = []
    ags = [x for x in ags if x["id"] != ag_id]
    ags.append(ag_atual)
    with open(file_path, "w", encoding="utf-8") as f2:
        json.dump(ags, f2, indent=4, ensure_ascii=False)

    flash("Status atualizado!", "success")
    current_app.extensions["socketio"].emit(
        "atualizar-agendamento", ag_atual, room=None)
    return redirect(url_for("agenda_bp.agenda_main"))


@agenda_bp.route("/historico", methods=["GET"])
@login_required
def ver_historico():
    meses = listar_meses_historico()
    all_hist = []
    return render_template("historico.html", lista_meses=meses, historico_global=all_hist)


@agenda_bp.route("/historico/<int:ano>/<int:mes>", methods=["GET"])
@login_required
def historico_mes(ano, mes):
    meses = listar_meses_historico()
    hist_entries = carregar_historico_mes(ano, mes)

    search_q = request.args.get("q", "").lower()
    if search_q:
        filtered = []
        for e in hist_entries:
            combo = (
                str(e.get("agendamento_id", "")) + " " +
                e.get("ordem_servico", "") + " " +
                e.get("usuario", "") + " " +
                str(e.get("acao", "")) + " " +
                json.dumps(e.get("mudancas", ""))
            )
            if search_q in combo.lower():
                filtered.append(e)
        hist_entries = filtered

    return render_template("historico.html",
                           lista_meses=meses,
                           historico_global=hist_entries,
                           ano=ano,
                           mes=mes,
                           search_q=search_q)


@agenda_bp.route("/get_slots_disponiveis", methods=["GET"])
@login_required
def get_slots_disponiveis():
    tipos_agendamento_qtd = load_tipos()
    data = request.args.get("data")
    categoria = request.args.get("categoria", "").strip()
    tipo = request.args.get("tipo")
    if not all([data, categoria, tipo]):
        return jsonify([])
    try:
        data_dt = datetime.strptime(data, "%Y-%m-%d")
    except:
        return jsonify([])
    qtd = tipos_agendamento_qtd.get(tipo, 1)
    all_slots = gerar_slots()
    all_slots = [s for s in all_slots if "Intervalo" not in s]
    ags = carregar_agendamentos([data_dt])
    ocupados = set()
    for a in ags:
        if a.get("data") == data and a.get("categoria", "").strip().lower() == categoria.lower():
            for s in a.get("slots_ocupados", []):
                ocupados.add(s)
    livres = []
    for i in range(len(all_slots)):
        subset = all_slots[i:i+qtd]
        if len(subset) < qtd:
            break
        if any(s in ocupados for s in subset):
            continue
        livres.append(all_slots[i])
    return jsonify(livres)


@agenda_bp.route("/reagendar", methods=["POST"])
@login_required
def reagendar():
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "Dados inválidos."}), 400

    ag_id = data.get("id")
    nova_data = data.get("nova_data")
    novo_slot = data.get("novo_slot")
    categoria = data.get("categoria", "").strip()
    tipo = data.get("tipo", "")
    if not all([ag_id, nova_data, novo_slot, categoria, tipo]):
        return jsonify({"status": "error", "message": "Dados incompletos."}), 400

    try:
        nova_data_dt = datetime.strptime(nova_data, "%Y-%m-%d")
    except:
        return jsonify({"status": "error", "message": "Dados inválidos."}), 400

    ag_atual, file_path = encontrar_agendamento_por_id(ag_id)
    if not ag_atual:
        return jsonify({"status": "error", "message": "Agendamento não encontrado."}), 404

    qtd_atual = ag_atual.get("quantidade_slots", 1)
    slots = gerar_slots()
    if novo_slot not in slots:
        return jsonify({"status": "error", "message": "Horário inválido."}), 400

    idx_inicial = slots.index(novo_slot)
    if idx_inicial + qtd_atual > len(slots):
        return jsonify({"status": "error", "message": "Horários insuficientes."}), 400

    new_slots = slots[idx_inicial:idx_inicial + qtd_atual]
    ags_nova = carregar_agendamentos([nova_data_dt])
    for x in ags_nova:
        if x.get("id") == ag_id:
            continue
        if x.get("data") == nova_data and x.get("categoria", "").strip().lower() == categoria.lower():
            if set(new_slots) & set(x.get("slots_ocupados", [])):
                return jsonify({"status": "error", "message": "Conflito de horários."}), 409

    old = ag_atual.copy()
    ag_atual["data"] = nova_data
    ag_atual["slots_ocupados"] = new_slots
    ag_atual["tipo"] = tipo
    ag_atual["categoria"] = categoria
    if not ag_atual.get("criador"):
        ag_atual["criador"] = ag_atual.get("usuario", "?")
    ag_atual["reagendado_por"] = current_user.nome_completo
    ag_atual["quantidade_slots"] = qtd_atual
    ag_atual["usuario"] = ag_atual["criador"]

    diffs = obter_diferencas(old, ag_atual)
    if diffs:
        hist = {
            "usuario": current_user.nome_completo,
            "data_hora": datetime.now().isoformat(),
            "mudancas": diffs
        }
        salvar_no_historico_global(
            ag_atual["id"], ag_atual["ordem_servico"], hist)

    old_day = old["data"]
    ags_old = carregar_agendamentos([datetime.strptime(old_day, "%Y-%m-%d")])
    ags_old = [xx for xx in ags_old if xx["id"] != ag_id]
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(ags_old, f, indent=4, ensure_ascii=False)

    salvar_agendamentos(ag_atual)
    current_app.extensions["socketio"].emit(
        "atualizar-agendamento", ag_atual, room=None)
    return jsonify({"status": "success", "message": "Agendamento reagendado com sucesso."}), 200


@agenda_bp.route("/redimensionar_slots", methods=["POST"])
@login_required
def redimensionar_slots():
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "Dados inválidos."}), 400

    ag_id = data.get("id")
    nova_qtd = data.get("nova_qtd_slots")
    if not ag_id or not nova_qtd:
        return jsonify({"status": "error", "message": "Dados incompletos."}), 400

    try:
        nova_qtd = int(nova_qtd)
    except:
        return jsonify({"status": "error", "message": "Dados inválidos."}), 400

    if nova_qtd < 1:
        return jsonify({"status": "error", "message": "Quantidade de horários inválida."}), 400

    ag_atual, file_path = encontrar_agendamento_por_id(ag_id)
    if not ag_atual:
        return jsonify({"status": "error", "message": "Agendamento não encontrado."}), 404

    day = ag_atual["data"]
    slots = gerar_slots()
    slot_inicial = ag_atual["slots_ocupados"][0]
    if slot_inicial not in slots:
        return jsonify({"status": "error", "message": "Horário inicial inválido."}), 400

    idx_inicial = slots.index(slot_inicial)
    if idx_inicial + nova_qtd > len(slots):
        return jsonify({"status": "error", "message": "Horários insuficientes."}), 400

    new_slots = slots[idx_inicial:idx_inicial + nova_qtd]
    ags_data = carregar_agendamentos([datetime.strptime(day, "%Y-%m-%d")])
    for x in ags_data:
        if x["id"] == ag_id:
            continue
        if x.get("data") == day and x.get("categoria", "").strip().lower() == ag_atual["categoria"].strip().lower():
            if set(new_slots) & set(x.get("slots_ocupados", [])):
                return jsonify({"status": "error", "message": "Conflito de horários."}), 409

    old = ag_atual.copy()
    ag_atual["slots_ocupados"] = new_slots
    ag_atual["quantidade_slots"] = nova_qtd

    diffs = obter_diferencas(old, ag_atual)
    if diffs:
        hist = {
            "usuario": current_user.nome_completo,
            "data_hora": datetime.now().isoformat(),
            "mudancas": diffs
        }
        salvar_no_historico_global(ag_id, ag_atual["ordem_servico"], hist)

    with open(file_path, "r", encoding="utf-8") as f:
        try:
            ags = json.load(f)
        except:
            ags = []
    ags = [xx for xx in ags if xx["id"] != ag_id]
    ags.append(ag_atual)
    with open(file_path, "w", encoding="utf-8") as f2:
        json.dump(ags, f2, indent=4, ensure_ascii=False)

    current_app.extensions["socketio"].emit(
        "atualizar-agendamento", ag_atual, room=None)
    return jsonify({"status": "success", "message": "Agendamento redimensionado com sucesso."}), 200


@agenda_bp.route("/adicionar_tipo", methods=["POST"])
@login_required
def adicionar_tipo():
    nome = request.form.get("nome", "").strip()
    qtd_str = request.form.get("qtd", "").strip()
    if not nome or not qtd_str:
        flash("Nome e quantidade são obrigatórios.", "danger")
        return redirect(url_for("agenda_bp.agenda_main"))
    try:
        qtd = int(qtd_str)
        if qtd < 1:
            qtd = 1
    except:
        qtd = 1

    tipos = load_tipos()
    tipos[nome] = qtd
    save_tipos(tipos)

    flash("Novo tipo adicionado!", "success")
    return redirect(url_for("agenda_bp.agenda_main"))

# /AgendaLS/blueprints/agenda/agenda.py


@agenda_bp.route("/aniversariantes", methods=["GET", "POST"])
@login_required
def aniversariantes():
    from .utils_agenda import load_aniversariantes, save_aniversariantes
    if request.method == "POST":
        nome = request.form.get("nome")
        data = request.form.get("data")
        if data:
            try:
                dt = datetime.strptime(data, "%Y-%m-%d")
                birthday = dt.strftime("%m-%d")
            except:
                birthday = data
        else:
            birthday = ""
        if nome and birthday:
            aniversariantes_list = load_aniversariantes()
            aniversariantes_list.append({"nome": nome, "data": birthday})
            save_aniversariantes(aniversariantes_list)
    aniversariantes_list = load_aniversariantes()
    return render_template("aniversariantes.html", aniversariantes=aniversariantes_list)


@agenda_bp.route("/corrigir-data", methods=["GET", "POST"])
@login_required
def corrigir_data():
    from .utils_agenda import load_correcoes, save_correcoes
    if request.method == "POST":
        data = request.form.get("data")
        status = request.form.get("status")
        if data and status and status.lower() in ["normal", "feriado", "plantao", "reuniao"]:
            correcoes = load_correcoes()
            correcoes[data] = status.capitalize()
            save_correcoes(correcoes)
            flash("Status atualizado para a data " + data, "success")
        else:
            flash("Dados inválidos.", "danger")
        return redirect(url_for("agenda_bp.corrigir_data"))
    return render_template("corrigir_data.html")
