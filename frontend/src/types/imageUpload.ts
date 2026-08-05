import type { JsonValue, SearchResult } from './home'

export type UploadKind = 'part_photo' | 'machine_nameplate' | 'engine_nameplate' | 'package_label'
export type RecognitionStep = 'upload' | 'ocr' | 'parse' | 'match'

export interface UploadedImage {
  image_id: string
  url: string
  mime_type: string
  size: number
}

export interface OcrResult { image_id: string; raw_text: string; lines: string[] }

export interface ParsedImage extends OcrResult {
  image_type: string
  confidence: number
  extracted_info: Record<string, JsonValue>
}

export interface ImageMatchResult extends SearchResult {
  images?: ParsedImage[]
}

export interface UploadResultState {
  images: UploadedImage[]
  parsed: ParsedImage[]
  kind: UploadKind
  matchResult?: ImageMatchResult
  issueCode?: string
}
