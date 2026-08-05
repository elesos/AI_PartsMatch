const MAX_SIZE = 10 * 1024 * 1024
const allowedExtensions = new Set(['jpg', 'jpeg', 'png', 'webp', 'heic', 'heif'])
const allowedMimes = new Set(['image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif'])
const extensionMimes: Record<string, string[]> = {
  jpg: ['image/jpeg'], jpeg: ['image/jpeg'], png: ['image/png'], webp: ['image/webp'],
  heic: ['image/heic', 'image/heif'], heif: ['image/heic', 'image/heif'],
}

export const validateImageFile = (file: File): string | null => {
  const extension = file.name.split('.').pop()?.toLowerCase() ?? ''
  if (!allowedExtensions.has(extension)) return '仅支持 JPG、JPEG、PNG、WebP 或 HEIC 图片'
  if (file.type && !allowedMimes.has(file.type.toLowerCase())) return '文件内容类型与支持的图片格式不符'
  if (file.type && !extensionMimes[extension].includes(file.type.toLowerCase())) return '图片扩展名与内容类型不一致'
  if (!file.type && !['heic', 'heif'].includes(extension)) return '无法确认图片类型，请重新导出后上传'
  if (file.size > MAX_SIZE) return '单张图片不能超过 10MB'
  if (file.size === 0) return '图片文件为空'
  return null
}
