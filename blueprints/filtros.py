from datetime import datetime

def formato_datahora(value):
    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime("%d/%m/%Y - %H:%M:%S")
    except:
        return value
