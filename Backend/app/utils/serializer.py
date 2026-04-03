from datetime import datetime
from typing import Any

from bson import ObjectId


# Convert Mongo types to JSON-serializable values.
def serialize_document(document: Any) -> Any:
    if isinstance(document, list):
        return [serialize_document(item) for item in document]

    if isinstance(document, dict):
        return {key: serialize_document(value) for key, value in document.items()}

    if isinstance(document, ObjectId):
        return str(document)

    if isinstance(document, datetime):
        return document.isoformat()

    return document
