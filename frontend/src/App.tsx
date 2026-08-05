import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import { AppLayout } from './components/AppLayout'
import { ToastViewport } from './components/ToastViewport'
import { HomePage } from './pages/HomePage'
import { NotFoundPage } from './pages/NotFoundPage'
import { PartDetailPage } from './pages/PartDetailPage'
import { SearchPage } from './pages/SearchPage'
import { UploadPage } from './pages/UploadPage'
import { UploadResultPage } from './pages/UploadResultPage'
import { CartPage } from './pages/CartPage'
import { InquiryPage } from './pages/InquiryPage'
import { InquirySuccessPage } from './pages/InquirySuccessPage'
import { BatchPage } from './pages/BatchPage'
import { BatchResultPage } from './pages/BatchResultPage'

const router = createBrowserRouter([{
  path: '/', element: <AppLayout />, errorElement: <NotFoundPage />, children: [
    { index: true, element: <HomePage /> },
    { path: 'search', element: <SearchPage /> },
    { path: 'parts/:id', element: <PartDetailPage /> },
    { path: 'upload', element: <UploadPage /> },
    { path: 'upload/result', element: <UploadResultPage /> },
    { path: 'batch', element: <BatchPage /> },
    { path: 'batch/result', element: <BatchResultPage /> },
    { path: 'cart', element: <CartPage /> },
    { path: 'inquiry', element: <InquiryPage /> },
    { path: 'inquiry/success', element: <InquirySuccessPage /> },
    { path: '*', element: <NotFoundPage /> },
  ],
}])

export default function App() { return <><RouterProvider router={router} /><ToastViewport /></> }
