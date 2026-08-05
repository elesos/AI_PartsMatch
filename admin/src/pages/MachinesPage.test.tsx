import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { AuthContext, type AuthContextValue } from '../contexts/AuthContext'
import * as machinesApi from '../services/machinesApi'
import * as partsApi from '../services/partsApi'
import type { Machine, MachineType, Fitment } from '../types/machines'
import type { Part } from '../types/parts'
import { MachinesPage } from './MachinesPage'

vi.mock('../services/machinesApi'); vi.mock('../services/partsApi')
beforeAll(() => { HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open','') }; HTMLDialogElement.prototype.close = function () { this.removeAttribute('open') } })

const type: MachineType = { id:'type-1',code:'forklift',name:'叉车',sort_order:10,is_active:true,created_at:'2026-01-01',updated_at:'2026-01-01' }
const machine: Machine = { id:'machine-1',machine_type:'forklift',brand:'Toyota',model:'8FD30',series:'8',year:2024,region:'CN',engine_model:'1DZ',notes:'出口版',created_at:'2026-01-01',updated_at:'2026-01-01' }
const fitment: Fitment = { id:'fit-1',machine_id:'machine-1',part_id:'part-1',system:'engine',position:'left',serial_from:'S001',serial_to:'S999',notes:'主滤芯',priority:8,is_active:true,part_no:'PN-001',part_name:'机油滤芯',part_brand:'CAT',part_category:'engine',created_at:'2026-01-01',updated_at:'2026-01-01' }
const part = { id:'part-1',sku:'SKU-1',part_no:'PN-001',oem_no:null,alternate_no:null,brand:'CAT',category:'engine',name_zh:'机油滤芯',name_en:null,name_vi:null,specs:{},unit:'件',price:null,stock:2,stock_status:'in_stock',is_active:true,notes:null,images:[],created_at:'2026-01-01',updated_at:'2026-01-01' } as Part
const auth = (role:'admin'|'operator'):AuthContextValue => ({ user:{id:'u1',username:role,role},ready:true,signIn:vi.fn(),signOut:vi.fn() })
const renderPage = (entry='/machines',role:'admin'|'operator'='admin') => render(<AuthContext.Provider value={auth(role)}><MemoryRouter initialEntries={[entry]}><Routes><Route path="/machines" element={<MachinesPage />} /><Route path="/machines/:machineId" element={<MachinesPage />} /></Routes></MemoryRouter></AuthContext.Provider>)

describe('MachinesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(machinesApi.listMachines).mockResolvedValue({items:[structuredClone(machine)],total:41,page:1,page_size:20})
    vi.mocked(machinesApi.getMachineOptions).mockResolvedValue({brands:['Toyota'],types:[structuredClone(type)]})
    vi.mocked(machinesApi.listMachineTypes).mockResolvedValue([structuredClone(type)])
    vi.mocked(machinesApi.getMachine).mockResolvedValue(structuredClone(machine))
    vi.mocked(machinesApi.listFitments).mockResolvedValue({items:[structuredClone(fitment)],total:1,page:1,page_size:100})
    vi.mocked(machinesApi.createMachine).mockResolvedValue(structuredClone(machine)); vi.mocked(machinesApi.updateMachine).mockResolvedValue(structuredClone(machine))
    vi.mocked(machinesApi.createFitment).mockResolvedValue(structuredClone(fitment)); vi.mocked(machinesApi.deleteFitment).mockResolvedValue({id:'fit-1'})
    vi.mocked(partsApi.listParts).mockResolvedValue({items:[structuredClone(part)],total:1,page:1,page_size:20})
    vi.mocked(machinesApi.importFitments).mockResolvedValue({created:0,valid:1,processed:2,dry_run:true,errors:[{line:3,message:'relation already exists',reason:'not_unique'}]})
  })

  it('uses URL-backed server pagination, model search and database type/brand filters', async () => {
    renderPage('/machines?q=8FD&type=forklift&brand=Toyota&page=2')
    expect(await screen.findByText('8FD30')).toBeInTheDocument()
    expect(machinesApi.listMachines).toHaveBeenCalledWith({q:'8FD',brand:'Toyota',machine_type:'forklift',page:2,page_size:20},expect.any(AbortSignal))
    fireEvent.change(screen.getByLabelText('搜索设备型号'),{target:{value:'PC200'}}); fireEvent.submit(screen.getByLabelText('搜索设备型号').closest('form')!)
    await waitFor(() => expect(machinesApi.listMachines).toHaveBeenLastCalledWith(expect.objectContaining({q:'PC200',page:1}),expect.any(AbortSignal)))
    fireEvent.change(screen.getByLabelText('设备类型筛选'),{target:{value:'forklift'}})
    await waitFor(() => expect(machinesApi.listMachines).toHaveBeenLastCalledWith(expect.objectContaining({machine_type:'forklift'}),expect.any(AbortSignal)))
  })

  it('creates a complete machine and manages extensible machine types without hard-coded options', async () => {
    vi.mocked(machinesApi.createMachineType).mockResolvedValue({...type,id:'type-2',code:'telehandler',name:'伸缩臂叉装车'})
    renderPage(); await screen.findByText('8FD30'); fireEvent.click(screen.getByRole('button',{name:'新增设备'}))
    const dialog=screen.getByRole('dialog',{name:'新增设备'}); fireEvent.change(within(dialog).getByLabelText('设备类型'),{target:{value:'forklift'}}); fireEvent.change(within(dialog).getByLabelText('品牌'),{target:{value:'JCB'}}); fireEvent.change(within(dialog).getByLabelText('型号'),{target:{value:'540-170'}}); fireEvent.change(within(dialog).getByLabelText('年份'),{target:{value:'2025'}}); fireEvent.change(within(dialog).getByLabelText('地区版本'),{target:{value:'EU'}}); fireEvent.change(within(dialog).getByLabelText('发动机型号'),{target:{value:'EcoMAX'}}); fireEvent.change(within(dialog).getByLabelText('备注'),{target:{value:'Stage V'}}); fireEvent.click(within(dialog).getByRole('button',{name:'保存记录'}))
    await waitFor(() => expect(machinesApi.createMachine).toHaveBeenCalledWith(expect.objectContaining({machine_type:'forklift',brand:'JCB',model:'540-170',year:2025,region:'EU',engine_model:'EcoMAX',notes:'Stage V'})))
    fireEvent.click(screen.getByRole('button',{name:'管理设备类型'})); fireEvent.click(screen.getByRole('button',{name:'新增类型'})); const typeDialog=screen.getByRole('dialog',{name:'新增设备类型'}); fireEvent.change(within(typeDialog).getByLabelText('类型代码'),{target:{value:'telehandler'}}); fireEvent.change(within(typeDialog).getByLabelText('显示名称'),{target:{value:'伸缩臂叉装车'}}); fireEvent.click(within(typeDialog).getByRole('button',{name:'保存记录'}))
    await waitFor(() => expect(machinesApi.createMachineType).toHaveBeenCalledWith(expect.objectContaining({code:'telehandler',name:'伸缩臂叉装车'})))
  })

  it('adds and deletes fitments and performs real CSV preview then partial-success import', async () => {
    renderPage('/machines/machine-1'); expect(await screen.findByText('PN-001')).toBeInTheDocument(); expect(screen.getByText(/S001/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button',{name:'新增关系'})); const dialog=screen.getByRole('dialog',{name:'新增适配关系'}); await within(dialog).findByRole('option',{name:/PN-001/}); fireEvent.change(within(dialog).getByLabelText('配件'),{target:{value:'part-1'}}); fireEvent.change(within(dialog).getByLabelText('配件系统'),{target:{value:'engine'}}); fireEvent.change(within(dialog).getByLabelText('序列号起'),{target:{value:'A001'}}); fireEvent.click(within(dialog).getByRole('button',{name:'保存记录'})); await waitFor(() => expect(machinesApi.createFitment).toHaveBeenCalledWith(expect.objectContaining({machine_id:'machine-1',part_id:'part-1',system:'engine',serial_from:'A001'})))
    fireEvent.click(within(screen.getByLabelText('设备详情')).getByRole('button',{name:'删除'})); const confirm=screen.getByRole('dialog',{name:'删除适配关系'}); fireEvent.click(within(confirm).getByRole('button',{name:'确认删除'})); await waitFor(() => expect(machinesApi.deleteFitment).toHaveBeenCalledWith('fit-1'))
    const file=new File(['part_id,system\npart-1,engine'],'fitments.csv',{type:'text/csv'}); fireEvent.change(screen.getByLabelText('选择 CSV 并预检'),{target:{files:[file]}}); await waitFor(() => expect(machinesApi.importFitments).toHaveBeenCalledWith('machine-1',file,true)); expect(await screen.findByText(/2 行 \/ 1 行有效 \/ 1 行失败/)).toBeInTheDocument()
    vi.mocked(machinesApi.importFitments).mockResolvedValueOnce({created:1,valid:1,processed:2,dry_run:false,errors:[{line:3,message:'relation already exists',reason:'not_unique'}]}); fireEvent.click(screen.getByRole('button',{name:'确认导入 1 行'})); await waitFor(() => expect(machinesApi.importFitments).toHaveBeenLastCalledWith('machine-1',file,false)); expect(await screen.findByText('已创建 1 条关系')).toBeInTheDocument()
  })

  it('keeps operator access read-only while allowing lists and relation details', async () => {
    renderPage('/machines/machine-1','operator'); expect(await screen.findByText('PN-001')).toBeInTheDocument(); expect(screen.getByText(/OPERATOR READ ONLY/)).toBeInTheDocument(); expect(screen.queryByRole('button',{name:'新增设备'})).not.toBeInTheDocument(); expect(screen.queryByRole('button',{name:'新增关系'})).not.toBeInTheDocument(); expect(screen.queryByText('批量导入 CSV')).not.toBeInTheDocument()
  })
})
