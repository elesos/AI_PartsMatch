from typing import Literal

from pydantic import BaseModel


class LanguagePreferenceRequest(BaseModel):
    lang: Literal["zh", "en", "vi"]
