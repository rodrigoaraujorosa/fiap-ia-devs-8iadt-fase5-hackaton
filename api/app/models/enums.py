from enum import StrEnum


class Intent(StrEnum):
    COMPRA = "compra"
    ALUGUEL = "aluguel"
    INVESTIMENTO = "investimento"
    INDEFINIDO = "indefinido"


class LeadStatus(StrEnum):
    NOVO = "novo"
    EM_QUALIFICACAO = "em_qualificacao"
    QUALIFICADO = "qualificado"
    AGENDADO = "agendado"
    ENCAMINHADO = "encaminhado"
    PERDIDO = "perdido"


class Temperature(StrEnum):
    QUENTE = "quente"
    MORNO = "morno"
    FRIO = "frio"


class Urgency(StrEnum):
    ALTA = "alta"
    MEDIA = "media"
    BAIXA = "baixa"


class Channel(StrEnum):
    WEB = "web"
    SITE = "site"  # widget embutido no site de uma imobiliária
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    FOLLOWUP = "followup"
    SYSTEM = "system"


class PropertyPurpose(StrEnum):
    VENDA = "venda"
    ALUGUEL = "aluguel"


class UserRole(StrEnum):
    ADMIN = "admin"
    GESTOR = "gestor"
    CORRETOR = "corretor"  # só os leads e as visitas do corretor vinculado
    VISUALIZADOR = "visualizador"  # só leitura


class BrokerRole(StrEnum):
    CORRETOR = "corretor"
    ESPECIALISTA_INVESTIMENTO = "especialista_investimento"


class AppointmentKind(StrEnum):
    VISITA = "visita"
    REUNIAO = "reuniao"
    VIDEOCHAMADA = "videochamada"


class AppointmentStatus(StrEnum):
    AGENDADO = "agendado"
    CONFIRMADO = "confirmado"
    CANCELADO = "cancelado"
    REALIZADO = "realizado"
