import { validateImageFile } from './imageValidation'

describe('image validation', () => {
  it.each([
    ['part.jpg', 'image/jpeg'], ['part.JPEG', 'image/jpeg'], ['part.png', 'image/png'],
    ['part.webp', 'image/webp'], ['part.heic', 'image/heic'], ['part.HEIF', ''],
  ])('accepts supported image %s', (name, type) => {
    expect(validateImageFile(new File(['image'], name, { type }))).toBeNull()
  })

  it('validates extension, MIME, size and empty files', () => {
    expect(validateImageFile(new File(['x'], 'part.gif', { type: 'image/gif' }))).toMatch(/仅支持/)
    expect(validateImageFile(new File(['x'], 'part.jpg', { type: 'text/plain' }))).toMatch(/内容类型/)
    expect(validateImageFile(new File(['x'], 'part.png', { type: 'image/jpeg' }))).toMatch(/不一致/)
    expect(validateImageFile(new File(['x'], 'part.jpg'))).toMatch(/无法确认/)
    expect(validateImageFile(new File([new Uint8Array(10 * 1024 * 1024 + 1)], 'part.png', { type: 'image/png' }))).toMatch(/10MB/)
    expect(validateImageFile(new File([], 'part.png', { type: 'image/png' }))).toMatch(/为空/)
  })
})
