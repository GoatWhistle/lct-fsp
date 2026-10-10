from html import escape

from app.adapter.brand.palette import hex_color
from app.adapter.brand.words import Words
from app.domain.locale import Locale
from app.domain.mail import Mail

UI_STACK = "Onest, 'Segoe UI', Roboto, Arial, sans-serif"
MONO_STACK = "'JetBrains Mono', 'SFMono-Regular', Consolas, monospace"
TABLE = 'role="presentation" cellpadding="0" cellspacing="0"'


def _style(**rules: str) -> str:
    return ";".join(f"{name.replace('_', '-')}:{value}" for name, value in rules.items())


def _paragraph(value: str, **rules: str) -> str:
    return f'<p style="{_style(**rules)}">{escape(value)}</p>'


def _lockup(words: Words) -> str:
    style = _style(
        padding="0 4px 16px",
        font_family=MONO_STACK,
        font_size="20px",
        font_weight="700",
        color=hex_color("text-primary"),
    )
    return f'<tr><td style="{style}">{escape(words("brand.name"))}</td></tr>'


def _card(body: str) -> str:
    style = _style(
        background=hex_color("surface-card"),
        border=f"1px solid {hex_color('border-hairline')}",
        border_radius="12px",
        padding="32px",
        font_family=UI_STACK,
        color=hex_color("text-primary"),
    )
    return f'<tr><td style="{style}">{body}</td></tr>'


def _footer(words: Words) -> str:
    style = _style(
        padding="16px 4px",
        font_family=UI_STACK,
        font_size="12px",
        line_height="18px",
        color=hex_color("text-tertiary"),
    )
    return f'<tr><td style="{style}">{escape(words("mail.footer"))}</td></tr>'


def _page(words: Words, preheader: str, body: str) -> str:
    canvas = hex_color("surface-canvas")
    hidden = _style(display="none", max_height="0", overflow="hidden")
    rows = _lockup(words) + _card(body) + _footer(words)
    return (
        f'<!doctype html><html lang="{words.locale}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1"></head>'
        f'<body style="margin:0;padding:0;background:{canvas};">'
        f'<div style="{hidden}">{escape(preheader)}</div>'
        f'<table {TABLE} width="100%" style="background:{canvas};">'
        '<tr><td align="center" style="padding:32px 16px;">'
        f'<table {TABLE} width="100%" style="max-width:560px;">{rows}</table>'
        "</td></tr></table></body></html>"
    )


def _button(label: str, link: str) -> str:
    action = hex_color("action-primary")
    style = _style(
        display="inline-block",
        padding="14px 24px",
        font_family=MONO_STACK,
        font_size="14px",
        font_weight="700",
        color=hex_color("text-on-action"),
        text_decoration="none",
        border_radius="8px",
    )
    return (
        f'<table {TABLE}><tr><td style="border-radius:8px;background:{action};">'
        f'<a href="{link}" style="{style}">{escape(label)}</a></td></tr></table>'
    )


def _link_mail(
    words: Words, key: str, to: str, link: str, ttl_hours: int, **values: object
) -> Mail:
    """Письмо со ссылкой подтверждения: приветствие, пояснение, кнопка, ссылка текстом и срок."""
    greeting = words(f"{key}.greeting")
    lead = words(f"{key}.lead", **values)
    ttl = words(f"{key}.ttl", hours=ttl_hours)
    ignore = words(f"{key}.ignore")
    safe = escape(link, quote=True)
    muted = hex_color("text-tertiary")
    link_style = _style(
        margin="0 0 24px",
        font_family=MONO_STACK,
        font_size="12px",
        line_height="18px",
        word_break="break-all",
    )
    body = "".join(
        [
            _paragraph(
                greeting,
                margin="0 0 8px",
                font_size="22px",
                line_height="28px",
                font_weight="600",
            ),
            _paragraph(
                lead,
                margin="0 0 24px",
                font_size="16px",
                line_height="24px",
                color=hex_color("text-secondary"),
            ),
            _button(words(f"{key}.button"), safe),
            _paragraph(
                words(f"{key}.fallback"),
                margin="24px 0 4px",
                font_size="13px",
                line_height="20px",
                color=muted,
            ),
            f'<p style="{link_style}"><a href="{safe}" '
            f'style="color:{hex_color("action-primary")};">{safe}</a></p>',
            _paragraph(
                f"{ttl} {ignore}",
                margin="0",
                font_size="13px",
                line_height="20px",
                color=muted,
            ),
        ]
    )
    return Mail(
        to=to,
        subject=words(f"{key}.subject", **values),
        text="\n\n".join([greeting, lead, link, ttl, ignore]),
        html=_page(words, words(f"{key}.preheader", **values), body),
    )


class BrandMailTemplates:
    def verification(self, to: str, link: str, ttl_hours: int, locale: Locale) -> Mail:
        return _link_mail(Words(locale), "mail.verification", to, link, ttl_hours)

    def domain_verification(
        self, to: str, link: str, ttl_hours: int, company: str, domain: str, locale: Locale
    ) -> Mail:
        return _link_mail(
            Words(locale),
            "mail.domain",
            to,
            link,
            ttl_hours,
            company=company,
            domain=domain,
        )
