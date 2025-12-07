from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID


class WordDictionaryBase(BaseModel):
    word: str = Field(..., description="Word text")
    lemma: Optional[str] = Field(None, description="Lemmatized form")
    df: Optional[int] = Field(0, description="Document frequency")


class WordDictionaryCreate(BaseModel):
    word: str
    lemma: Optional[str] = None
    df: Optional[int] = 0


class WordDictionaryUpdate(BaseModel):
    lemma: Optional[str] = None
    df: Optional[int] = None


class WordDictionary(WordDictionaryBase):
    word_id: int = Field(..., description="Unique word identifier")

    class Config:
        from_attributes = True


class WordDictionaryResponse(WordDictionary):
    pass


# Word occurrences for precise text search
class WordOccurrenceBase(BaseModel):
    word_id: int = Field(..., description="Word identifier")
    case_id: int = Field(..., description="Associated case ID")
    chunk_id: int = Field(..., description="Associated chunk ID")
    sentence_id: int = Field(..., description="Associated sentence ID")
    document_id: Optional[int] = Field(None, description="Associated document ID")
    position: int = Field(..., description="Token position within sentence")


class WordOccurrenceCreate(WordOccurrenceBase):
    pass


class WordOccurrence(WordOccurrenceBase):
    class Config:
        from_attributes = True
