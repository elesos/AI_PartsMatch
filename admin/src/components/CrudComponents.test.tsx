import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { FormModal } from './FormModal'
import { ConfirmDialog } from './ConfirmDialog'
import { ImageUpload } from './ImageUpload'

beforeAll(() => { HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', '') }; HTMLDialogElement.prototype.close = function () { this.removeAttribute('open') } })
it('submits form modal and confirms destructive action', () => {
  const submit = vi.fn(event => event.preventDefault()); const close = vi.fn(); const { rerender } = render(<FormModal open title="新增配件" onClose={close} onSubmit={submit}><label>编号<input name="part_no" /></label></FormModal>)
  expect(screen.getByRole('dialog', { name: '新增配件' })).toBeInTheDocument(); fireEvent.submit(screen.getByRole('dialog').querySelector('form')!); expect(submit).toHaveBeenCalled()
  const confirm = vi.fn(); rerender(<ConfirmDialog open title="删除配件" description="删除后不可恢复" onCancel={close} onConfirm={confirm} />); fireEvent.click(screen.getByRole('button', { name: '确认删除' })); expect(confirm).toHaveBeenCalled()
})
it('validates, previews, uploads images and releases object URLs', async () => {
  const create = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:part'); const revoke = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined); const upload = vi.fn().mockResolvedValue(undefined)
  const { unmount } = render(<ImageUpload onUpload={upload} />); const input = screen.getByLabelText('选择配件图片')
  fireEvent.change(input, { target: { files: [new File(['x'], 'part.jpg', { type: 'image/jpeg' })] } }); expect(await screen.findByAltText('待上传图片 1')).toBeInTheDocument(); fireEvent.click(screen.getByRole('button', { name: '上传 1 张图片' })); await waitFor(() => expect(upload).toHaveBeenCalled())
  unmount(); expect(create).toHaveBeenCalled(); expect(revoke).toHaveBeenCalled(); create.mockRestore(); revoke.mockRestore()
})
