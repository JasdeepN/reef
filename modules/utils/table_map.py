from modules.models import db as models_db

TABLE_MAP = {
    model.__tablename__: model
    for model in models_db.Model.registry._class_registry.values()
    if isinstance(model, type) and hasattr(model, "__tablename__")
}