"""Домен: понятия и инварианты механик без библиотек хранения, схем и HTTP.

Зависимости слоёв направлены сюда (docs/adr/0001-layers-and-ports.md): `domain` не импортирует
SQLAlchemy, Pydantic и FastAPI — это проверяет `tests/test_layers.py`.
"""
